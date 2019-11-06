from django.db.models.signals import post_save
from django.dispatch import receiver

from desecapi import models


@receiver(post_save, sender=models.Domain, dispatch_uid=__name__)
def domain_handler(sender, instance: models.Domain, created, raw, using, update_fields, **kwargs):
    pass
