from django.db.utils import IntegrityError, ProgrammingError
from rest_framework import status

from desecapi.models import Token
from desecapi.tests.base import DomainOwnerTestCase


class TokenModelTestCase(DomainOwnerTestCase):
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

    def _set_properties_then_override_failure(self, token, **kwargs):
        self._set_properties(token, **kwargs)
        token.save()
        with self.assertRaises(IntegrityError):
            self._override_user(self.token, self.user)

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
        self._set_properties_then_override_failure(self.token, perm_manage_tokens=True)

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


class TokenViewTestCase(DomainOwnerTestCase):
    def setUp(self):
        super().setUp()
        # Setup tokens. self.owner already has one (self.token)
        # Create one for self.user, and another for self.owner with user_override = self.user
        self.user.token = self.create_token(owner=self.user)
        self.owner.token_with_override = self.create_token(
            owner=self.owner, user_override=self.user
        )

    def test_basics(self):
        self.assertEqual(
            set(self.user.token_set.all()),
            {self.user.token, self.owner.token_with_override},
        )
        self.assertEqual(set(self.owner.token_set.all()), {self.token})

    def test_token_visibility(self):
        # Enable both non-override tokens to inspect the tokens/ endpoint
        for token in [self.token, self.user.token]:
            token.perm_manage_tokens = True
            token.save()

        # Check that self.owner can see their token and the override token
        url_list = self.reverse("v1:token-list")
        url_get = self.reverse("v1:token-detail", pk=self.owner.token_with_override.id)

        response = self.client.get(url_list)  # uses self.token
        self.assertTrue(
            all(token["owner"] == self.owner.email for token in response.data)
        )
        self.assertTrue(any(token["user_override"] is None for token in response.data))
        self.assertTrue(
            any(token["user_override"] == self.user.email for token in response.data)
        )
        self.assertStatus(self.client.get(url_get), status.HTTP_200_OK)

        # Check that self.user can see their token and the override token
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.user.token.plain)
        response = self.client.get(self.reverse("v1:token-list"))
        self.assertTrue(
            any(token["owner"] == self.user.email for token in response.data)
        )
        self.assertTrue(
            any(token["owner"] == self.owner.email for token in response.data)
        )
        self.assertTrue(any(token["user_override"] is None for token in response.data))
        self.assertTrue(
            any(token["user_override"] == self.user.email for token in response.data)
        )
        self.assertStatus(self.client.get(url_get), status.HTTP_200_OK)

        # Only effective user (.user_override, not .owner) may manage override token
        url = self.reverse("v1:token-detail", pk=self.owner.token_with_override.id)
        assert self.user.token.perm_manage_tokens

        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.user.token.plain)
        for method in [self.client.patch, self.client.put]:
            response = method(url, data={"name": "<NAME>"})
            self.assertStatus(response, status.HTTP_200_OK)

        assert self.token.perm_manage_tokens
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.plain)
        for method in [self.client.patch, self.client.put]:
            response = method(url, data={"name": "<NAME>"})
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

    def _delete_token_with_override(self, token):
        token.perm_manage_tokens = True
        token.save()

        override_token = self.create_token(owner=self.owner, user_override=self.user)
        url = self.reverse("v1:token-detail", pk=override_token.id)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.plain)
        response = self.client.delete(url)
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

    def test_delete_token_with_override_owner(self):
        self._delete_token_with_override(self.token)

    def test_delete_token_with_override_user(self):
        self._delete_token_with_override(self.user.token)

    def test_cannot_write_user_fields(self):
        for token in [self.token, self.user.token]:
            token.perm_manage_tokens = True
            token.save()

        url = self.reverse("v1:token-detail", pk=self.owner.token_with_override.id)
        for request_token, expected_status in {
            self.token: status.HTTP_403_FORBIDDEN,  # wrong user
            self.user.token: status.HTTP_200_OK,  # can modify, but field is no-op
            self.owner.token_with_override: status.HTTP_403_FORBIDDEN,  # perm_manage_tokens=False
        }.items():
            self.client.credentials(HTTP_AUTHORIZATION="Token " + request_token.plain)
            for method in [self.client.patch, self.client.put]:
                for field in ["owner", "user", "user_override"]:
                    response = method(url, data={field: self.create_user().email})
                    self.assertStatus(response, expected_status)
                    self.owner.token_with_override.refresh_from_db()
                    self.assertEqual(self.owner.token_with_override.owner, self.owner)
                    self.assertEqual(
                        self.owner.token_with_override.user_override, self.user
                    )
                    self.assertEqual(self.owner.token_with_override.user, self.user)


class TokenDomainTestCase(DomainOwnerTestCase):
    def setUp(self):
        super().setUp()
        # Setup tokens. self.owner already has one (self.token)
        # Create one for self.user, and another for self.owner with user_override = self.user
        self.owner.token_with_override = self.create_token(
            owner=self.owner,
            user_override=self.user,
            auto_policy=True,
            perm_create_domain=True,
        )

    def test_list_domains(self):
        # self.owner has two domains
        # Create one regular domain in self.user, and one through the override token
        domain1 = self.create_domain(owner=self.user)

        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.owner.token_with_override.plain
        )
        name = "foo.com"
        url = self.reverse("v1:domain-list")
        with self.assertRequests(self.requests_desec_domain_creation(name)):
            response = self.client.post(url, {"name": name})
            self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(
            set(self.user.domains.values_list("name", flat=True)),
            {domain1.name, name},
        )

        response = self.client.get(url)
        self.assertEqual(
            set(domain["name"] for domain in response.data),
            {name},
        )

        self.owner.token_with_override.auto_policy = False
        self.owner.token_with_override.save()
        response = self.client.get(url)
        self.assertEqual(
            set(domain["name"] for domain in response.data),
            {domain1.name, name},
        )
