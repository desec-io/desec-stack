import re

import django.core.exceptions
from django.core.validators import RegexValidator
from django.db import models, transaction
from djoser import serializers as djoser_serializers
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty
from rest_framework.settings import api_settings
from rest_framework_bulk import BulkListSerializer, BulkSerializerMixin

from desecapi.models import Domain, Donation, User, RR, RRset, Token


class TokenSerializer(serializers.ModelSerializer):
    value = serializers.ReadOnlyField(source='key')
    # note this overrides the original "id" field, which is the db primary key
    id = serializers.ReadOnlyField(source='user_specific_id')

    class Meta:
        model = Token
        fields = ('id', 'created', 'name', 'value',)
        read_only_fields = ('created', 'value', 'id')


class RRSerializer(serializers.ModelSerializer):
    class Meta:
        model = RR
        fields = ('content',)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            data = {'content': data}
        return super().to_internal_value(data)


class RRsetBulkListSerializer(BulkListSerializer):
    default_error_messages = {'not_a_list': 'Invalid input, expected a list of RRsets.'}

    @transaction.atomic
    def update(self, queryset, validated_data):
        q = models.Q(pk__isnull=True)
        for data in validated_data:
            q |= models.Q(subname=data.get('subname', ''), type=data['type'])
        rrsets = {(obj.subname, obj.type): obj for obj in queryset.filter(q)}
        instance = [rrsets.get((data.get('subname', ''), data['type']), None)
                    for data in validated_data]
        # noinspection PyUnresolvedReferences,PyProtectedMember
        return self.child._save(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data):
        # noinspection PyUnresolvedReferences,PyProtectedMember
        return self.child._save([None] * len(validated_data), validated_data)


class RequiredOnPartialUpdateCharField(serializers.CharField):
    """
    This field is always required, even for partial updates (e.g. using PATCH).
    """
    def validate_empty_values(self, data):
        if data is empty:
            self.fail('required')

        return super().validate_empty_values(data)


class SlugRRField(serializers.SlugRelatedField):
    def __init__(self, *args, **kwargs):
        kwargs['slug_field'] = 'content'
        kwargs['queryset'] = RR.objects.all()
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        return RR(**{self.slug_field: data})


