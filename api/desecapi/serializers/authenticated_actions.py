import binascii
import json
from datetime import timedelta

from django.conf import settings
from rest_framework import fields, serializers
from rest_framework.settings import api_settings
from rest_framework.validators import UniqueValidator, qs_filter

from desecapi import crypto, models

from .captcha import CaptchaSolutionSerializer


class CustomFieldNameUniqueValidator(UniqueValidator):
    """
    Does exactly what rest_framework's UniqueValidator does, however allows to further customize the
    query that is used to determine the uniqueness.
    More specifically, we allow that the field name the value is queried against is passed when initializing
    this validator. (At the time of writing, UniqueValidator insists that the field's name is used for the
    database query field; only how the lookup must match is allowed to be changed.)
    """

    def __init__(self, queryset, message=None, lookup="exact", lookup_field=None):
        self.lookup_field = lookup_field
        super().__init__(queryset, message, lookup)

    def filter_queryset(self, value, queryset, field_name):
        """
        Filter the queryset to all instances matching the given value on the specified lookup field.
        """
        filter_kwargs = {
            "%s__%s" % (self.lookup_field or field_name, self.lookup): value
        }
        return qs_filter(queryset, **filter_kwargs)


class AuthenticatedActionSerializer(serializers.ModelSerializer):
    state = serializers.CharField()  # serializer read-write, but model read-only field
    validity_period = settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE

    _crypto_context = "desecapi.serializers.AuthenticatedActionSerializer"
    timestamp = None  # is set to the code's timestamp during validation

    class Meta:
        model = models.AuthenticatedAction
        fields = ("state",)

    @classmethod
    def _pack_code(cls, data):
        payload = json.dumps(data).encode()
        code = crypto.encrypt(payload, context=cls._crypto_context).decode()
        return code.rstrip("=")

    @classmethod
    def _unpack_code(cls, code, *, ttl):
        code += -len(code) % 4 * "="
        try:
            timestamp, payload = crypto.decrypt(
                code.encode(), context=cls._crypto_context, ttl=ttl
            )
            return timestamp, json.loads(payload.decode())
        except (
            TypeError,
            UnicodeDecodeError,
            UnicodeEncodeError,
            json.JSONDecodeError,
            binascii.Error,
        ):
            raise ValueError

    def to_representation(self, instance: models.AuthenticatedAction):
        # do the regular business
        data = super().to_representation(instance)

        # encode into single string
        return {"code": self._pack_code(data)}

    def to_internal_value(self, data):
        # Allow injecting validity period from context.  This is used, for example, for authentication, where the code's
        # integrity and timestamp is checked by AuthenticatedBasicUserActionSerializer with validity injected as needed.
        validity_period = self.context.get("validity_period", self.validity_period)
        # calculate code TTL
        try:
            ttl = validity_period.total_seconds()
        except AttributeError:
            ttl = None  # infinite

        # decode from single string
        try:
            self.timestamp, unpacked_data = self._unpack_code(
                self.context["code"], ttl=ttl
            )
        except KeyError:
            raise serializers.ValidationError({"code": ["This field is required."]})
        except ValueError:
            if ttl is None:
                msg = "This code is invalid."
            else:
                msg = f"This code is invalid, possibly because it expired (validity: {validity_period})."
            raise serializers.ValidationError({api_settings.NON_FIELD_ERRORS_KEY: msg})

        # add extra fields added by the user, but give precedence to fields unpacked from the code
        data = {**data, **unpacked_data}

        # do the regular business
        return super().to_internal_value(data)

    def act(self):
        self.instance.act()
        return self.instance

    def save(self, **kwargs):
        raise ValueError


class AuthenticatedBasicUserActionMixin:
    def save(self, **kwargs):
        context = {**self.context, "action_serializer": self}
        return self.action_user.send_email(self.reason, context=context, **kwargs)


class AuthenticatedBasicUserActionSerializer(
    AuthenticatedBasicUserActionMixin, AuthenticatedActionSerializer
):
    user = serializers.PrimaryKeyRelatedField(
        queryset=models.User.objects.all(),
        error_messages={"does_not_exist": "This user does not exist."},
        pk_field=serializers.UUIDField(),
    )

    reason = None

    class Meta:
        model = models.AuthenticatedBasicUserAction
        fields = AuthenticatedActionSerializer.Meta.fields + ("user",)

    @property
    def action_user(self):
        return self.instance.user

    @classmethod
    def build_and_save(cls, **kwargs):
        action = cls.Meta.model(**kwargs)
        return cls(action).save()


