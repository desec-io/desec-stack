from django.db import DataError
from rest_framework.exceptions import ValidationError
from rest_framework.validators import qs_exists, qs_filter, UniqueTogetherValidator


def qs_exclude(queryset, **kwargs):
    try:
        return queryset.exclude(**kwargs)
    except (TypeError, ValueError, DataError):
        return queryset.none()


class ExclusionConstraintValidator(UniqueTogetherValidator):
    """
    Validator that implements ExclusionConstraints, currently very basic with support for one field only.
    Should be applied to the serializer class, not to an individual field.
    No-op if parent serializer is a list serializer (many=True). We expect the list serializer to assure exclusivity.
    """
    message = 'This field violates an exclusion constraint.'

    def __init__(self, queryset, fields, exclusion_condition, message=None):
        super().__init__(queryset, fields, message)
        self.exclusion_condition = exclusion_condition

    def filter_queryset(self, attrs, queryset, serializer):
        qs = super().filter_queryset(attrs, queryset, serializer)

        # Determine the exclusion filters and prepare the queryset.
        field_name = self.exclusion_condition[0]
        value = self.exclusion_condition[1]
        source = serializer.fields[field_name].source
        if serializer.instance is not None:
            if source not in attrs:
                attrs[source] = getattr(serializer.instance, source)
        exclusion_method = qs_exclude if attrs[source] == value else qs_filter
        return exclusion_method(qs, **{field_name: value})

    def __call__(self, attrs, serializer, *args, **kwargs):
        # Ignore validation if the many flag is set
        if getattr(serializer.root, 'many', False):
            return

        self.enforce_required_fields(attrs, serializer)
        queryset = self.queryset
        queryset = self.filter_queryset(attrs, queryset, serializer)
        queryset = self.exclude_current_instance(attrs, queryset, serializer.instance)

        # Ignore validation if any field is None
        checked_values = [
            value for field, value in attrs.items() if field in self.fields
        ]
        if None not in checked_values and qs_exists(queryset):
            types = queryset.values_list('type', flat=True)
            types = ', '.join(types)
            message = self.message.format(types=types)
            raise ValidationError(message, code='exclusive')
