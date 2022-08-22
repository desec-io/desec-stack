from base64 import b64encode

from captcha.audio import AudioCaptcha
from captcha.image import ImageCaptcha
from rest_framework import serializers

from api import settings
from desecapi.models import Captcha


class CaptchaSerializer(serializers.ModelSerializer):
    challenge = serializers.SerializerMethodField()

    class Meta:
        model = Captcha
        fields = (
            ("id", "challenge", "kind")
            if not settings.DEBUG
            else ("id", "challenge", "kind", "content")
        )

    def get_challenge(self, obj: Captcha):
        # TODO Does this need to be stored in the object instance, in case this method gets called twice?
        if obj.kind == Captcha.Kind.IMAGE:
            challenge = ImageCaptcha().generate(obj.content).getvalue()
        elif obj.kind == Captcha.Kind.AUDIO:
            challenge = AudioCaptcha().generate(obj.content)
        else:
            raise ValueError(f"Unknown captcha type {obj.kind}")
        return b64encode(challenge)


class CaptchaSolutionSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Captcha.objects.all(),
        error_messages={"does_not_exist": "CAPTCHA does not exist."},
    )
    solution = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        captcha = attrs["id"]  # Note that this already is the Captcha object
        if not captcha.verify(attrs["solution"]):
            raise serializers.ValidationError(
                "CAPTCHA could not be validated. Please obtain a new one and try again."
            )

        return attrs