class AuthenticatedBasicUserActionListSerializer(
    AuthenticatedBasicUserActionMixin, serializers.ListSerializer
):
    @property
    def reason(self):
        return self.child.reason

    @property
    def action_user(self):
        user = self.instance[0].user
        if any(instance.user != user for instance in self.instance):
            raise ValueError("Actions must belong to the same user.")
        return user


class AuthenticatedChangeOutreachPreferenceUserActionSerializer(
    AuthenticatedBasicUserActionSerializer
):
    reason = "change-outreach-preference"
    validity_period = None

    class Meta:
        model = models.AuthenticatedChangeOutreachPreferenceUserAction
        fields = AuthenticatedBasicUserActionSerializer.Meta.fields + (
            "outreach_preference",
        )


class AuthenticatedActivateUserActionSerializer(AuthenticatedBasicUserActionSerializer):
    captcha = CaptchaSolutionSerializer(required=False)

    reason = "activate-account"

    class Meta(AuthenticatedBasicUserActionSerializer.Meta):
        model = models.AuthenticatedActivateUserAction
        fields = AuthenticatedBasicUserActionSerializer.Meta.fields + (
            "captcha",
            "domain",
        )
        extra_kwargs = {"domain": {"default": None, "allow_null": True}}

    def validate(self, attrs):
        try:
            attrs.pop(
                "captcha"
            )  # remove captcha from internal value to avoid passing to Meta.model(**kwargs)
        except KeyError:
            if attrs["user"].needs_captcha:
                raise serializers.ValidationError(
                    {"captcha": fields.Field.default_error_messages["required"]}
                )
        return attrs


class AuthenticatedChangeEmailUserActionSerializer(
    AuthenticatedBasicUserActionSerializer
):
    new_email = serializers.EmailField(
        validators=[
            CustomFieldNameUniqueValidator(
                queryset=models.User.objects.all(),
                lookup_field="email",
                message="You already have another account with this email address.",
            )
        ],
        required=True,
    )

    reason = "change-email"

    class Meta(AuthenticatedBasicUserActionSerializer.Meta):
        model = models.AuthenticatedChangeEmailUserAction
        fields = AuthenticatedBasicUserActionSerializer.Meta.fields + ("new_email",)

    def save(self):
        return super().save(recipient=self.instance.new_email)


class AuthenticatedConfirmAccountUserActionSerializer(
    AuthenticatedBasicUserActionSerializer
):
    reason = "confirm-account"
    validity_period = timedelta(days=14)

    class Meta(AuthenticatedBasicUserActionSerializer.Meta):
        model = (
            models.AuthenticatedNoopUserAction
        )  # confirmation happens during authentication, so nothing left to do


class AuthenticatedCreateTOTPFactorUserActionSerializer(
    AuthenticatedBasicUserActionSerializer
):
    reason = "create-totp"
    validity_period = timedelta(hours=1)

    class Meta(AuthenticatedBasicUserActionSerializer.Meta):
        model = models.AuthenticatedCreateTOTPFactorUserAction
        fields = AuthenticatedBasicUserActionSerializer.Meta.fields + ("name",)


class AuthenticatedResetPasswordUserActionSerializer(
    AuthenticatedBasicUserActionSerializer
):
    new_password = serializers.CharField(write_only=True)

    reason = "reset-password"

    class Meta(AuthenticatedBasicUserActionSerializer.Meta):
        model = models.AuthenticatedResetPasswordUserAction
        fields = AuthenticatedBasicUserActionSerializer.Meta.fields + ("new_password",)


class AuthenticatedDeleteUserActionSerializer(AuthenticatedBasicUserActionSerializer):
    reason = "delete-account"

    class Meta(AuthenticatedBasicUserActionSerializer.Meta):
        model = models.AuthenticatedDeleteUserAction


class AuthenticatedDomainBasicUserActionSerializer(
    AuthenticatedBasicUserActionSerializer
):
    domain = serializers.PrimaryKeyRelatedField(
        queryset=models.Domain.objects.all(),
        error_messages={"does_not_exist": "This domain does not exist."},
    )

    class Meta:
        model = models.AuthenticatedDomainBasicUserAction
        fields = AuthenticatedBasicUserActionSerializer.Meta.fields + ("domain",)


class AuthenticatedRenewDomainBasicUserActionSerializer(
    AuthenticatedDomainBasicUserActionSerializer
):
    reason = "renew-domain"
    validity_period = None

    class Meta(AuthenticatedDomainBasicUserActionSerializer.Meta):
        model = models.AuthenticatedRenewDomainBasicUserAction
        list_serializer_class = AuthenticatedBasicUserActionListSerializer
