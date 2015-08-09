from rest_framework import serializers
from models import Domain


class DomainSerializer(serializers.ModelSerializer):
    owner = serializers.Field(source='owner.email')
    name = serializers.RegexField(regex=r'^[A-Za-z0-9\.\-]+$')

    class Meta:
        model = Domain
        fields = ('id', 'name', 'owner', 'arecord', 'aaaarecord', 'dyn')
