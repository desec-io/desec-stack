from rest_framework import serializers
from models import Domain


class DomainSerializer(serializers.ModelSerializer):
    owner = serializers.Field(source='owner.email')
    cert_serial_no = serializers.Field(source='cert_serial_no')
    cert_fingerprint = serializers.Field(source='cert_fingerprint')

    class Meta:
        model = Domain
        fields = ('id', 'name', 'owner', 'cert_info', 'cert_serial_no', 'cert_fingerprint')