class RRsetSerializer(BulkSerializerMixin, serializers.ModelSerializer):
    domain = serializers.SlugRelatedField(read_only=True, slug_field='name')
    subname = serializers.CharField(
        allow_blank=True,
        required=False,
        validators=[RegexValidator(
            regex=r'^\*?[a-z\.\-_0-9]*$',
            message='Subname can only use (lowercase) a-z, 0-9, ., -, and _.',
            code='invalid_subname'
        )]
    )
    type = RequiredOnPartialUpdateCharField(
        allow_blank=False,
        required=True,
        validators=[RegexValidator(
            regex=r'^[A-Z][A-Z0-9]*$',
            message='Type must be uppercase alphanumeric and start with a letter.',
            code='invalid_type'
        )]
    )
    records = SlugRRField(many=True)

    class Meta:
        model = RRset
        fields = ('id', 'domain', 'subname', 'name', 'records', 'ttl', 'type',)
        list_serializer_class = RRsetBulkListSerializer

    def _save(self, instance, validated_data):
        bulk = isinstance(instance, list)
        if not bulk:
            instance = [instance]
            validated_data = [validated_data]

        name = self.context['view'].kwargs['name']
        domain = self.context['request'].user.domains.get(name=name)
        method = self.context['request'].method

        errors = []
        rrsets = {}
        rrsets_seen = set()
        for rrset, data in zip(instance, validated_data):
            # Construct RRset
            records = data.pop('records', None)
            if rrset:
                # We have a known instance (update). Update fields if given.
                rrset.subname = data.get('subname', rrset.subname)
                rrset.type = data.get('type', rrset.type)
                rrset.ttl = data.get('ttl', rrset.ttl)
            else:
                # No known instance (creation)
                rrset_errors = {}
                if 'ttl' not in data:
                    rrset_errors['ttl'] = ['This field is required for new RRsets.']
                if records is None:
                    rrset_errors['records'] = ['This field is required for new RRsets.']
                if rrset_errors:
                    errors.append(rrset_errors)
                    continue
                data.pop('id', None)
                data['domain'] = domain
                rrset = RRset(**data)

            # Verify that we have not seen this RRset before
            if (rrset.subname, rrset.type) in rrsets_seen:
                errors.append({'__all__': ['RRset repeated with same subname and type.']})
                continue
            rrsets_seen.add((rrset.subname, rrset.type))

            # Validate RRset. Raises error if type or subname have been changed
            # or if new RRset is not unique.
            validate_unique = (method == 'POST')
            try:
                rrset.full_clean(exclude=['updated'],
                                 validate_unique=validate_unique)
            except django.core.exceptions.ValidationError as e:
                errors.append(e.message_dict)
                continue

            # Construct dictionary of RR lists to write, indexed by their RRset
            if records is None:
                rrsets[rrset] = None
            else:
                rr_data = [{'content': x.content} for x in records]

                # Use RRSerializer to validate records inputs
                allow_empty = (method in ('PATCH', 'PUT'))
                rr_serializer = RRSerializer(data=rr_data, many=True,
                                             allow_empty=allow_empty)

                if not rr_serializer.is_valid():
                    error = rr_serializer.errors
                    if api_settings.NON_FIELD_ERRORS_KEY in error:
                        error['records'] = error.pop(api_settings.NON_FIELD_ERRORS_KEY)
                    errors.append(error)
                    continue

                # Blessings have been given, so add RRset to the to-write dict
                rrsets[rrset] = [RR(rrset=rrset, **rr_validated_data)
                                 for rr_validated_data in rr_serializer.validated_data]

            errors.append({})

        if any(errors):
            raise ValidationError(errors if bulk else errors[0])

        # Now try to save RRsets
        try:
            rrsets = domain.write_rrsets(rrsets)
        except django.core.exceptions.ValidationError as e:
            for attr in ['errors', 'error_dict', 'message']:
                detail = getattr(e, attr, None)
                if detail:
                    raise ValidationError(detail)
            raise ValidationError(str(e))
        except ValueError as e:
            raise ValidationError({'__all__': str(e)})

        return rrsets if bulk else rrsets[0]

    @transaction.atomic
    def update(self, instance, validated_data):
        return self._save(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data):
        return self._save(None, validated_data)

    @staticmethod
    def validate_type(value):
        if value in RRset.DEAD_TYPES:
            raise serializers.ValidationError(
                "The %s RRset type is currently unsupported." % value)
        if value in RRset.RESTRICTED_TYPES:
            raise serializers.ValidationError(
                "You cannot tinker with the %s RRset." % value)
        if value.startswith('TYPE'):
            raise serializers.ValidationError(
                "Generic type format is not supported.")
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop('id')
        return data


class DomainSerializer(serializers.ModelSerializer):
    name = serializers.RegexField(regex=r'^[a-z0-9_.-]+$', max_length=191, trim_whitespace=False)

    class Meta:
        model = Domain
        fields = ('created', 'published', 'name', 'keys')


class DonationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Donation
        fields = ('name', 'iban', 'bic', 'amount', 'message', 'email')

    @staticmethod
    def validate_bic(value):
        return re.sub(r'[\s]', '', value)

    @staticmethod
    def validate_iban(value):
        return re.sub(r'[\s]', '', value)


class UserSerializer(djoser_serializers.UserSerializer):
    locked = serializers.SerializerMethodField()

    class Meta(djoser_serializers.UserSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            'dyn',
            'limit_domains',
            'locked',
        )
        read_only_fields = ('dyn', 'limit_domains', 'locked',)

    @staticmethod
    def get_locked(obj):
        return bool(obj.locked)


class UserCreateSerializer(djoser_serializers.UserCreateSerializer):

    class Meta(djoser_serializers.UserCreateSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            'password',
            'dyn',
        )
