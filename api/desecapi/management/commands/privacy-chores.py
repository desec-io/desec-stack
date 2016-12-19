from django.core.management import BaseCommand
from desecapi.models import User

class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        users = User.objects.filter() # TODO filter for non-empty registration remote ip
        for u in users:
            u.registration_remote_ip = None
            u.save() # TODO bulk update?
