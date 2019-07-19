import re

from django.core.validators import MinValueValidator
from django.db.models import Model, Q
from djoser import serializers as djoser_serializers
from rest_framework import serializers
from rest_framework.fields import empty, SkipField, ListField, CharField
from rest_framework.serializers import ListSerializer
from rest_framework.settings import api_settings
from rest_framework.validators import UniqueTogetherValidator

from desecapi.models import Domain, Donation, User, RRset, Token, RR


class TokenSerializer(serializers.ModelSerializer):
    value = serializers.ReadOnlyField(source='key')
    # note this overrides the original "id" field, which is the db primary key
    id = serializers.ReadOnlyField(source='user_specific_id')

    class Meta:
        model = Token
        fields = ('id', 'created', 'name', 'value',)
        read_only_fields = ('created', 'value', 'id')


class RequiredOnPartialUpdateCharField(serializers.CharField):
    """
    This field is always required, even for partial updates (e.g. using PATCH).
    """
    def validate_empty_values(self, data):
        if data is empty:
            self.fail('required')

        return super().validate_empty_values(data)


class Validator:

    message = 'This field did not pass validation.'

    def __init__(self, message=None):
        self.field_name = None
        self.message = message or self.message
        self.instance = None

    def __call__(self, value):
        raise NotImplementedError

    def __repr__(self):
        return '<%s>' % self.__class__.__name__


class ReadOnlyOnUpdateValidator(Validator):

    message = 'Can only be written on create.'

    def set_context(self, serializer_field):
        """
        This hook is called by the serializer instance,
        prior to the validation call being made.
        """
        self.field_name = serializer_field.source_attrs[-1]
        self.instance = getattr(serializer_field.parent, 'instance', None)

    def __call__(self, value):
        if isinstance(self.instance, Model) and value != getattr(self.instance, self.field_name):
            raise serializers.ValidationError(self.message, code='read-only-on-update')


class StringField(CharField):

    def to_internal_value(self, data):
        return data

    def run_validation(self, data=empty):
        data = super().run_validation(data)
        if not isinstance(data, str):
            raise serializers.ValidationError('Must be a string.', code='must-be-a-string')
        return data


class RRsField(ListField):

    def __init__(self, **kwargs):
        super().__init__(child=StringField(), **kwargs)

    def to_representation(self, data):
        return [rr.content for rr in data.all()]


class ConditionalExistenceModelSerializer(serializers.ModelSerializer):
    """
    Only considers data with certain condition as existing data.
    If the existence condition does not hold, given instances are deleted, and no new instances are created,
    respectively. Also, to_representation and data will return None.
    Contrary, if the existence condition holds, the behavior is the same as DRF's ModelSerializer.
    """

    def exists(self, arg):
        """
        Determine if arg is to be considered existing.
        :param arg: Either a model instance or (possibly invalid!) data object.
        :return: Whether we treat this as non-existing instance.
        """
        raise NotImplementedError

    def to_representation(self, instance):
        return None if not self.exists(instance) else super().to_representation(instance)

    @property
    def data(self):
        try:
            return super().data
        except TypeError:
            return None

    def save(self, **kwargs):
        validated_data = {}
        validated_data.update(self.validated_data)
        validated_data.update(kwargs)

        known_instance = self.instance is not None
        data_exists = self.exists(validated_data)

        if known_instance and data_exists:
            self.instance = self.update(self.instance, validated_data)
        elif known_instance and not data_exists:
            self.delete()
        elif not known_instance and data_exists:
            self.instance = self.create(validated_data)
        elif not known_instance and not data_exists:
            pass  # nothing to do

        return self.instance

    def delete(self):
        self.instance.delete()


class NonBulkOnlyDefault:
    """
    This class may be used to provide default values that are only used
    for non-bulk operations, but that do not return any value for bulk
    operations.
    Implementation inspired by CreateOnlyDefault.
    """
    def __init__(self, default):
        self.default = default

    def set_context(self, serializer_field):
        # noinspection PyAttributeOutsideInit
        self.is_many = getattr(serializer_field.root, 'many', False)
        if callable(self.default) and hasattr(self.default, 'set_context') and not self.is_many:
            # noinspection PyUnresolvedReferences
            self.default.set_context(serializer_field)

    def __call__(self):
        if self.is_many:
            raise SkipField()
        if callable(self.default):
            return self.default()
        return self.default

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, repr(self.default))


