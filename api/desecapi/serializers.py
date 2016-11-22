from rest_framework import serializers
from desecapi.models import Domain, Donation

class DomainSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.email')
    name = serializers.RegexField(regex=r'^[A-Za-z0-9\.\-]+$')

    class Meta:
        model = Domain
        fields = ('id', 'name', 'owner', 'arecord', 'aaaarecord', 'dyn')

class DonationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Donation
        fields = ('name', 'iban', 'bic', 'amount', 'message', 'email')
