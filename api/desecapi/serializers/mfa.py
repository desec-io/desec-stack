from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from desecapi.models import BaseFactor, TOTPFactor


class TOTPFactorSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = TOTPFactor
        fields = ("id", "created", "last_used", "name", "secret", "user")
        read_only_fields = ("id", "created", "last_used", "secret", "user")
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
        return fields

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if "secret" in ret:
            ret["secret"] = instance.base32_secret
        return ret