class RRsetSerializer(ConditionalExistenceModelSerializer):
    domain = serializers.SlugRelatedField(read_only=True, slug_field='name')
    records = RRsField(allow_empty=True)
    ttl = serializers.IntegerField(max_value=604800)

    class Meta:
        model = RRset
        fields = ('domain', 'subname', 'name', 'records', 'ttl', 'type',)
        extra_kwargs = {
            'subname': {'required': False, 'default': NonBulkOnlyDefault('')}
        }

    def __init__(self, instance=None, data=empty, domain=None, **kwargs):
        if domain is None:
            raise ValueError('RRsetSerializer() must be given a domain object (to validate uniqueness constraints).')
        self.domain = domain
        super().__init__(instance, data, **kwargs)

    @classmethod
    def many_init(cls, *args, **kwargs):
        domain = kwargs.pop('domain')
        kwargs['child'] = cls(domain=domain)
        return RRsetListSerializer(*args, **kwargs)

    def get_fields(self):
        fields = super().get_fields()
        fields['subname'].validators.append(ReadOnlyOnUpdateValidator())
        fields['type'].validators.append(ReadOnlyOnUpdateValidator())
        fields['ttl'].validators.append(MinValueValidator(limit_value=self.domain.minimum_ttl))
        return fields

    def get_validators(self):
        return [UniqueTogetherValidator(
            self.domain.rrset_set, ('subname', 'type'),
            message='Another RRset with the same subdomain and type exists for this domain.'
        )]

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

    def validate_records(self, value):
        # `records` is usually allowed to be empty (for idempotent delete), except for POST requests which are intended
        # for RRset creation only. We use the fact that DRF generic views pass the request in the serializer context.
        request = self.context.get('request')
        if request and request.method == 'POST' and not value:
            raise serializers.ValidationError('This field must not be empty when using POST.')
        return value

    def exists(self, arg):
        if isinstance(arg, RRset):
            return arg.records.exists()
        else:
            return bool(arg.get('records')) if 'records' in arg.keys() else True

    def create(self, validated_data):
        rrs_data = validated_data.pop('records')
        rrset = RRset.objects.create(**validated_data)
        self._set_all_record_contents(rrset, rrs_data)
        return rrset

    def update(self, instance: RRset, validated_data):
        rrs_data = validated_data.pop('records', None)
        if rrs_data is not None:
            self._set_all_record_contents(instance, rrs_data)

        ttl = validated_data.pop('ttl', None)
        if ttl and instance.ttl != ttl:
            instance.ttl = ttl
            instance.save()

        return instance

    @staticmethod
    def _set_all_record_contents(rrset: RRset, record_contents):
        """
        Updates this RR set's resource records, discarding any old values.

        To do so, two large select queries and one query per changed (added or removed) resource record are needed.

        Changes are saved to the database immediately.

        :param rrset: the RRset at which we overwrite all RRs
        :param record_contents: set of strings
        """
        # Remove RRs that we didn't see in the new list
        removed_rrs = rrset.records.exclude(content__in=record_contents)  # one SELECT
        for rr in removed_rrs:
            rr.delete()  # one DELETE query

        # Figure out which entries in record_contents have not changed
        unchanged_rrs = rrset.records.filter(content__in=record_contents)  # one SELECT
        unchanged_content = [unchanged_rr.content for unchanged_rr in unchanged_rrs]
        added_content = filter(lambda c: c not in unchanged_content, record_contents)

        rrs = [RR(rrset=rrset, content=content) for content in added_content]
        RR.objects.bulk_create(rrs)  # One INSERT


