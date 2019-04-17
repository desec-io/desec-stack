import random
import string

from desecapi.models import Domain, User, Token


class utils(object):
    @classmethod
    def generateRandomIPv4Address(cls):
        return ".".join(map(str, (random.randint(0, 255) for _ in range(4))))

    @classmethod
    def generateRandomString(cls, size=6, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @classmethod
    def generateUsername(cls):
        return cls.generateRandomString() + '@' + cls.generateRandomString() + 'desec.io'

    @classmethod
    def generateDomainname(cls):
        return random.choice(string.ascii_lowercase) + cls.generateRandomString() + '.de'

    @classmethod
    def generateDynDomainname(cls):
        return random.choice(string.ascii_lowercase) + cls.generateRandomString() + '.dedyn.io'

    """
    Creates a new user and saves it to the database.
    The user object is returned.
    """

    @classmethod
    def createUser(cls, username=None, password=None, dyn=False):
        if username is None:
            username = cls.generateUsername()
        user = User(email=username, dyn=dyn)
        user.plainPassword = cls.generateRandomString(size=12) if password is None else password
        user.set_password(user.plainPassword)
        user.save()
        return user

    """
    Creates a new domain and saves it to the database.
    The domain object is returned.
    """

    @classmethod
    def createDomain(cls, owner=None, dyn=False):
        if owner is None:
            owner = cls.createUser(username=None, dyn=False)
        if dyn:
            name = cls.generateDynDomainname()
        else:
            name = cls.generateDomainname()
        domain = Domain(name=name, owner=owner)
        domain.save()
        return domain

    @classmethod
    def createToken(cls, user):
        token = Token.objects.create(user=user)
        token.save();
        return token.key;
