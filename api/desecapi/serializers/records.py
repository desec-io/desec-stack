import copy

import django.core.exceptions
import dns.name
import dns.zone
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db.models import F, Q
from django.utils import timezone
from netfields.functions import Masklen
from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.validators import UniqueTogetherValidator

from desecapi import metrics, models, validators


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
        return (
            None if not self.exists(instance) else super().to_representation(instance)
        )

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

    requires_context = True

    def __init__(self, default):
        self.default = default

    def __call__(self, serializer_field):
        is_many = getattr(serializer_field.root, "many", False)
        if is_many:
            serializer_field.fail("required")
        if callable(self.default):
            if getattr(self.default, "requires_context", False):
                return self.default(serializer_field)
            else:
                return self.default()
        return self.default

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.default))


class RRSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RR
        fields = ("content",)

    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError(
                "Must be a string.", code="must-be-a-string"
            )
        return super().to_internal_value({"content": data})

    def to_representation(self, instance):
        return instance.content


class RRsetListSerializer(serializers.ListSerializer):
    default_error_messages = {
        **serializers.Serializer.default_error_messages,
        **serializers.ListSerializer.default_error_messages,
        **{"not_a_list": "Expected a list of items but got {input_type}."},
    }

    @staticmethod
    def _key(data_item):
        return data_item.get("subname"), data_item.get("type")

    @staticmethod
    def _types_by_position_string(conflicting_indices_by_type):
        types_by_position = {}
        for type_, conflict_positions in conflicting_indices_by_type.items():
            for position in conflict_positions:
                types_by_position.setdefault(position, []).append(type_)
        # Sort by position, None at the end
        types_by_position = dict(
            sorted(types_by_position.items(), key=lambda x: (x[0] is None, x))
        )
        db_conflicts = types_by_position.pop(None, None)
        if db_conflicts:
            types_by_position["database"] = db_conflicts
        for position, types in types_by_position.items():
            types_by_position[position] = ", ".join(sorted(types))
        types_by_position = [
            f"{position} ({types})" for position, types in types_by_position.items()
        ]
        return ", ".join(types_by_position)

    def to_internal_value(self, data):
        if not isinstance(data, list):
            message = self.error_messages["not_a_list"].format(
                input_type=type(data).__name__
            )
            raise serializers.ValidationError(
                {api_settings.NON_FIELD_ERRORS_KEY: [message]}, code="not_a_list"
            )

        if not self.allow_empty and len(data) == 0:
            if self.parent and self.partial:
                raise serializers.SkipField()
            else:
                self.fail("empty")

        partial = self.partial

        # build look-up objects for instances and data, so we can look them up with their keys
        try:
            known_instances = {(x.subname, x.type): x for x in self.instance}
        except TypeError:  # in case self.instance is None (as during POST)
            known_instances = {}

        errors = [{} for _ in data]
        indices = {}
        for idx, item in enumerate(data):
            # Validate data types before using anything from it
            if not isinstance(item, dict):
                errors[idx].update(
                    {
                        api_settings.NON_FIELD_ERRORS_KEY: f"Expected a dictionary, but got {type(item).__name__}."
                    }
                )
                continue
            s, t = self._key(item)  # subname, type
            if not (isinstance(s, str) or s is None):
                errors[idx].update(
                    subname=f"Expected a string, but got {type(s).__name__}."
                )
            if not (isinstance(t, str) or t is None):
                errors[idx].update(
                    type=f"Expected a string, but got {type(t).__name__}."
                )
            if errors[idx]:
                continue

            # Construct an index of the RRsets in `data` by `s` and `t`. As (subname, type) may be given multiple times
            # (although invalid), we make indices[s][t] a set to properly keep track. We also check and record RRsets
            # which are known in the database (once per subname), using index `None` (for checking CNAME exclusivity).
            if s not in indices:
                types = self.child.domain.rrset_set.filter(subname=s).values_list(
                    "type", flat=True
                )
                indices[s] = {type_: {None} for type_ in types}
            indices[s].setdefault(t, set()).add(idx)

        collapsed_indices = copy.deepcopy(indices)
        for idx, item in enumerate(data):
            if errors[idx]:
                continue
            if item.get("records") == []:
                s, t = self._key(item)
                collapsed_indices[s][t] -= {idx, None}

        # Iterate over all rows in the data given
        ret = []
        for idx, item in enumerate(data):
            if errors[idx]:
                continue
            try:
                # see if other rows have the same key
                s, t = self._key(item)
                data_indices = indices[s][t] - {None}
                if len(data_indices) > 1:
                    raise serializers.ValidationError(
                        {
                            api_settings.NON_FIELD_ERRORS_KEY: [
                                "Same subname and type as in position(s) %s, but must be unique."
                                % ", ".join(map(str, data_indices - {idx}))
                            ]
                        }
                    )

                # see if other rows violate CNAME exclusivity
                if item.get("records") != []:
                    conflicting_indices_by_type = {
                        k: v
                        for k, v in collapsed_indices[s].items()
                        if (k == "CNAME") != (t == "CNAME")
                    }
                    if any(conflicting_indices_by_type.values()):
                        types_by_position = self._types_by_position_string(
                            conflicting_indices_by_type
                        )
                        raise serializers.ValidationError(
                            {
                                api_settings.NON_FIELD_ERRORS_KEY: [
                                    f"RRset with conflicting type present: {types_by_position}."
                                    " (No other RRsets are allowed alongside CNAME.)"
                                ]
                            }
                        )

                # determine if this is a partial update (i.e. PATCH):
                # we allow partial update if a partial update method (i.e. PATCH) is used, as indicated by self.partial,
                # and if this is not actually a create request because it is unknown and nonempty
                unknown = self._key(item) not in known_instances.keys()
                nonempty = item.get("records", None) != []
                self.partial = partial and not (unknown and nonempty)
                self.child.instance = known_instances.get(self._key(item), None)

                # with partial value and instance in place, let the validation begin!
                validated = self.child.run_validation(item)
            except serializers.ValidationError as exc:
                errors[idx].update(exc.detail)
            else:
                ret.append(validated)

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
            return data_item.get("records", None) == []

        query = Q(
            pk__in=[]
        )  # start out with an always empty query, see https://stackoverflow.com/q/35893867/6867099
        for item in validated_data:
            query |= Q(
                type=item["type"], subname=item["subname"]
            )  # validation has ensured these fields exist
        instance = instance.filter(query)

        instance_index = {(rrset.subname, rrset.type): rrset for rrset in instance}
        data_index = {self._key(data): data for data in validated_data}

        if data_index.keys() | instance_index.keys() != data_index.keys():
            raise ValueError(
                "Given set of known RRsets (`instance`) is not a subset of RRsets referred to in"
                " `validated_data`. While this would produce a correct result, this is illegal due to its"
                " inefficiency."
            )

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

        # The above algorithm makes sure that created, updated, and deleted are disjoint. Thus, no "override cases"
        # (such as: an RRset should be updated and delete, what should be applied last?) need to be considered.
        # We apply deletion first to get any possible CNAME exclusivity collisions out of the way.
        for subname, type_ in deleted:
            instance_index[(subname, type_)].delete()

        for subname, type_ in created:
            ret.append(self.child.create(validated_data=data_index[(subname, type_)]))

        for subname, type_ in updated:
            ret.append(
                self.child.update(
                    instance=instance_index[(subname, type_)],
                    validated_data=data_index[(subname, type_)],
                )
            )

        return ret

    def save(self, **kwargs):
        kwargs.setdefault("domain", self.child.domain)
        return super().save(**kwargs)


