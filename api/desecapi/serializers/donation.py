import re

from rest_framework import serializers

from desecapi import models


class DonationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Donation
        fields = (
            "name",
            "iban",
            "bic",
            "amount",
            "message",
            "email",
            "mref",
            "interval",
        )
        read_only_fields = ("mref",)
        extra_kwargs = {  # do not return sensitive information
            "iban": {"write_only": True},
            "bic": {"write_only": True},
            "message": {"write_only": True},
        }

    @staticmethod
    def validate_bic(value):
        return re.sub(r"\s", "", value)

    @staticmethod
    def validate_iban(value):
        return re.sub(r"\s", "", value)

    def create(self, validated_data):
        return self.Meta.model(**validated_data)
