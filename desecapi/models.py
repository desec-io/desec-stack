from django.conf import settings
from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)
from OpenSSL import crypto


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
    cert_info = models.TextField(blank=True)
    cert_serial_no = models.IntegerField(null=True,blank=True)
    cert_fingerprint = models.CharField(max_length=1024,null=True,blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='domains')

    def save(self, *args, **kwargs):
        if (not self.cert_serial_no and self.cert_info):
            self.updateCertificateData()
        super(Domain, self).save(*args, **kwargs) # Call the "real" save() method.

    def getCertificateObj(self):
        if '--BEGIN CERTIFICATE--' in self.cert_info:
            try:
                return crypto.load_certificate(crypto.FILETYPE_PEM, self.cert_info)
            except:
                return
        return

    def updateCertificateData(self):
        x509 = self.getCertificateObj()
        if x509:
            self.cert_serial_no = x509.get_serial_number()
            self.cert_fingerprint = x509.digest('sha1')

    class Meta:
        ordering = ('created',)
