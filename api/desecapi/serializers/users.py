from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from desecapi.models import TokenDomainPolicy, User, validate_domain_name

from .captcha import CaptchaSolutionSerializer
from .domains import DomainSerializer


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailPasswordSerializer(EmailSerializer):
    password = serializers.CharField()


class ChangeEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        if value == self.context["request"].user.email:
            raise serializers.ValidationError("Email address unchanged.")
        return value


class ResetPasswordSerializer(EmailSerializer):
    captcha = CaptchaSolutionSerializer(required=True)


class UserSerializer(serializers.ModelSerializer):
    domains_under_management = serializers.SerializerMethodField()
    insecure_delegated_domains = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "created",
            "domains_under_management",
            "email",
            "id",
            "limit_domains",
            "limit_insecure_domains",
            "insecure_delegated_domains",
            "outreach_preference",
        )
        read_only_fields = (
            "created",
            "domains_under_management",
            "email",
            "id",
            "limit_domains",
            "limit_insecure_domains",
            "insecure_delegated_domains",
        )

    def get_domains_under_management(self, obj):
        return obj.domains.count() + (
            TokenDomainPolicy.objects.filter(token__owner=obj)
            .exclude(token__user_override=None)
            .exclude(domain=None)
            .values("domain")
            .distinct()
            .count()
        )

    def get_insecure_delegated_domains(self, obj):
        return obj.domains.filter(is_registered=True, is_delegated=True).exclude(
            is_secured=True
        ).count()

    def validate_password(self, value):
        if value is not None:
            validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class RegisterAccountSerializer(UserSerializer):
    domain = serializers.CharField(required=False, validators=validate_domain_name)
    captcha = CaptchaSolutionSerializer(required=False)

    class Meta:
        model = UserSerializer.Meta.model
        fields = (
            "email",
            "password",
            "domain",
            "captcha",
            "outreach_preference",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,  # Do not expose password field
                "allow_null": True,
            }
        }

    def validate_domain(self, value):
        serializer = DomainSerializer(data=dict(name=value), context=self.context)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError:
            raise serializers.ValidationError(
                serializer.default_error_messages["name_unavailable"],
                code="name_unavailable",
            )
        return value

    def validate(self, attrs):
        if (
            not settings.REGISTER_LPS
            and attrs.get("captcha") is not None
            and attrs.get("domain") is not None
            and DomainSerializer.Meta.model(name=attrs["domain"]).is_locally_registrable
        ):
            raise serializers.ValidationError(
                {
                    "domain": [
                        DomainSerializer.default_error_messages["name_unavailable"]
                    ]
                },
                code="name_unavailable",
            )
        return super().validate(attrs)

    def create(self, validated_data):
        validated_data.pop("domain", None)
        # If validated_data['captcha'] exists, the captcha was also validated, so we can set the user to verified
        if "captcha" in validated_data:
            validated_data.pop("captcha")
            validated_data["needs_captcha"] = False
        return super().create(validated_data)
