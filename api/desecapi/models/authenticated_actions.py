from __future__ import annotations

import json
from hashlib import sha256

from django.db import models
from django.utils import timezone

from .domains import Domain


class AuthenticatedAction(models.Model):
    """
    Represents a procedure call on a defined set of arguments.

    Subclasses can define additional arguments by adding Django model fields and must define the action to be taken by
    implementing the `_act` method.

    AuthenticatedAction provides the `state` property which by default is a hash of the action type (defined by the
    action's class path). Other information such as user state can be included in the state hash by (carefully)
    overriding the `_state_fields` property. Instantiation of the model, if given a `state` kwarg, will raise an error
    if the given state argument does not match the state computed from `_state_fields` at the moment of instantiation.
    The same applies to the `act` method: If called on an object that was instantiated without a `state` kwargs, an
    error will be raised.

    This effectively allows hash-authenticated procedure calls by third parties as long as the server-side state is
    unaltered, according to the following protocol:

    (1) Instantiate the AuthenticatedAction subclass representing the action to be taken (no `state` kwarg here),
    (2) provide information on how to instantiate the instance, and the state hash, to a third party,
    (3) when provided with data that allows instantiation and a valid state hash, take the defined action, possibly with
        additional parameters chosen by the third party that do not belong to the verified state.
    """

    _validated = False

    class Meta:
        managed = False

    def __init__(self, *args, **kwargs):
        state = kwargs.pop("state", None)
        super().__init__(*args, **kwargs)

        if state is not None:
            self._validated = self.validate_state(state)
            if not self._validated:
                raise ValueError

    @property
    def _state_fields(self) -> list:
        """
        Returns a list that defines the state of this action (used for authentication of this action).

        Return value must be JSON-serializable.

        Values not included in the return value will not be used for authentication, i.e. those values can be varied
        freely and function as unauthenticated action input parameters.

        Use caution when overriding this method. You will usually want to append a value to the list returned by the
        parent. Overriding the behavior altogether could result in reducing the state to fewer variables, resulting
        in valid signatures when they were intended to be invalid. The suggested method for overriding is

            @property
            def _state_fields:
                return super()._state_fields + [self.important_value, self.another_added_value]

        :return: List of values to be signed.
        """
        name = ".".join([self.__module__, self.__class__.__qualname__])
        return [name]

    @staticmethod
    def state_of(fields: list):
        state = json.dumps(fields).encode()
        h = sha256()
        h.update(state)
        return h.hexdigest()

    @property
    def state(self):
        return self.state_of(self._state_fields)

    def validate_state(self, value):
        return value == self.state

    def _act(self):
        """
        Conduct the action represented by this class.
        :return: None
        """
        raise NotImplementedError

    def act(self):
        if not self._validated:
            raise RuntimeError("Action state could not be verified.")
        return self._act()


class AuthenticatedBasicUserAction(AuthenticatedAction):
    """
    Abstract AuthenticatedAction involving a user instance.
    """

    user = models.ForeignKey("User", on_delete=models.DO_NOTHING)

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [str(self.user.id)]


class AuthenticatedEmailUserAction(AuthenticatedBasicUserAction):
    """
    Abstract AuthenticatedAction involving a user instance with unmodified email address.

    Only child class is now AuthenticatedChangeOutreachPreferenceUserAction. Conceptually, we could
    flatten the Authenticated*Action class hierarchy, but that would break migration 0024 that depends
    on it (see https://docs.djangoproject.com/en/4.1/topics/migrations/#historical-models).
    """

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [self.user.email]


class AuthenticatedChangeOutreachPreferenceUserAction(AuthenticatedEmailUserAction):
    outreach_preference = models.BooleanField(default=False)

    class Meta:
        managed = False

    def _act(self):
        self.user.outreach_preference = self.outreach_preference
        self.user.save()


class AuthenticatedUserAction(AuthenticatedBasicUserAction):
    """
    Abstract AuthenticatedBasicUserAction, incorporating the user's id, email, password, and is_active flag into the
    Message Authentication Code state.
    """

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [
            self.user.credentials_changed.isoformat(),
            self.user.is_active,
        ]


class AuthenticatedActivateUserAction(AuthenticatedUserAction):
    domain = models.CharField(max_length=191)

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [self.domain]

    def _act(self):
        self.user.activate()


class AuthenticatedChangeEmailUserAction(AuthenticatedUserAction):
    new_email = models.EmailField()

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [self.new_email]

    def _act(self):
        self.user.change_email(self.new_email)


class AuthenticatedNoopUserAction(AuthenticatedBasicUserAction):
    class Meta:
        managed = False

    def _act(self):
        pass


class AuthenticatedResetPasswordUserAction(AuthenticatedUserAction):
    new_password = models.CharField(max_length=128)

    class Meta:
        managed = False

    def _act(self):
        self.user.change_password(self.new_password)


class AuthenticatedDeleteUserAction(AuthenticatedUserAction):
    class Meta:
        managed = False

    def _act(self):
        self.user.delete()


class AuthenticatedDomainBasicUserAction(AuthenticatedBasicUserAction):
    """
    Abstract AuthenticatedBasicUserAction involving an domain instance, incorporating the domain's id, name as well as
    the owner ID into the Message Authentication Code state.
    """

    domain = models.ForeignKey("Domain", on_delete=models.DO_NOTHING)

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [
            str(self.domain.id),  # ensures the domain object is identical
            self.domain.name,  # exclude renamed domains
            str(self.domain.owner.id),  # exclude transferred domains
        ]


class AuthenticatedRenewDomainBasicUserAction(AuthenticatedDomainBasicUserAction):
    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [str(self.domain.renewal_changed)]

    def _act(self):
        self.domain.renewal_state = Domain.RenewalState.FRESH
        self.domain.renewal_changed = timezone.now()
        self.domain.save(update_fields=["renewal_state", "renewal_changed"])
