from django.db.models.signals import post_save
from django.dispatch import receiver

from desecapi import models


@receiver(post_save, sender=models.Domain, dispatch_uid=__name__)
def domain_handler(sender, instance: models.Domain, created, raw, using, update_fields, **kwargs):
    if instance.is_locally_registrable:
        instance.owner.send_email('domain-dyndns', context={
            'domain': instance.name,
            'url': f'https://update.{instance.parent_domain_name}/',
            'username': instance.name,
            'password': models.Token.objects.create(user=instance.owner, name='dyndns').plain
        })
