from django.conf import settings
from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)
import requests
import json
import subprocess
import os

class MyUserManager(BaseUserManager):
    def create_user(self, email, password=None):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(email,
                                password=password
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    email = models.EmailField(
        verbose_name='email address',
        max_length=255,
        unique=True,
    )
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = MyUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        # Simplest possible answer: All admins are staff
        return self.is_admin


class Domain(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=255, unique=True)
    arecord = models.CharField(max_length=255, blank=True)
    aaaarecord = models.CharField(max_length=1024, blank=True)
    dyn = models.BooleanField(default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='domains')

    headers = {
        'User-Agent': 'desecapi',
        'X-API-Key': settings.POWERDNS_API_TOKEN,
    }

    def save(self, *args, **kwargs):
        if self.id is None:
            self.pdnsCreate()
        if self.arecord or self.aaaarecord:
            self.pdnsUpdate()
        super(Domain, self).save(*args, **kwargs) # Call the "real" save() method.

    def pdnsCreate(self):
        payload = {
            "name": self.name,
            "kind": "master",
            "masters": [],
            "nameservers": [
                "ns1.desec.io",
                "ns2.desec.io"
            ],
            "soa_edit": "INCREMENT-WEEKS"
        }
        r = requests.post(settings.POWERDNS_API + '/zones', data=json.dumps(payload), headers=self.headers)
        if r.status_code < 200 or r.status_code >= 300:
            raise Exception(r)

        self.postCreateHook()

    def pdnsUpdate(self):
        if self.arecord:
            a = \
                {
                    "records": [
                            {
                                "type": "A",
                                "ttl": 60,
                                "name": self.name,
                                "disabled": False,
                                "content": self.arecord,
                            }
                        ],
                    "changetype": "REPLACE",
                    "type": "A",
                    "name": self.name,
                }
        else:
            a = \
                {
                    "changetype": "DELETE",
                    "type": "A",
                    "name": self.name
                }

        if self.aaaarecord:
            aaaa = \
                {
                    "records": [
                            {
                                "type": "AAAA",
                                "ttl": 60,
                                "name": self.name,
                                "disabled": False,
                                "content": self.aaaarecord,
                            }
                        ],
                    "changetype": "REPLACE",
                    "type": "AAAA",
                    "name": self.name,
                }
        else:
            aaaa = \
                {
                    "changetype": "DELETE",
                    "type": "AAAA",
                    "name": self.name
                }

        payload = { "rrsets": [a, aaaa] }
        r = requests.patch(settings.POWERDNS_API + '/zones/' + self.name, data=json.dumps(payload), headers=self.headers)
        if r.status_code < 200 or r.status_code >= 300:
            raise Exception(r)

        self.postUpdateHook()

    def hook(self, cmd):
        if not self.name:
            raise Exception

        env = os.environ.copy()
        env['APITOKEN'] = settings.POWERDNS_API_TOKEN

        cmd = [cmd, self.name.lower()]
        p_hook = subprocess.Popen(cmd,
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  env=env)
        stdout, stderr = p_hook.communicate()

        if not p_hook.returncode == 0:
            raise Exception((stdout, stderr))

        return

    def postCreateHook(self):
        self.hook(cmd='domain_post_create.sh')

    def postUpdateHook(self):
        self.hook(cmd='domain_post_update.sh')

    class Meta:
        ordering = ('created',)
