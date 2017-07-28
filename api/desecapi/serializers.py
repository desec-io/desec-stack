from rest_framework import serializers
from desecapi.models import Domain, Donation, User, RRset
from djoser import serializers as djoserSerializers
import json


class JSONSerializer(serializers.Field):
    def to_representation(self, obj):
        return json.loads(obj)

    def to_internal_value(self, data):
        return json.dumps(data)


class RecordsSerializer(JSONSerializer):
    def to_internal_value(self, records):
        if isinstance(records, str) or not all(isinstance(record, str) for record in records):
            msg = 'Incorrect type. Expected a list of strings'
            raise serializers.ValidationError(msg)

        # https://lists.isc.org/pipermail/bind-users/2008-April/070148.html
        if not len(records) < 4092:
            msg = 'Records too long. Must be less than 4092 characters, but was %d'
            raise serializers.ValidationError(msg % len(records))

        return super().to_internal_value(records)


class GenericRRsetSerializer(serializers.ModelSerializer):
    subname = serializers.CharField(allow_blank=True, required=False)
    type = serializers.CharField(required=False)
    records = RecordsSerializer()


    class Meta:
        model = RRset
        fields = ('domain', 'subname', 'name', 'records', 'ttl', 'type',)


class RRsetSerializer(GenericRRsetSerializer):
    # The value of this field is set in RRsetList.perform_create()
    domain = serializers.SlugRelatedField(read_only=True, slug_field='name')


class DomainSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.email')
    name = serializers.RegexField(regex=r'^[A-Za-z0-9_.-]+$', trim_whitespace=False)

    class Meta:
        model = Domain
        fields = ('name', 'owner', 'arecord', 'aaaarecord', 'created', 'updated', 'acme_challenge')
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
            'dyn',
        )
