from rest_framework import serializers
from desecapi.models import Domain, Donation, User, RRset
from djoser import serializers as djoserSerializers
from rest_framework.exceptions import ValidationError
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


class FromContext(object):
    """
    Callable helper class, useful to extract a value from the view context.

    A common use case is to use such a view context value as a default value
    for populating otherwise read-only fields of a new model instance.

    The class also comes with a specialized method that allows retrieving a
    Domain instance based on a domain name string.
    """
    def __init__(self, value_fn):
        self.value_fn = value_fn

    def set_context(self, serializer_field):
        try:
            self.value = self.value_fn(serializer_field.context)
        except KeyError:
            raise ValidationError("This field is required.")

    def __call__(self):
        return self.value

    @staticmethod
    def get_domain(context):
        domain = Domain.objects.get(name=context['view'].kwargs['name'],
                                    owner=context['request'].user.pk)
        return domain


class GenericRRsetSerializer(serializers.ModelSerializer):
    subname = serializers.CharField(allow_blank=True, required=False)
    type = serializers.CharField(required=False)
    records = RecordsSerializer()


    class Meta:
        model = RRset
        fields = ('domain', 'subname', 'name', 'records', 'ttl', 'type',)


class RRsetSerializer(GenericRRsetSerializer):
    # The domain field is not a user input
    domain = serializers.SlugRelatedField(
        read_only=True, slug_field='name',
        default=FromContext(
            lambda context: FromContext.get_domain(context)
        ))

    # This construction allows us to offer '' as a default for POST, while
    # taking the present value as default on PUT
    subname = serializers.CharField(
        allow_blank=True,
        default=FromContext(
            lambda context: context['request'].data.get('subname', '')
                                if context['request'].method == 'POST'
                                else None
        ))


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
        )
