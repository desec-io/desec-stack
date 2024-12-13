import django.core.exceptions
from netfields.rest_framework import CidrAddressField
from rest_framework import serializers

from desecapi import models, validators


class SensitiveSlugRelatedField(serializers.SlugRelatedField):
    def to_internal_value(self, data):
        queryset = self.get_queryset()
        try:
            return queryset.get(**{self.slug_field: data})
        except django.core.exceptions.ObjectDoesNotExist:
            # Retain to prevent responses from exposing object non-existence in database
            return queryset.model(**{self.slug_field: data})
        except (TypeError, ValueError):
            self.fail("invalid")


class TokenSerializer(serializers.ModelSerializer):
    owner = serializers.SlugRelatedField(slug_field="email", read_only=True)
    user_override = SensitiveSlugRelatedField(
        slug_field="email",
        queryset=models.User.objects.all(),
        allow_null=True,
        default=None,
    )
    allowed_subnets = serializers.ListField(child=CidrAddressField(), required=False)
    token = serializers.ReadOnlyField(source="plain")
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = models.Token
        fields = (
            "id",
            "created",
            "last_used",
            "owner",
            "user_override",
            "max_age",
            "max_unused_period",
            "name",
            "perm_create_domain",
            "perm_delete_domain",
            "perm_manage_tokens",
            "allowed_subnets",
            "auto_policy",
            "is_valid",
            "token",
        )
        read_only_fields = (
            "id",
            "created",
            "last_used",
            "owner",
            "token",
        )

    def __init__(self, *args, include_plain=False, **kwargs):
        self.include_plain = include_plain
        super().__init__(*args, **kwargs)

    def get_fields(self):
        fields = super().get_fields()
        if not self.include_plain:
            fields.pop("token")
        fields["user_override"].validators.append(
            validators.ReadOnlyOnUpdateValidator()
        )
        return fields

    def validate_user_override(self, value):
        if self.instance and value != self.instance.user_override:
            raise serializers.ValidationError(f"Cannot alter this field once set.")
        return value

    def save(self, **kwargs):
        try:
            return super().save(**kwargs)
        except django.core.exceptions.ValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)


class DomainSlugRelatedField(serializers.SlugRelatedField):
    def get_queryset(self):
        return self.context["request"].user.domains


class TokenDomainPolicySerializer(serializers.ModelSerializer):
    domain = DomainSlugRelatedField(allow_null=True, slug_field="name")

    class Meta:
        model = models.TokenDomainPolicy
        fields = (
            "id",
            "domain",
            "subname",
            "type",
            "perm_write",
        )
        extra_kwargs = {
            "subname": {"required": True},
            "type": {"required": True},
        }

    def to_internal_value(self, data):
        return {
            **super().to_internal_value(data),
            # TODO may raise Token.DoesNotExist
            "token": self.context["request"].user.token_set.get(
                id=self.context["view"].kwargs["token_id"]
            ),
        }

    def save(self, **kwargs):
        try:
            return super().save(**kwargs)
        except django.core.exceptions.ValidationError as exc:
            raise serializers.ValidationError(exc.message_dict, code="precedence")
