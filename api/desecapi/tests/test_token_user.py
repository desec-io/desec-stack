from django.db.utils import IntegrityError, ProgrammingError

from desecapi.models import Token
from desecapi.tests.base import DomainOwnerTestCase


class TokenUserTestCase(DomainOwnerTestCase):
    def _add_default_policies(self, token, additional=True):
        token.tokendomainpolicy_set.create(domain=None, subname=None, type=None)
        if additional:
            token.tokendomainpolicy_set.create(domain=None, subname="sub", type=None)
            token.tokendomainpolicy_set.create(domain=None, subname=None, type="type")
            token.tokendomainpolicy_set.create(domain=None, subname="sub", type="type")

    def _override_user(self, token, user_override):
        token.user_override = user_override
        token.save()
        token.refresh_from_db()

    def _set_properties(self, token, **kwargs):
        for k, v in kwargs.items():
            setattr(token, k, v)

    def _set_properties_then_override_failure(
        self, token, _exc=IntegrityError, **kwargs
    ):
        self._set_properties(token, **kwargs)
        token.save()
        with self.assertRaises(_exc):
            self._override_user(token, self.user)

    def _set_properties_then_save_failure(self, token, _exc=IntegrityError, **kwargs):
        self._set_properties(token, **kwargs)
        with self.assertRaises(_exc):
            token.save()

    def test_change_owner_with_default_policies(self):
        self._add_default_policies(self.token)
        old_owner = self.token.owner
        assert old_owner != self.user
        self.token.owner = self.user
        self.token.save()
        self.token.refresh_from_db()
        self.assertEqual(self.token.owner, self.user)
        self.assertEqual(self.token.user, self.token.owner)

    def test_change_owner_with_domain_policy(self):
        self._add_default_policies(self.token, additional=False)
        self.token.tokendomainpolicy_set.create(
            domain=self.my_domain, subname=None, type=None
        )
        self._set_properties_then_save_failure(self.token, owner=self.user)

    def test_user_override_with_default_policies(self):
        self._add_default_policies(self.token)
        old_owner = self.token.owner
        self._override_user(self.token, self.user)
        self.assertEqual(self.token.owner, old_owner)
        self.assertEqual(self.token.user_override, self.user)
        self.assertEqual(self.token.user, self.token.user_override)
        # Test that TokenDomainPolicy.token_user_id is updated
        self.assertEqual(
            set(self.token.tokendomainpolicy_set.values_list("token_user", flat=True)),
            {self.user.pk},
        )

    def test_user_override_with_domain_policy(self):
        self._add_default_policies(self.token, additional=False)
        self.token.tokendomainpolicy_set.create(
            domain=self.my_domain, subname=None, type=None
        )
        self._set_properties_then_save_failure(self.token, user_override=self.user)

    def test_user_override_from_inception(self):
        token = self.create_token(owner=self.owner, user_override=self.user)
        self.assertEqual(token.owner, self.owner)
        self.assertEqual(token.user_override, self.user)
        self.assertEqual(token.user, self.user)

    def test_user_override_not_owner(self):
        self._set_properties_then_save_failure(
            self.token, user_override=self.token.owner
        )

    def test_user_override_not_manage_tokens(self):
        self._set_properties_then_override_failure(
            self.token, perm_manage_tokens=True, _exc=ValidationError
        )

    def test_user_override_not_login_tokens(self):
        self._set_properties_then_override_failure(self.token, mfa=False)

    def test_user_override_not_mfa_tokens(self):
        self._set_properties_then_override_failure(self.token, mfa=True)

    def test_user_override_only_once(self):
        self._override_user(self.token, self.user)

        self._set_properties_then_save_failure(
            self.token, user_override=self.token.owner
        )
        self._set_properties_then_save_failure(
            self.token, user_override=None, _exc=ProgrammingError
        )

    def test_delete_override_user_deletes_token(self):
        self._override_user(self.token, self.user)
        self.assertEqual(self.token.user_override, self.user)
        self.user.delete()
        with self.assertRaises(Token.DoesNotExist):
            Token.objects.get(pk=self.token.pk)

    def test_delete_owner_deletes_token(self):
        owner = self.create_user()
        token = self.create_token(owner=owner)
        self._override_user(token, self.user)
        self.assertEqual(token.user_override, self.user)
        token.owner.delete()
        with self.assertRaises(Token.DoesNotExist):
            Token.objects.get(pk=token.pk)