class RRsetSerializer(ConditionalExistenceModelSerializer):
    domain = serializers.SlugRelatedField(read_only=True, slug_field="name")
    records = RRSerializer(many=True)
    ttl = serializers.IntegerField(max_value=settings.MAXIMUM_TTL)

    class Meta:
        model = models.RRset
        fields = (
            "created",
            "domain",
            "subname",
            "name",
            "records",
            "ttl",
            "type",
            "touched",
        )
        extra_kwargs = {
            "subname": {"required": False, "default": NonBulkOnlyDefault("")}
        }
        list_serializer_class = RRsetListSerializer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.domain = self.context["domain"]
        except KeyError:
            raise ValueError(
                "RRsetSerializer() must be given a domain object (to validate uniqueness constraints)."
            )
        self.minimum_ttl = self.context.get("minimum_ttl", self.domain.minimum_ttl)

    def get_fields(self):
        fields = super().get_fields()
        fields["type"].validators.append(validators.ReadOnlyOnUpdateValidator())
        fields["ttl"].validators.append(MinValueValidator(limit_value=self.minimum_ttl))
        return fields

    def get_validators(self):
        return [
            validators.PermissionValidator(),
            UniqueTogetherValidator(
                self.domain.rrset_set,
                ("subname", "type"),
                message="Another RRset with the same subdomain and type exists for this domain. (Try modifying it.)",
            ),
            validators.ExclusionConstraintValidator(
                self.domain.rrset_set,
                ("subname",),
                exclusion_condition=(
                    "type",
                    "CNAME",
                ),
                message="RRset with conflicting type present: database ({types})."
                " (No other RRsets are allowed alongside CNAME.)",
            ),
        ]

    @staticmethod
    def validate_type(value):
        if value not in models.RR_SET_TYPES_MANAGEABLE:
            # user cannot manage this type, let's try to tell her the reason
            if value in models.RR_SET_TYPES_AUTOMATIC:
                raise serializers.ValidationError(
                    f"You cannot tinker with the {value} RR set. It is managed "
                    f"automatically."
                )
            elif value.startswith("TYPE"):
                raise serializers.ValidationError(
                    "Generic type format is not supported."
                )
            else:
                raise serializers.ValidationError(
                    f"The {value} RR set type is currently unsupported."
                )
        return value

    def validate_records(self, value):
        # `records` is usually allowed to be empty (for idempotent delete), except for POST requests which are intended
        # for RRset creation only. We use the fact that DRF generic views pass the request in the serializer context.
        request = self.context.get("request")
        if request and request.method == "POST" and not value:
            raise serializers.ValidationError(
                "This field must not be empty when using POST."
            )
        return value

    def validate_subname(self, value):
        # Needs to live here (instead of .subname.validators) because `allow_blank`
        # prevents validators from running on subname="" (but this method here runs!)
        if self.instance and value != self.instance.subname:
            raise serializers.ValidationError(
                validators.ReadOnlyOnUpdateValidator.message, code="read-only-on-update"
            )

        try:
            dns.name.from_text(value, dns.name.from_text(self.domain.name))
        except dns.name.NameTooLong:
            raise serializers.ValidationError(
                "This field combined with the domain name must not exceed 255 characters.",
                code="name_too_long",
            )
        return value

    def _validate_canonical_presentation(self, attrs, type_):
        try:
            attrs["records"] = [
                {
                    "content": models.RR.canonical_presentation_format(
                        rr["content"], type_
                    )
                }
                for rr in attrs["records"]
            ]
        except ValueError as ex:
            raise serializers.ValidationError(str(ex))
        return attrs

    def _validate_length(self, attrs):
        # There is a 12 byte baseline requirement per record, c.f.
        # https://lists.isc.org/pipermail/bind-users/2008-April/070137.html
        # There also seems to be a 32 byte (?) baseline requirement per RRset, plus the qname length, see
        # https://lists.isc.org/pipermail/bind-users/2008-April/070148.html
        # The binary length of the record depends actually on the type, but it's never longer than vanilla len()
        qname = models.RRset.construct_name(attrs.get("subname", ""), self.domain.name)
        conservative_total_length = (
            32 + len(qname) + sum(12 + len(rr["content"]) for rr in attrs["records"])
        ) + 256  # some leeway for RRSIG record (really ~110 bytes) and other data we have not thought of

        excess_length = conservative_total_length - 65535  # max response size
        if excess_length > 0:
            metrics.get("desecapi_records_serializer_validate_length").inc()
            raise serializers.ValidationError(
                f"Total length of RRset exceeds limit by {excess_length} bytes.",
                code="max_length",
            )
        return attrs

    def _validate_blocked_content(self, attrs, type_):
        # Reject IP addresses from blocked IP ranges
        if type_ == "A" and self.domain.is_locally_registrable:
            qs = models.BlockedSubnet.objects.values_list("subnet", flat=True).order_by(
                Masklen(F("subnet")).desc()
            )
            for record in attrs["records"]:
                subnet = qs.filter(subnet__net_contains=record["content"]).first()
                if subnet:
                    metrics.get(
                        "desecapi_records_serializer_validate_blocked_subnet"
                    ).labels(str(subnet)).inc()
                    raise serializers.ValidationError(
                        f"IP address {record['content']} not allowed."
                    )
        return attrs

    def validate(self, attrs):
        # on the RRsetDetail endpoint, the type is not in attrs
        type_ = attrs.get("type") or self.instance.type

        if "records" in attrs:
            attrs = self._validate_canonical_presentation(attrs, type_)
            attrs = self._validate_length(attrs)
            attrs = self._validate_blocked_content(attrs, type_)

        # Disallow modification of NS RRsets for locally registrable domains
        # Deletion using records=[] is allowed, except at the apex
        if (
            type_ == "NS"
            and self.domain.is_locally_registrable
            and (
                attrs.get("records", True)
                or not attrs.get("subname", self.instance.subname)
            )
        ):
            raise serializers.ValidationError(
                {"type": ["Cannot modify NS records for this domain."]}
            )

        return attrs

    def exists(self, arg):
        if isinstance(arg, models.RRset):
            return arg.records.exists() if arg.pk else False
        else:
            return bool(arg.get("records")) if "records" in arg.keys() else True

    def create(self, validated_data):
        rrs_data = validated_data.pop("records")
        rrset = models.RRset.objects.create(**validated_data)
        self._set_all_record_contents(rrset, rrs_data)
        return rrset

    def update(self, instance: models.RRset, validated_data):
        rrs_data = validated_data.pop("records", None)
        if rrs_data is not None:
            self._set_all_record_contents(instance, rrs_data)

        ttl = validated_data.pop("ttl", None)
        if ttl and instance.ttl != ttl:
            instance.ttl = ttl
            instance.save()  # also updates instance.touched
        else:
            # Update instance.touched without triggering post-save signal (no pdns action required)
            models.RRset.objects.filter(pk=instance.pk).update(touched=timezone.now())

        return instance

    def save(self, **kwargs):
        kwargs.setdefault("domain", self.domain)
        return super().save(**kwargs)

    @staticmethod
    def _set_all_record_contents(rrset: models.RRset, rrs):
        """
        Updates this RR set's resource records, discarding any old values.

        :param rrset: the RRset at which we overwrite all RRs
        :param rrs: list of RR representations
        """
        record_contents = [rr["content"] for rr in rrs]
        try:
            rrset.save_records(record_contents)
        except django.core.exceptions.ValidationError as e:
            raise serializers.ValidationError(e.messages, code="record-content")
