from django.core.exceptions import ValidationError
from django.db import connection
from django.db.utils import IntegrityError, ProgrammingError
from rest_framework import status

from desecapi.models import Domain, Token, TokenDomainPolicy
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

    def test_token_management_permissions(self):
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
        response = self.client.patch(url, data={"name": "<NAME>"})
        self.assertStatus(response, status.HTTP_200_OK)

        # Cannot change .user_override once set (here, via PUT which sets it to None (default))
        response = self.client.put(url, data={"name": "<NAME>"})
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Cannot alter this field once set.", response.data["user_override"]
        )

        assert self.token.perm_manage_tokens
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.plain)
        for method in [self.client.patch, self.client.put]:
            response = method(url, data={"name": "<NAME>"})
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

    def test_token_policy_permissions(self):
        # Configure a default policy
        TokenDomainPolicy(token=self.owner.token_with_override).save()
        policy_id = self.owner.token_with_override.get_policy().pk

        url = self.reverse(
            "v1:token_domain_policies-list", token_id=self.owner.token_with_override.id
        )
        url_detail = self.reverse(
            "v1:token_domain_policies-detail",
            token_id=self.owner.token_with_override.id,
            pk=policy_id,
        )

        def _assert_policy_request_statuses(list_code, get_patch_put_delete_codes):
            self.assertStatus(self.client.get(url), list_code)
            for (method, data), code in zip(
                (
                    (self.client.get, None),
                    (self.client.patch, None),
                    (self.client.put, {"domain": None, "subname": None, "type": None}),
                    (self.client.delete, None),
                ),
                get_patch_put_delete_codes,
            ):
                self.assertStatus(method(url_detail, data=data), code)

        # Try owner token (no perm_manage_tokens)
        _assert_policy_request_statuses(
            status.HTTP_403_FORBIDDEN,
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
            ),
        )

        # Add perm_manage_tokens
        self.token.perm_manage_tokens = True
        self.token.save()
        _assert_policy_request_statuses(
            status.HTTP_200_OK,
            (
                status.HTTP_200_OK,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
            ),
        )

        # Try target user (no perm_manage_tokens yet)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.user.token.plain)
        _assert_policy_request_statuses(
            status.HTTP_403_FORBIDDEN,
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
            ),
        )

        # Allow target user to manage tokens
        self.user.token.perm_manage_tokens = True
        self.user.token.save()
        _assert_policy_request_statuses(
            status.HTTP_200_OK,
            (
                status.HTTP_200_OK,
                status.HTTP_200_OK,
                status.HTTP_200_OK,
                status.HTTP_204_NO_CONTENT,
            ),
        )

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

    def test_post_user_fields_noop(self):
        assert self.owner.email != self.user.email
        self.token.perm_manage_tokens = True
        self.token.save()

        data = {k: self.user.email for k in ("owner", "user", "user_override")}
        url = self.reverse("v1:token-list")
        response = self.client.post(url, data=data)
        self.assertStatus(response, status.HTTP_202_ACCEPTED)
        self.assertNotIn("user", response.data)
        self.assertEqual(response.data["owner"], self.owner.email)
        self.assertIsNone(response.data["user_override"])

    def test_cannot_modify_perm_manage_tokens(self):
        self.user.token.perm_manage_tokens = True
        self.user.token.save()

        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.user.token.plain)
        url = self.reverse("v1:token-detail", pk=self.owner.token_with_override.id)
        response = self.client.patch(url, data={"perm_manage_tokens": True})
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"],
            ["perm_manage_tokens and user_override are mutually exclusive."],
        )

    def test_cannot_modify_user_fields(self):
        for token in [self.token, self.user.token]:
            token.perm_manage_tokens = True
            token.save()

        url = self.reverse("v1:token-detail", pk=self.owner.token_with_override.id)
        for method in [self.client.patch, self.client.put]:
            for request_token, expected_status in {
                self.token: status.HTTP_403_FORBIDDEN,  # wrong user
                self.user.token: status.HTTP_200_OK,  # has permission but no-op
                self.owner.token_with_override: status.HTTP_403_FORBIDDEN,  # perm_manage_tokens=False
            }.items():
                self.client.credentials(
                    HTTP_AUTHORIZATION="Token " + request_token.plain
                )
                for field in ["owner", "user"]:
                    response = method(
                        url,
                        data={
                            field: self.create_user().email,
                            "user_override": self.owner.token_with_override.user_override.email,
                        },
                    )
                    self.assertStatus(response, expected_status)
                    self.owner.token_with_override.refresh_from_db()
                    self.assertEqual(self.owner.token_with_override.owner, self.owner)
                    self.assertEqual(
                        self.owner.token_with_override.user_override, self.user
                    )
                    self.assertEqual(self.owner.token_with_override.user, self.user)
            for request_token, expected_status in {
                self.token: status.HTTP_403_FORBIDDEN,  # wrong user
                self.user.token: status.HTTP_400_BAD_REQUEST,  # has permission
                self.owner.token_with_override: status.HTTP_403_FORBIDDEN,  # perm_manage_tokens=False
            }.items():
                self.client.credentials(
                    HTTP_AUTHORIZATION="Token " + request_token.plain
                )
                response = method(url, data={"user_override": self.create_user().email})
                self.assertStatus(response, expected_status)


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
            perm_delete_domain=True,
        )

    def test_domain_permissions(self):
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
        domain2 = Domain.objects.get(name=name)

        # Cannot see/delete other domain because token has policies
        response = self.client.get(url)
        self.assertEqual(
            set(domain["name"] for domain in response.data),
            {name},
        )
        url = self.reverse("v1:domain-detail", name=domain1.name)
        response = self.client.delete(url)
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.user.domains.filter(name=domain1.name).exists())

        # GET
        url = self.reverse("v1:domain-detail", name=name)
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=name)
        ):
            response = self.client.get(url)
            self.assertStatus(response, status.HTTP_200_OK)

        # Can't directly PATCH/PUT domain
        for method in [self.client.patch, self.client.put]:
            response = method(url, response.data)
            self.assertStatus(response, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Create RRset
        data = {"subname": "", "type": "A", "ttl": 86400, "records": ["1.2.3.4"]}
        with self.assertRequests(self.requests_desec_rr_sets_update(name=name)):
            response = self.client.post_rr_set(domain_name=name, **data)
            self.assertStatus(response, status.HTTP_201_CREATED)

        # Modify RRset
        with self.assertRequests(self.requests_desec_rr_sets_update(name=name)):
            response = self.client.patch_rr_set(
                name, "", "A", data={"records": ["4.3.2.1"]}
            )
            self.assertStatus(response, status.HTTP_200_OK)
        with self.assertRequests(self.requests_desec_rr_sets_update(name=name)):
            response = self.client.put_rr_set(name, "", "A", data=data)
            self.assertStatus(response, status.HTTP_200_OK)

        # Delete RRset
        with self.assertRequests(self.requests_desec_rr_sets_update(name=name)):
            response = self.client.delete_rr_set(name, subname="", type_="A")
            self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        # Can see other domain when configured even with perm_write=False
        TokenDomainPolicy(
            token=self.owner.token_with_override, domain=domain1, perm_write=False
        ).save()
        url = self.reverse("v1:domain-list")
        response = self.client.get(url)
        self.assertEqual(
            set(domain["name"] for domain in response.data),
            {domain1.name, name},
        )

        # Can see other domain when policies are removed
        self.owner.token_with_override.auto_policy = False
        self.owner.token_with_override.save()
        connection.check_constraints()  # simulate transaction commit
        self.owner.token_with_override.tokendomainpolicy_set.all().delete()
        url = self.reverse("v1:domain-list")
        response = self.client.get(url)
        self.assertEqual(
            set(domain["name"] for domain in response.data),
            {domain1.name, name},
        )

        # Delete domain
        url = self.reverse("v1:domain-detail", name=name)
        with self.assertRequests(self.requests_desec_domain_deletion(domain2)):
            response = self.client.delete(url)
            self.assertStatus(response, status.HTTP_204_NO_CONTENT)

    def test_domain_lifecycle(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.owner.token_with_override.plain
        )
