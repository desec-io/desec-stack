import argparse
import sys

from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand
from django.template import engines
from django.template.backends.django import DjangoTemplates
from django.urls import resolve, reverse

from desecapi.models import User


def _get_default_template_backend():
    # Ad-hoc implementation of https://github.com/django/django/pull/15944
    for backend in engines.all():
        if isinstance(backend, DjangoTemplates):
            return backend
    raise ImproperlyConfigured("No DjangoTemplates backend is configured.")


class Command(BaseCommand):
    help = "Reach out to users with an email. Takes email template on stdin."

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            nargs="*",
            help="User(s) to contact, identified by their email addresses. "
            "Defaults to everyone with outreach_preference = True, excluding inactive users.",
        )
        parser.add_argument(
            "--contentfile",
            nargs="?",
            type=argparse.FileType("r"),
            default=sys.stdin,
            help="File to take email content from. Defaults to stdin.",
        )
        parser.add_argument(
            "--reason",
            nargs="?",
            default="change-outreach-preference",
            help="Kind of message to send. Choose from reasons given in serializers.py. Defaults to "
            "newsletter with unsubscribe link (reason: change-outreach-preference).",
        )
        parser.add_argument(
            "--subject",
            nargs="?",
            default=None,
            help='Subject, default according to "reason".',
        )

    def handle(self, *args, **options):
        reason = options["reason"]
        path = reverse(f"v1:confirm-{reason}", args=["code"])
        serializer_class = resolve(path).func.cls.serializer_class

        content = options["contentfile"].read().strip()
        if not content and options["contentfile"].name != "/dev/null":
            raise RuntimeError("Empty content only allowed from /dev/null")

        try:
            subject = "[deSEC] " + options["subject"]
        except TypeError:
            subject = None

        base_file = f"emails/{reason}/content.txt"
        template_code = '{%% extends "%s" %%}' % base_file
        if content:
            template_code += "{% block content %}" + content + "{% endblock %}"
        template = _get_default_template_backend().from_string(template_code)

        if options["email"]:
            users = User.objects.filter(email__in=options["email"])
        elif content:
            users = User.objects.exclude(is_active=False).filter(
                outreach_preference=True
            )
        else:
            raise RuntimeError(
                "To send default content, specify recipients explicitly."
            )

        for user in users:
            action = serializer_class.Meta.model(user=user)
            serializer_class(action).save(subject=subject, template=template)
