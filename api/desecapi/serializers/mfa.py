from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from desecapi.models import BaseFactor, TOTPFactor


class TOTPFactorSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = TOTPFactor
        fields = ("id", "created", "last_used", "name", "secret", "uri", "user")
        read_only_fields = ("id", "created", "last_used", "secret", "uri", "user")
        extra_kwargs = {
            # needed for uniqueness, https://github.com/encode/django-rest-framework/issues/7489
            "name": {"default": ""}
        }
        validators = [
            UniqueTogetherValidator(
                queryset=BaseFactor.objects.all(),
                fields=["user", "name"],
                message="An authentication factor with this name already exists.",
            )
        ]

    def __init__(self, *args, include_secret=False, **kwargs):
        self.include_secret = include_secret
        return super().__init__(*args, **kwargs)

    def get_fields(self):
        fields = super().get_fields()
        if not self.include_secret:
            fields.pop("secret")
            fields.pop("uri")
        return fields

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if "secret" in ret:
            ret["secret"] = instance.base32_secret
        return ret


class TOTPCodeSerializer(serializers.Serializer):
    # length requirements preserve leading zeros
    code = serializers.RegexField("^[0-9]+$", max_length=6, min_length=6)

    class Meta:
        fields = ("code",)

    def validate_code(self, value):
        factor = self.context["view"].get_object()
        if not factor.verify(value):
            raise serializers.ValidationError("Invalid code.")
        return value
