from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from desecapi.models import Domain, Donation, User, RR, RRset, Token
from djoser import serializers as djoserSerializers
from django.db import models, transaction
import django.core.exceptions
from rest_framework_bulk import BulkListSerializer, BulkSerializerMixin
import re
from rest_framework.fields import empty
from rest_framework.settings import api_settings


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
    @transaction.atomic
    def update(self, queryset, validated_data):
        q = models.Q(pk__isnull=True)
        for data in validated_data:
            q |= models.Q(subname=data.get('subname', ''), type=data['type'])
        rrsets = {(obj.subname, obj.type): obj for obj in queryset.filter(q)}
        instance = [rrsets.get((data.get('subname', ''), data['type']), None)
                    for data in validated_data]
        return self.child._save(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data):
        return self.child._save([None] * len(validated_data), validated_data)


class RRsetTypeField(serializers.CharField):
    def validate_empty_values(self, data):
        # The type field is always required, regardless of PATCH or not
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
    domain = serializers.StringRelatedField()
    subname = serializers.CharField(allow_blank=True, required=False)
    type = RRsetTypeField()
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
                # No known instance (creation or meaningless request)
                if not 'ttl' in data:
                    if records:
                        # If we have records, this is a creation request, so we
                        # need a TTL.
                        errors.append({'ttl': ['This field is required for new RRsets.']})
                        continue
                    else:
                        # If this request is meaningless, we still want it to
                        # be processed by pdns for type validation. In this
                        # case, we need some dummy TTL.
                        data['ttl'] = data.get('ttl', 1)
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

    def validate_type(self, value):
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
    name = serializers.RegexField(regex=r'^[A-Za-z0-9_.-]+$', max_length=191, trim_whitespace=False)

    class Meta:
        model = Domain
        fields = ('created', 'published', 'name', 'keys')


class DonationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Donation
        fields = ('name', 'iban', 'bic', 'amount', 'message', 'email')

    def validate_bic(self, value):
        return re.sub(r'[\s]', '', value)

    def validate_iban(self, value):
        return re.sub(r'[\s]', '', value)


class UserSerializer(djoserSerializers.UserSerializer):
    locked = serializers.SerializerMethodField()

    class Meta(djoserSerializers.UserSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            'dyn',
            'limit_domains',
            'locked',
        )
        read_only_fields = ('dyn', 'limit_domains', 'locked',)

    def get_locked(self, obj):
        return bool(obj.locked)


class UserCreateSerializer(djoserSerializers.UserCreateSerializer):

    class Meta(djoserSerializers.UserCreateSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            'password',
            'dyn',
        )
