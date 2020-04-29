import binascii
import json
import re
from base64 import urlsafe_b64decode, urlsafe_b64encode, b64encode

from captcha.image import ImageCaptcha
from django.contrib.auth.password_validation import validate_password
from django.core.validators import MinValueValidator
from django.db import IntegrityError, OperationalError
from django.db.models import Model, Q
from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.validators import UniqueTogetherValidator, UniqueValidator, qs_filter

from api import settings
from desecapi import crypto, metrics, models
from desecapi.exceptions import ConcurrencyException


class CaptchaSerializer(serializers.ModelSerializer):
    challenge = serializers.SerializerMethodField()

    class Meta:
        model = models.Captcha
        fields = ('id', 'challenge') if not settings.DEBUG else ('id', 'challenge', 'content')

    def get_challenge(self, obj: models.Captcha):
        # TODO Does this need to be stored in the object instance, in case this method gets called twice?
        challenge = ImageCaptcha().generate(obj.content).getvalue()
        return b64encode(challenge)


class CaptchaSolutionSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=models.Captcha.objects.all(),
        error_messages={'does_not_exist': 'CAPTCHA does not exist.'}
    )
    solution = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        captcha = attrs['id']  # Note that this already is the Captcha object
        if not captcha.verify(attrs['solution']):
            raise serializers.ValidationError('CAPTCHA could not be validated. Please obtain a new one and try again.')

        return attrs


class TokenSerializer(serializers.ModelSerializer):
    token = serializers.ReadOnlyField(source='plain')

    class Meta:
        model = models.Token
        fields = ('id', 'created', 'last_used', 'name', 'token',)
        read_only_fields = ('id', 'created', 'last_used', 'token')

    def __init__(self, *args, include_plain=False, **kwargs):
        self.include_plain = include_plain
        return super().__init__(*args, **kwargs)

    def get_fields(self):
        fields = super().get_fields()
        if not self.include_plain:
            fields.pop('token')
        return fields


class RequiredOnPartialUpdateCharField(serializers.CharField):
    """
    This field is always required, even for partial updates (e.g. using PATCH).
    """
    def validate_empty_values(self, data):
        if data is serializers.empty:
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
            raise serializers.SkipField()
        if callable(self.default):
            return self.default()
        return self.default

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, repr(self.default))


class RRSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.RR
        fields = ('content',)

    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError('Must be a string.', code='must-be-a-string')
        return super().to_internal_value({'content': data})

    def to_representation(self, instance):
        return instance.content


