from rest_framework import serializers
from models import Domain


class DomainSerializer(serializers.ModelSerializer):
    owner = serializers.Field(source='owner.email')

    class Meta:
        model = Domain
        fields = ('id', 'name', 'owner')
