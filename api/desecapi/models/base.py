import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


def validate_lower(value):
    if value != value.lower():
        raise ValidationError('Invalid value (not lowercase): %(value)s',
                              code='invalid',
                              params={'value': value})


def validate_upper(value):
    if value != value.upper():
        raise ValidationError('Invalid value (not uppercase): %(value)s',
                              code='invalid',
                              params={'value': value})


validate_domain_name = [
    validate_lower,
    RegexValidator(
        regex=r'^(([a-z0-9_-]{1,63})\.)*[a-z0-9-]{1,63}$',
        message='Domain names must be labels separated by dots. Labels may consist of up to 63 letters, digits, '
                'hyphens, and underscores. The last label may not contain an underscore.',
        code='invalid_domain_name',
        flags=re.IGNORECASE
    )
]