class RRsetSerializer(ConditionalExistenceModelSerializer):
    domain = serializers.SlugRelatedField(read_only=True, slug_field='name')
    records = RRSerializer(many=True)
    ttl = serializers.IntegerField(max_value=604800)

    class Meta:
        model = models.RRset
        fields = ('created', 'domain', 'subname', 'name', 'records', 'ttl', 'type',)
        extra_kwargs = {
            'subname': {'required': False, 'default': NonBulkOnlyDefault('')}
        }

    def __init__(self, instance=None, data=serializers.empty, domain=None, **kwargs):
        if domain is None:
            raise ValueError('RRsetSerializer() must be given a domain object (to validate uniqueness constraints).')
        self.domain = domain
        super().__init__(instance, data, **kwargs)

    @classmethod
    def many_init(cls, *args, **kwargs):
        domain = kwargs.pop('domain')
        # Note: We are not yet deciding the value of the child's "partial" attribute, as its value depends on whether
        # the RRSet is created (never partial) or not (partial if PATCH), for each given item (RRset) individually.
        kwargs['child'] = cls(domain=domain)
        serializer = RRsetListSerializer(*args, **kwargs)
        metrics.get('desecapi_rrset_list_serializer').inc()
        return serializer

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
        if value in models.RRset.DEAD_TYPES:
            raise serializers.ValidationError(f'The {value} RRset type is currently unsupported.')
        if value in models.RRset.RESTRICTED_TYPES:
            raise serializers.ValidationError(f'You cannot tinker with the {value} RRset.')
        if value.startswith('TYPE'):
            raise serializers.ValidationError('Generic type format is not supported.')
        return value

    def validate_records(self, value):
        # `records` is usually allowed to be empty (for idempotent delete), except for POST requests which are intended
        # for RRset creation only. We use the fact that DRF generic views pass the request in the serializer context.
        request = self.context.get('request')
        if request and request.method == 'POST' and not value:
            raise serializers.ValidationError('This field must not be empty when using POST.')
        return value

    def validate(self, attrs):
        if 'records' in attrs:
            # There is a 12 byte baseline requirement per record, c.f.
            # https://lists.isc.org/pipermail/bind-users/2008-April/070137.html
            # There also seems to be a 32 byte (?) baseline requirement per RRset, plus the qname length, see
            # https://lists.isc.org/pipermail/bind-users/2008-April/070148.html
            # The binary length of the record depends actually on the type, but it's never longer than vanilla len()
            qname = models.RRset.construct_name(attrs.get('subname', ''), self.domain.name)
            conservative_total_length = 32 + len(qname) + sum(12 + len(rr['content']) for rr in attrs['records'])

            # Add some leeway for RRSIG record (really ~110 bytes) and other data we have not thought of
            conservative_total_length += 256

            excess_length = conservative_total_length - 65535  # max response size
            if excess_length > 0:
                raise serializers.ValidationError(f'Total length of RRset exceeds limit by {excess_length} bytes.',
                                                  code='max_length')

        return attrs

    def exists(self, arg):
        if isinstance(arg, models.RRset):
            return arg.records.exists()
        else:
            return bool(arg.get('records')) if 'records' in arg.keys() else True

    def create(self, validated_data):
        rrs_data = validated_data.pop('records')
        rrset = models.RRset.objects.create(**validated_data)
        self._set_all_record_contents(rrset, rrs_data)
        return rrset

    def update(self, instance: models.RRset, validated_data):
        rrs_data = validated_data.pop('records', None)
        if rrs_data is not None:
            self._set_all_record_contents(instance, rrs_data)

        ttl = validated_data.pop('ttl', None)
        if ttl and instance.ttl != ttl:
            instance.ttl = ttl
            instance.save()

        return instance

    @staticmethod
    def _set_all_record_contents(rrset: models.RRset, rrs):
        """
        Updates this RR set's resource records, discarding any old values.

        To do so, two large select queries and one query per changed (added or removed) resource record are needed.

        Changes are saved to the database immediately.

        :param rrset: the RRset at which we overwrite all RRs
        :param rrs: list of RR representations
        """
        record_contents = [rr['content'] for rr in rrs]

        # Remove RRs that we didn't see in the new list
        removed_rrs = rrset.records.exclude(content__in=record_contents)  # one SELECT
        for rr in removed_rrs:
            rr.delete()  # one DELETE query

        # Figure out which entries in record_contents have not changed
        unchanged_rrs = rrset.records.filter(content__in=record_contents)  # one SELECT
        unchanged_content = [unchanged_rr.content for unchanged_rr in unchanged_rrs]
        added_content = filter(lambda c: c not in unchanged_content, record_contents)

        rrs = [models.RR(rrset=rrset, content=content) for content in added_content]
        models.RR.objects.bulk_create(rrs)  # One INSERT


