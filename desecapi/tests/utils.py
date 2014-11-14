import random
import string

from rest_framework.authtoken.models import Token
from desecapi.models import Domain, User


class utils(object):
    @classmethod
    def generateRandomString(cls, size=6, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @classmethod
    def generateUsername(cls):
        return cls.generateRandomString() + '@desec.io'

    @classmethod
    def generateDomainname(cls):
        return random.choice(string.ascii_lowercase) + cls.generateRandomString() + '.de'

    """
    Creates a new user and saves it to the database.
    The user object is returned.
    """

    @classmethod
    def createUser(cls, username=None):
        if username is None:
            username = cls.generateUsername()
        user = User(email=username)
        user.plainPassword = cls.generateRandomString(size=12)
        user.set_password(user.plainPassword)
        user.save()
        return user

    """
    Creates a new domain and saves it to the database.
    The domain object is returned.
    """

    @classmethod
    def createDomain(cls, owner=None):
        if owner is None:
            owner = cls.createUser(username=None)
        domain = Domain(name=cls.generateDomainname(), owner=owner)
        domain.save()
        return domain

    @classmethod
    def createToken(cls, user):
        token = Token.objects.create(user=user)
        token.save();
        return token.key;
