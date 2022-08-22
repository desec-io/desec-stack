from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import get_template
from rest_framework import generics

from desecapi.serializers import DonationSerializer


class DonationList(generics.CreateAPIView):
    serializer_class = DonationSerializer

    def perform_create(self, serializer):
        instance = serializer.save()

        context = {
            'donation': instance,
            'creditoridentifier': settings.SEPA['CREDITOR_ID'],
            'creditorname': settings.SEPA['CREDITOR_NAME'],
        }

        # internal desec notification
        content_tmpl = get_template('emails/donation/desec-content.txt')
        subject_tmpl = get_template('emails/donation/desec-subject.txt')
        attachment_tmpl = get_template('emails/donation/desec-attachment-jameica.txt')
        from_tmpl = get_template('emails/from.txt')
        email = EmailMessage(subject_tmpl.render(context),
                             content_tmpl.render(context),
                             from_tmpl.render(context),
                             [settings.DEFAULT_FROM_EMAIL],
                             attachments=[('jameica-directdebit.xml', attachment_tmpl.render(context), 'text/xml')],
                             reply_to=[instance.email] if instance.email else None
                             )
        email.send()

        # donor notification
        if instance.email:
            content_tmpl = get_template('emails/donation/donor-content.txt')
            subject_tmpl = get_template('emails/donation/donor-subject.txt')
            email = EmailMessage(subject_tmpl.render(context),
                                 content_tmpl.render(context),
                                 from_tmpl.render(context),
                                 [instance.email])
            email.send()
