from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from desecapi.models import Domain, Donation, User, RR, RRset
from djoser import serializers as djoserSerializers
from django.db import transaction


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

    def _set_records(self, instance):
        # Although serializer fields have required=True by default, that
        # setting does not work for the SerializerMethodField "records".
        # Thus, let's wrap our read access to include the validation check.
        records = self.context['request'].data.get('records')
        if records is None:
            raise ValidationError({'records': 'This field is required.'},
                                  code='required')

        records_data = [{'content': x} for x in records]
        rr_serializer = RRSerializer(data=records_data, many=True,
                                     allow_empty=False)
        if not rr_serializer.is_valid():
            errors = rr_serializer.errors
            if 'non_field_errors' in errors:
                errors['records'] = errors.pop('non_field_errors')
            raise serializers.ValidationError(errors)
        instance.set_rrs([x['content'] for x in rr_serializer.validated_data])

    @transaction.atomic
    def create(self, validated_data):
        instance = super().create(validated_data)
        self._set_records(instance)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        # Update records only if required (PUT) or provided (PATCH)
        if not self.partial or 'records' in self.context['request'].data:
            instance.records.all().delete()
            self._set_records(instance)
        return instance

    def get_records(self, obj):
        return list(obj.records.values_list('content', flat=True))

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
        fields = ('name', 'owner', 'keys')


class DonationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Donation
        fields = ('name', 'iban', 'bic', 'amount', 'message', 'email')


class UserSerializer(djoserSerializers.UserSerializer):

    class Meta(djoserSerializers.UserSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
        )


class UserCreateSerializer(djoserSerializers.UserCreateSerializer):

    class Meta(djoserSerializers.UserCreateSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            'password',
            'dyn',
        )
