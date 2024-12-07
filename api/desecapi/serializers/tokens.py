import django.core.exceptions
from netfields.rest_framework import CidrAddressField
from rest_framework import serializers

from desecapi.models import Token, TokenDomainPolicy


class TokenSerializer(serializers.ModelSerializer):
    owner = serializers.SlugRelatedField(slug_field="email", read_only=True)
    user_override = serializers.SlugRelatedField(slug_field="email", read_only=True)
    allowed_subnets = serializers.ListField(child=CidrAddressField(), required=False)
    token = serializers.ReadOnlyField(source="plain")
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = Token
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
            "user_override",
            "token",
        )

    def __init__(self, *args, include_plain=False, **kwargs):
        self.include_plain = include_plain
        super().__init__(*args, **kwargs)

    def get_fields(self):
        fields = super().get_fields()
        if not self.include_plain:
            fields.pop("token")
        return fields

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
        model = TokenDomainPolicy
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
