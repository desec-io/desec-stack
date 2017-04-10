from rest_framework import serializers
from desecapi.models import Domain, Donation, User
from djoser import serializers as djoserSerializers


class DomainSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.email')
    name = serializers.RegexField(regex=r'^[A-Za-z0-9\.\-]+$',trim_whitespace=False)

    class Meta:
        model = Domain
        fields = ('name', 'owner', 'arecord', 'aaaarecord', 'created', 'updated')
        read_only_fields = ('created', 'updated',)


class DonationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Donation
        fields = ('name', 'iban', 'bic', 'amount', 'message', 'email')


class UserSerializer(djoserSerializers.UserSerializer):

    class Meta(djoserSerializers.UserSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
        )


class UserRegistrationSerializer(djoserSerializers.UserRegistrationSerializer):

    class Meta(djoserSerializers.UserRegistrationSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            'password',
        )