class RRsetListSerializer(ListSerializer):
    default_error_messages = {
        **serializers.Serializer.default_error_messages,
        **ListSerializer.default_error_messages,
        **{'not_a_list': 'Expected a list of items but got {input_type}.'},
    }

    @staticmethod
    def _key(data_item):
        return data_item.get('subname', None), data_item.get('type', None)

    def to_internal_value(self, data):
        if not isinstance(data, list):
            message = self.error_messages['not_a_list'].format(input_type=type(data).__name__)
            raise serializers.ValidationError({api_settings.NON_FIELD_ERRORS_KEY: [message]}, code='not_a_list')

        if not self.allow_empty and len(data) == 0:
            if self.parent and self.partial:
                raise SkipField()
            else:
                self.fail('empty')

        ret = []
        errors = []
        partial = self.partial

        # build look-up objects for instances and data, so we can look them up with their keys
        try:
            known_instances = {(x.subname, x.type): x for x in self.instance}
        except TypeError:  # in case self.instance is None (as during POST)
            known_instances = {}
        indices_by_key = {}
        for idx, item in enumerate(data):
            # Validate item type before using anything from it
            if not isinstance(item, dict):
                self.fail('invalid', datatype=type(item).__name__)
            items = indices_by_key.setdefault(self._key(item), set())
            items.add(idx)

        # Iterate over all rows in the data given
        for idx, item in enumerate(data):
            try:
                # see if other rows have the same key
                if len(indices_by_key[self._key(item)]) > 1:
                    raise serializers.ValidationError({
                        '__all__': [
                            'Same subname and type as in position(s) %s, but must be unique.' %
                            ', '.join(map(str, indices_by_key[self._key(item)] - {idx}))
                        ]
                    })

                # determine if this is a partial update (i.e. PATCH):
                # we allow partial update if a partial update method (i.e. PATCH) is used, as indicated by self.partial,
                # and if this is not actually a create request because it is unknown and nonempty
                unknown = self._key(item) not in known_instances.keys()
                nonempty = item.get('records', None) != []
                self.partial = partial and not (unknown and nonempty)
                self.child.instance = known_instances.get(self._key(item), None)

                # with partial value and instance in place, let the validation begin!
                validated = self.child.run_validation(item)
            except serializers.ValidationError as exc:
                errors.append(exc.detail)
            else:
                ret.append(validated)
                errors.append({})

        self.partial = partial

        if any(errors):
            raise serializers.ValidationError(errors)

        return ret

    def update(self, instance, validated_data):
        """
        Creates, updates and deletes RRsets according to the validated_data given. Relevant instances must be passed as
        a queryset in the `instance` argument.

        RRsets that appear in `instance` are considered "known", other RRsets are considered "unknown". RRsets that
        appear in `validated_data` with records == [] are considered empty, otherwise non-empty.

        The update proceeds as follows:
        1. All unknown, non-empty RRsets are created.
        2. All known, non-empty RRsets are updated.
        3. All known, empty RRsets are deleted.
        4. Unknown, empty RRsets will not cause any action.

        Rationale:
        As both "known"/"unknown" and "empty"/"non-empty" are binary partitions on `everything`, the combination of
        both partitions `everything` in four disjoint subsets. Hence, every RRset in `everything` is taken care of.

                   empty   |  non-empty
        ------- | -------- | -----------
        known   |  delete  |   update
        unknown |  no-op   |   create

        :param instance: QuerySet of relevant RRset objects, i.e. the Django.Model subclass instances. Relevant are all
        instances that are referenced in `validated_data`. If a referenced RRset is missing from instances, it will be
        considered unknown and hence be created. This may cause a database integrity error. If an RRset is given, but
        not relevant (i.e. not referred to by `validated_data`), a ValueError will be raised.
        :param validated_data: List of RRset data objects, i.e. dictionaries.
        :return: List of RRset objects (Django.Model subclass) that have been created or updated.
        """
        def is_empty(data_item):
            return data_item.get('records', None) == []

        query = Q()
        for item in validated_data:
            query |= Q(type=item['type'], subname=item['subname'])  # validation has ensured these fields exist
        instance = instance.filter(query)

        instance_index = {(rrset.subname, rrset.type): rrset for rrset in instance}
        data_index = {self._key(data): data for data in validated_data}

        if data_index.keys() | instance_index.keys() != data_index.keys():
            raise ValueError('Given set of known RRsets (`instance`) is not a subset of RRsets referred to in'
                             '`validated_data`. While this would produce a correct result, this is illegal due to its'
                             ' inefficiency.')

        everything = instance_index.keys() | data_index.keys()
        known = instance_index.keys()
        unknown = everything - known
        # noinspection PyShadowingNames
        empty = {self._key(data) for data in validated_data if is_empty(data)}
        nonempty = everything - empty

        # noinspection PyUnusedLocal
        noop = unknown & empty
        created = unknown & nonempty
        updated = known & nonempty
        deleted = known & empty

        ret = []
        for subname, type_ in created:
            ret.append(self.child.create(
                validated_data=data_index[(subname, type_)]
            ))

        for subname, type_ in updated:
            ret.append(self.child.update(
                instance=instance_index[(subname, type_)],
                validated_data=data_index[(subname, type_)]
            ))

        for subname, type_ in deleted:
            instance_index[(subname, type_)].delete()

        return ret


class DomainSerializer(serializers.ModelSerializer):

    class Meta:
        model = Domain
        fields = ('created', 'published', 'name', 'keys', 'minimum_ttl',)
        extra_kwargs = {
            'name': {'trim_whitespace': False},
            'published': {'read_only': True},
            'minimum_ttl': {'read_only': True},
        }

    def get_fields(self):
        fields = super().get_fields()
        fields['name'].validators.append(ReadOnlyOnUpdateValidator())
        return fields


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