class RRsetListSerializer(serializers.ListSerializer):
    default_error_messages = {
        **serializers.Serializer.default_error_messages,
        **serializers.ListSerializer.default_error_messages,
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
                raise serializers.SkipField()
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
                        'non_field_errors': [
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

        try:
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

        # time of check (does it exist?) and time of action (create vs update) are different,
        # so for parallel requests, we can get integrity errors due to duplicate keys.
        # This will be considered a 429-error, even though re-sending the request will be successful.
        except OperationalError as e:
            try:
                if e.args[0] == 1213:
                    # 1213 is mysql for deadlock, other OperationalErrors are treated elsewhere or not treated at all
                    raise ConcurrencyException from e
            except (AttributeError, KeyError):
                pass
            raise e
        except (IntegrityError, models.RRset.DoesNotExist) as e:
            raise ConcurrencyException from e

        return ret


class DomainSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Domain
        fields = ('created', 'published', 'name', 'keys', 'minimum_ttl',)
        read_only_fields = ('published', 'minimum_ttl',)
        extra_kwargs = {
            'name': {'trim_whitespace': False},
        }

    def __init__(self, *args, include_keys=False, **kwargs):
        self.include_keys = include_keys
        return super().__init__(*args, **kwargs)

    def get_fields(self):
        fields = super().get_fields()
        if not self.include_keys:
            fields.pop('keys')
        fields['name'].validators.append(ReadOnlyOnUpdateValidator())
        return fields

    def validate_name(self, value):
        self.raise_if_domain_unavailable(value, self.context['request'].user)
        return value

    @staticmethod
    def raise_if_domain_unavailable(domain_name: str, user: models.User):
        if not models.Domain.is_registrable(domain_name, user):
            raise serializers.ValidationError(
                'This domain name is unavailable because it is already taken, or disallowed by policy.',
                code='name_unavailable'
            )

    def create(self, validated_data):
        if 'minimum_ttl' not in validated_data and models.Domain(name=validated_data['name']).is_locally_registrable:
            validated_data.update(minimum_ttl=60)
        return super().create(validated_data)


class DonationSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Donation
        fields = ('name', 'iban', 'bic', 'amount', 'message', 'email', 'mref')
        read_only_fields = ('mref',)


    @staticmethod
    def validate_bic(value):
        return re.sub(r'[\s]', '', value)

    @staticmethod
    def validate_iban(value):
        return re.sub(r'[\s]', '', value)


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.User
        fields = ('created', 'email', 'id', 'limit_domains', 'password',)
        extra_kwargs = {
            'password': {
                'write_only': True,  # Do not expose password field
                'allow_null': True,
            }
        }

    def validate_password(self, value):
        if value is not None:
            validate_password(value)
        return value

    def create(self, validated_data):
        return models.User.objects.create_user(**validated_data)


class RegisterAccountSerializer(UserSerializer):
    domain = serializers.CharField(required=False, validators=models.validate_domain_name)
    captcha = CaptchaSolutionSerializer(required=True)

    class Meta:
        model = UserSerializer.Meta.model
        fields = ('email', 'password', 'domain', 'captcha')
        extra_kwargs = UserSerializer.Meta.extra_kwargs

    def validate_domain(self, value):
        DomainSerializer.raise_if_domain_unavailable(value, self.context['request'].user)
        return value

    def create(self, validated_data):
        validated_data.pop('domain', None)
        validated_data.pop('captcha', None)
        return super().create(validated_data)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailPasswordSerializer(EmailSerializer):
    password = serializers.CharField()


class ChangeEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        if value == self.context['request'].user.email:
            raise serializers.ValidationError('Email address unchanged.')
        return value


class ResetPasswordSerializer(EmailSerializer):
    captcha = CaptchaSolutionSerializer(required=True)


class CustomFieldNameUniqueValidator(UniqueValidator):
    """
    Does exactly what rest_framework's UniqueValidator does, however allows to further customize the
    query that is used to determine the uniqueness.
    More specifically, we allow that the field name the value is queried against is passed when initializing
    this validator. (At the time of writing, UniqueValidator insists that the field's name is used for the
    database query field; only how the lookup must match is allowed to be changed.)
    """

    def __init__(self, queryset, message=None, lookup='exact', lookup_field=None):
        self.lookup_field = lookup_field
        super().__init__(queryset, message, lookup)

    def filter_queryset(self, value, queryset, field_name):
        """
        Filter the queryset to all instances matching the given value on the specified lookup field.
        """
        filter_kwargs = {'%s__%s' % (self.lookup_field or field_name, self.lookup): value}
        return qs_filter(queryset, **filter_kwargs)


class AuthenticatedActionSerializer(serializers.ModelSerializer):
    state = serializers.CharField()  # serializer read-write, but model read-only field

    class Meta:
        model = models.AuthenticatedAction
        fields = ('state',)

    @classmethod
    def _pack_code(cls, data):
        payload = json.dumps(data).encode()
        payload_enc = crypto.encrypt(payload, context='desecapi.serializers.AuthenticatedActionSerializer')
        return urlsafe_b64encode(payload_enc).decode()

    @classmethod
    def _unpack_code(cls, code):
        try:
            payload_enc = urlsafe_b64decode(code.encode())
            payload = crypto.decrypt(payload_enc, context='desecapi.serializers.AuthenticatedActionSerializer',
                                     ttl=settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE.total_seconds())
            return json.loads(payload.decode())
        except (TypeError, UnicodeDecodeError, UnicodeEncodeError, json.JSONDecodeError, binascii.Error):
            raise ValueError

    def to_representation(self, instance: models.AuthenticatedUserAction):
        # do the regular business
        data = super().to_representation(instance)

        # encode into single string
        return {'code': self._pack_code(data)}

    def to_internal_value(self, data):
        data = data.copy()  # avoid side effect from .pop
        try:
            # decode from single string
            unpacked_data = self._unpack_code(self.context['code'])
        except KeyError:
            raise serializers.ValidationError({'code': ['This field is required.']})
        except ValueError:
            raise serializers.ValidationError({'code': ['Invalid code.']})

        # add extra fields added by the user
        unpacked_data.update(**data)

        # do the regular business
        return super().to_internal_value(unpacked_data)

    def act(self):
        self.instance.act()
        return self.instance

    def save(self, **kwargs):
        raise ValueError


class AuthenticatedUserActionSerializer(AuthenticatedActionSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=models.User.objects.all(),
        error_messages={'does_not_exist': 'This user does not exist.'},
        pk_field=serializers.UUIDField()
    )

    class Meta:
        model = models.AuthenticatedUserAction
        fields = AuthenticatedActionSerializer.Meta.fields + ('user',)


class AuthenticatedActivateUserActionSerializer(AuthenticatedUserActionSerializer):

    class Meta(AuthenticatedUserActionSerializer.Meta):
        model = models.AuthenticatedActivateUserAction
        fields = AuthenticatedUserActionSerializer.Meta.fields + ('domain',)
        extra_kwargs = {
            'domain': {'default': None, 'allow_null': True}
        }


class AuthenticatedChangeEmailUserActionSerializer(AuthenticatedUserActionSerializer):
    new_email = serializers.EmailField(
        validators=[
            CustomFieldNameUniqueValidator(
                queryset=models.User.objects.all(),
                lookup_field='email',
                message='You already have another account with this email address.',
            )
        ],
        required=True,
    )

    class Meta(AuthenticatedUserActionSerializer.Meta):
        model = models.AuthenticatedChangeEmailUserAction
        fields = AuthenticatedUserActionSerializer.Meta.fields + ('new_email',)


class AuthenticatedResetPasswordUserActionSerializer(AuthenticatedUserActionSerializer):
    new_password = serializers.CharField(write_only=True)

    class Meta(AuthenticatedUserActionSerializer.Meta):
        model = models.AuthenticatedResetPasswordUserAction
        fields = AuthenticatedUserActionSerializer.Meta.fields + ('new_password',)


class AuthenticatedDeleteUserActionSerializer(AuthenticatedUserActionSerializer):

    class Meta(AuthenticatedUserActionSerializer.Meta):
        model = models.AuthenticatedDeleteUserAction
