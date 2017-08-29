from rest_framework import serializers
from desecapi.models import Domain, Donation, User, RR, RRset
from djoser import serializers as djoserSerializers


class RRSerializer(serializers.ModelSerializer):
    class Meta:
        model = RR
        fields = ('content',)


class RRsetSerializer(serializers.ModelSerializer):
    domain = serializers.StringRelatedField()
    subname = serializers.CharField(allow_blank=True, required=False)
    type = serializers.CharField(required=False)
    records = serializers.SerializerMethodField()


    class Meta:
        model = RRset
        fields = ('domain', 'subname', 'name', 'records', 'ttl', 'type',)

    def _inject_records_data(self, validated_data):
        records_data = [{'content': x}
                        for x in self.context['request'].data['records']]
        rrs = RRSerializer(data=records_data, many=True, allow_empty=False)
        if not rrs.is_valid():
            errors = rrs.errors
            if 'non_field_errors' in errors:
                errors['records'] = errors.pop('non_field_errors')
            raise serializers.ValidationError(errors)

        return {'records_data': rrs.validated_data, **validated_data}

    def create(self, validated_data):
        validated_data = self._inject_records_data(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._inject_records_data(validated_data)
        return super().update(instance, validated_data)

    def get_records(self, obj):
        return [x for x in obj.records.values_list('content', flat=True)]

    def validate_type(self, value):
        if value in RRset.RESTRICTED_TYPES:
            raise serializers.ValidationError(
                "You cannot tinker with the %s RRset." % value)
        return value


class DomainSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.email')
    name = serializers.RegexField(regex=r'^[A-Za-z0-9_.-]+$', trim_whitespace=False)

    class Meta:
        model = Domain
        fields = ('name', 'owner', 'arecord', 'aaaarecord', 'acme_challenge', 'keys')


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
