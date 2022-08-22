from datetime import timedelta

from django import template
from django.conf import settings
from django.urls import reverse

register = template.Library()


@register.simple_tag
def action_link(action_serializer, idx=None):
    view_name = f"v1:confirm-{action_serializer.reason}"
    code = (
        action_serializer.data["code"]
        if idx is None
        else action_serializer.data[idx]["code"]
    )
    return f"https://desec.{settings.DESECSTACK_DOMAIN}" + reverse(
        view_name, args=[code]
    )


@register.simple_tag
def action_link_expiration_hours(action_serializer):
    return action_serializer.validity_period // timedelta(hours=1)
