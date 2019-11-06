from django.core.mail import EmailMessage
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import get_template

from desecapi import models


@receiver(post_save, sender=models.Domain, dispatch_uid=__name__)
def domain_handler(sender, instance, created, raw, using, update_fields, **kwargs):
    if instance.is_locally_registrable:
        content_tmpl = get_template('emails/domain-dyndns/content.txt')
        subject_tmpl = get_template('emails/domain-dyndns/subject.txt')
        from_tmpl = get_template('emails/from.txt')
        context = {
            'domain': instance.name,
            'url': f'https://update.{instance.parent_domain_name}/',
            'username': instance.name,
            'password': models.Token.objects.create(user=instance.owner, name='dyndns')
        }
        email = EmailMessage(subject_tmpl.render(context),
                             content_tmpl.render(context),
                             from_tmpl.render(context),
                             [instance.owner.email])
        email.send()
