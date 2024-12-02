from django.db import connection, transaction
from django.db.utils import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient

from desecapi import models
from desecapi.tests.base import DomainOwnerTestCase


class TokenDomainPolicyClient(APIClient):
    def _request(self, method, url, *, using, **kwargs):
        if using is not None:
            kwargs.update(HTTP_AUTHORIZATION=f"Token {using.plain}")
        return method(url, **kwargs)

    def _request_policy(self, method, target, *, using, policy_id, **kwargs):
        url = DomainOwnerTestCase.reverse(
            "v1:token_domain_policies-detail", token_id=target.id, pk=policy_id
        )
        return self._request(method, url, using=using, **kwargs)

    def _request_policies(self, method, target, *, using, **kwargs):
        url = DomainOwnerTestCase.reverse(
            "v1:token_domain_policies-list", token_id=target.id
        )
        return self._request(method, url, using=using, **kwargs)

    def list_policies(self, target, *, using):
        return self._request_policies(self.get, target, using=using)

    def create_policy(self, target, *, using, **kwargs):
        return self._request_policies(self.post, target, using=using, **kwargs)

    def get_policy(self, target, *, using, policy_id):
        return self._request_policy(self.get, target, using=using, policy_id=policy_id)

    def patch_policy(self, target, *, using, policy_id, **kwargs):
        return self._request_policy(
            self.patch, target, using=using, policy_id=policy_id, **kwargs
        )

    def delete_policy(self, target, *, using, policy_id):
        return self._request_policy(
            self.delete, target, using=using, policy_id=policy_id
        )


class TokenDomainPolicyTestCase(DomainOwnerTestCase):
    client_class = TokenDomainPolicyClient
    default_data = dict(perm_write=False)

    def setUp(self):
        super().setUp()
        self.client.credentials()  # remove default credential (corresponding to domain owner)
        self.token_manage = self.create_token(self.owner, perm_manage_tokens=True)
        self.other_token = self.create_token(self.user)

    def test_get_policy(self):
        def get_policy(domain, subname, type):
            return self.token.get_policy(
                models.RRset(domain=domain, subname=subname, type=type)
            )

        def assertPolicy(policy, domain, subname, type):
            self.assertEqual(policy.domain, domain)
            self.assertEqual(policy.subname, subname)
            self.assertEqual(policy.type, type)

        qs = self.token.tokendomainpolicy_set

        # Default policy is fallback for everything
        qs.create(domain=None, subname=None, type=None)
        for kwargs in [
            dict(subname=subname, type=type_)
            for subname in (None, "www")
            for type_ in (None, "A")
        ]:
            policy = get_policy(self.my_domain, **kwargs)
            assertPolicy(policy, None, None, None)

        # Type wins over default
        qs.create(domain=None, subname=None, type="A")
        policy = get_policy(self.my_domain, "www", "A")
        assertPolicy(policy, None, None, "A")

        # Subname wins over type
        qs.create(domain=None, subname="www", type=None)
        policy = get_policy(self.my_domain, "www", "A")
        assertPolicy(policy, None, "www", None)

        # Most specific wins
        qs.create(domain=None, subname="www", type="A")
        policy = get_policy(self.my_domain, "www", "A")
        assertPolicy(policy, None, "www", "A")

        # Domain wins over default and over subname and type
        qs.create(domain=self.my_domain, subname=None, type=None)
        policy = get_policy(self.my_domain, None, None)
        assertPolicy(policy, self.my_domain, None, None)

        # Subname wins over default or domain default
        qs.create(domain=self.my_domain, subname="www", type=None)
        for kwargs in [
            dict(subname="www", type=None),
            dict(subname="www", type="A"),
        ]:
            policy = get_policy(self.my_domain, **kwargs)
            assertPolicy(policy, self.my_domain, "www", None)

        # Type wins over default or domain default
        qs.create(domain=self.my_domain, subname=None, type="A")
        for kwargs in [
            dict(subname=None, type="A"),
            dict(subname="www2", type="A"),
        ]:
            policy = get_policy(self.my_domain, **kwargs)
            assertPolicy(policy, self.my_domain, None, "A")

        # Subname wins over type
        policy = get_policy(self.my_domain, "www", "A")
        assertPolicy(policy, self.my_domain, "www", None)

        # Subname + type wins over less specific
        qs.create(domain=self.my_domain, subname="www", type="A")
        policy = get_policy(self.my_domain, "www", "A")
        assertPolicy(policy, self.my_domain, "www", "A")

        # Check that we did all combinations
        self.assertEqual(qs.count(), 2**3)

    def test_policy_lifecycle_without_management_permission(self):
        # Prepare (with management token)
        data = {"domain": None, "subname": None, "type": None, "perm_write": True}
        response = self.client.create_policy(
            self.token, using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_201_CREATED)
        response = self.client.create_policy(
            self.token_manage, using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_201_CREATED)

        # Self-inspection is fine
        ## List
        response = self.client.list_policies(self.token, using=self.token)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        default_policy_id = response.data[0]["id"]

        ## Get
        response = self.client.get_policy(
            self.token, using=self.token, policy_id=default_policy_id
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(
            response.data, self.default_data | data | {"id": default_policy_id}
        )

        # Inspection of other tokens forbidden
        ## List
        response = self.client.list_policies(self.token_manage, using=self.token)
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)

        ## Get
        response = self.client.get_policy(
            self.token_manage, using=self.token, policy_id=default_policy_id
        )
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)

        # Write operations forbidden (self and other)
        for target in [self.token, self.token_manage]:
            # Create
            response = self.client.create_policy(target, using=self.token)
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

            # Change
            data = dict(perm_write=True)
            policy = target.get_policy()
            response = self.client.patch_policy(
                target, using=self.token, policy_id=policy.pk, data=data
            )
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

            # Delete
            response = self.client.delete_policy(
                target, using=self.token, policy_id=default_policy_id
            )
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

    def test_policy_lifecycle(self):
        # Can't do anything unauthorized
        response = self.client.list_policies(self.token, using=None)
        self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)

        response = self.client.create_policy(self.token, using=None)
        self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)

        # Create
        ## without required field
        response = self.client.create_policy(self.token, using=self.token_manage)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        for field in ["domain", "subname", "type"]:
            self.assertEqual(response.data[field], ["This field is required."])

        ## without a default policy
        data = {"domain": self.my_domains[0].name, "subname": None, "type": None}
        with transaction.atomic():
            response = self.client.create_policy(
                self.token, using=self.token_manage, data=data
            )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"],
            ["Policy precedence: The first policy must be the default policy."],
        )

        # List: still empty
        response = self.client.list_policies(self.token, using=self.token_manage)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

        # Other token gives 404
        other_token = self.create_token(user=self.create_user())
        response = self.client.list_policies(other_token, using=self.token_manage)
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

        # Create
        ## default policy
        data = {"domain": None, "subname": None, "type": None, "perm_write": True}
        # Other token gives 404
        response = self.client.create_policy(
            models.Token(), using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)
        # Existing token works
        response = self.client.create_policy(
            self.token, using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_201_CREATED)
        default_policy_id = response.data["id"]

        ## can't create another default policy
        with transaction.atomic():
            response = self.client.create_policy(
                self.token,
                using=self.token_manage,
                data={"domain": None, "subname": None, "type": None},
            )
        self.assertStatus(response, status.HTTP_409_CONFLICT)

        ## verify object creation
        response = self.client.get_policy(
            self.token, using=self.token_manage, policy_id=default_policy_id
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(
            response.data, self.default_data | data | {"id": default_policy_id}
        )

        ## Non-existing policy gives 404
        response = self.client.get_policy(
            self.token, using=self.token_manage, policy_id=other_token.pk
        )
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

        ## can't create policy for other user's domain
        data = {
            "domain": self.other_domain.name,
            "subname": None,
            "type": None,
            "perm_dyndns": True,
            "perm_write": True,
        }
        response = self.client.create_policy(
            self.token, using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["domain"][0].code, "does_not_exist")

        ## another policy
        data = {
            "domain": self.my_domains[0].name,
            "subname": None,
            "type": None,
        }
        response = self.client.create_policy(
            self.token, using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_201_CREATED)
        policy_id = response.data["id"]

        ## can't create policy for the same domain
        with transaction.atomic():
            response = self.client.create_policy(
                self.token, using=self.token_manage, data=data
            )
        self.assertStatus(response, status.HTTP_409_CONFLICT)

        ## verify object creation
        response = self.client.get_policy(
            self.token, using=self.token_manage, policy_id=policy_id
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data | {"id": policy_id})

        # List: now has two elements
        response = self.client.list_policies(self.token, using=self.token_manage)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Change
        ## all fields of a policy
        data = dict(
            domain=self.my_domains[1].name,
            subname="_acme-challenge",
            type="TXT",
            perm_write=True,
        )
        response = self.client.patch_policy(
            self.token,
            using=self.token_manage,
            policy_id=policy_id,
            data=data,
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data | {"id": policy_id})

        ## verify modification
        response = self.client.get_policy(
            self.token, using=self.token_manage, policy_id=policy_id
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data | {"id": policy_id})

        ## verify that the default policy can't be changed to a non-default policy
        with transaction.atomic():
            response = self.client.patch_policy(
                self.token,
                using=self.token_manage,
                policy_id=default_policy_id,
                data=data,
            )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"],
            ["When using policies, there must be exactly one default policy."],
        )

        ## partially modify the default policy
        data = dict()
        response = self.client.patch_policy(
            self.token, using=self.token_manage, policy_id=default_policy_id, data=data
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "id": default_policy_id,
                "domain": None,
                "subname": None,
                "type": None,
                "perm_write": True,
            }
            | data,
        )

        # Delete
        ## can't delete default policy while others exist
        with transaction.atomic():
            response = self.client.delete_policy(
                self.token, using=self.token_manage, policy_id=default_policy_id
            )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"],
            ["Policy precedence: Can't delete default policy when there exist others."],
        )

        ## delete other policy
        response = self.client.delete_policy(
            self.token, using=self.token_manage, policy_id=policy_id
        )
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        ## delete default policy
        response = self.client.delete_policy(
            self.token, using=self.token_manage, policy_id=default_policy_id
        )
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        ## idempotence: delete a non-existing policy
        response = self.client.delete_policy(
            self.token, using=self.token_manage, policy_id=policy_id
        )
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        ## verify that policies are gone
        for pid in [policy_id, default_policy_id]:
            response = self.client.get_policy(
                self.token, using=self.token_manage, policy_id=pid
            )
            self.assertStatus(response, status.HTTP_404_NOT_FOUND)

        # List: empty again
        response = self.client.list_policies(self.token, using=self.token_manage)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_policy_permissions(self):
        def _reset_policies(token):
            for policy in token.tokendomainpolicy_set.all():
                for perm in self.default_data.keys():
                    setattr(policy, perm, False)
                policy.save()

        # Create
        ## default policy
        data = {"domain": None, "subname": None, "type": None}
        response = self.client.create_policy(
            self.token, using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_201_CREATED)
        default_policy_id = response.data["id"]

        ## another policy
        data = {"domain": self.my_domains[0].name, "subname": None, "type": None}
        response = self.client.create_policy(
            self.token, using=self.token_manage, data=data
        )
        self.assertStatus(response, status.HTTP_201_CREATED)
        policy_id = response.data["id"]

        ## verify object creation
        response = self.client.get_policy(
            self.token, using=self.token_manage, policy_id=policy_id
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data | {"id": policy_id})

        policy_id_by_domain = {
            self.my_domains[0]: policy_id,
            self.my_domains[1]: default_policy_id,
        }

        kwargs = dict(HTTP_AUTHORIZATION=f"Token {self.token.plain}")

        # For each permission type
        for perm in self.default_data.keys():
            # For the domain with specific policy and for the domain covered by the default policy
            for domain in policy_id_by_domain.keys():
                # For both possible values of the permission
                for value in [True, False]:
                    # Set only that permission for that domain (on its effective policy)
                    _reset_policies(self.token)
                    policy = self.token.tokendomainpolicy_set.get(
                        pk=policy_id_by_domain[domain]
                    )
                    setattr(policy, perm, value)
                    policy.save()

                    # Can't access account details
                    response = self.client.get(self.reverse("v1:account"), **kwargs)
                    self.assertStatus(response, status.HTTP_403_FORBIDDEN)

    def test_dyndns_permission(self):
        def _perform_request(**kwargs):
            return self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "username": self.my_domains[1].name,
                    "password": self.token.plain,
                    **kwargs,
                },
            )

        def assert_allowed(**kwargs):
            response = _perform_request(**kwargs)
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, "good")

        def assert_forbidden(**kwargs):
            response = _perform_request(**kwargs)
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)
            self.assertEqual(response.data["detail"], "Insufficient token permissions.")

        # No policy
        assert_allowed(
            myipv4=""
        )  # empty IPv4 and delete IPv6 (no-op, prevents pdns request)

        # Default policy (deny)
        qs = self.token.tokendomainpolicy_set
        qs.create(domain=None, subname=None, type=None)
        assert_forbidden(myipv4="")
        assert_allowed(
            myipv4="preserve", myipv6="preserve"
        )  # no-op needs no permissions

        # Only A permission
        qs.create(domain=self.my_domains[1], subname=None, type="A", perm_write=True)
        assert_forbidden(myipv4="")
        assert_allowed(myipv4="", myipv6="preserve")  # just IPv4

        # Only A permission
        qs.create(domain=self.my_domains[1], subname=None, type="AAAA")
        assert_forbidden(myipv4="")
        assert_allowed(myipv4="", myipv6="preserve")  # just IPv4

        # A + AAAA permission
        qs.filter(domain=self.my_domains[1], type="AAAA").update(perm_write=True)
        assert_allowed(myipv4="")  # empty IPv4 and delete IPv6

        # Only AAAA permission
        qs.filter(domain=self.my_domains[1], type="A").update(perm_write=False)
        assert_forbidden(myipv4="")
        assert_allowed(myipv4="preserve", myipv6="")  # just IPv6

        # Update default policy to allow, but A deny policy overrides
        qs.filter(domain__isnull=True).update(perm_write=True)
        assert_forbidden(myipv4="")
        assert_allowed(myipv4="preserve", myipv6="")  # just IPv6

        # AAAA (allow) and A (allow via default policy fallback)
        qs.filter(domain=self.my_domains[1], type="A").delete()
        assert_allowed(myipv4="", myipv6="")

        # Default policy (allow)
        qs.filter(domain=self.my_domains[1]).delete()
        assert_allowed(myipv4="", myipv6="")

        # No policy
        qs.filter().delete()
        assert_allowed(myipv4="", myipv6="")

    def test_domain_owner_consistency(self):
        models.TokenDomainPolicy(
            token=self.token, domain=None, subname=None, type=None
        ).save()

        domain = self.my_domains[0]
        policy = models.TokenDomainPolicy(
            token=self.token, domain=domain, subname=None, type=None
        )
        policy.save()

        domain.owner = self.other_domains[0].owner
        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                domain.save()

        policy.delete()
        domain.save()

    def test_token_user_consistency(self):
        policy = models.TokenDomainPolicy(
            token=self.token, domain=None, subname=None, type=None
        )
        policy.save()

        self.token.user = self.other_domains[0].owner
        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                self.token.save()

        policy.delete()
        self.token.save()

    def test_domain_owner_equals_token_user(self):
        models.TokenDomainPolicy(
            token=self.token, domain=None, subname=None, type=None
        ).save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                models.TokenDomainPolicy(
                    token=self.token,
                    domain=self.other_domains[0],
                    subname=None,
                    type=None,
                ).save()

        self.token.user = self.other_domain.owner
        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                self.token.save()

    def test_domain_deletion_policy_cleanup(self):
        domains = [None] + self.my_domains[:2]
        for domain in domains:
            models.TokenDomainPolicy(
                token=self.token, domain=domain, subname=None, type=None
            ).save()

        domain = domains.pop()
        domain.delete()
        self.assertEqual(
            set(policy.domain for policy in self.token.tokendomainpolicy_set.all()),
            set(domains),
        )

    def test_token_deletion(self):
        domains = [None] + self.my_domains[:2]
        policies = {}
        for domain in domains:
            policy = models.TokenDomainPolicy(
                token=self.token, domain=domain, subname=None, type=None
            )
            policies[domain] = policy
            policy.save()

        self.token.delete()
        for domain, policy in policies.items():
            self.assertFalse(
                models.TokenDomainPolicy.objects.filter(pk=policy.pk).exists()
            )
            if domain:
                self.assertTrue(models.Domain.objects.filter(pk=domain.pk).exists())

    def test_user_deletion(self):
        domains = [None] + self.my_domains[:2]
        for domain in domains:
            models.TokenDomainPolicy(
                token=self.token, domain=domain, subname=None, type=None
            ).save()

        # User can only be deleted when domains are deleted
        for domain in self.my_domains:
            domain.delete()

        # Only the default policy should be left, so get can simply get() it
        policy_pk = self.token.tokendomainpolicy_set.get().pk

        self.token.user.delete()
        self.assertFalse(models.TokenDomainPolicy.objects.filter(pk=policy_pk).exists())


class TokenAutoPolicyTestCase(DomainOwnerTestCase):
    client_class = TokenDomainPolicyClient

    def setUp(self):
        super().setUp()
        self.client.credentials()  # remove default credential (corresponding to domain owner)
        self.token_manage = self.create_token(self.owner, perm_manage_tokens=True)
        self.other_token = self.create_token(self.user)

    def test_default_policy_constraints(self):
        self.assertFalse(self.token.tokendomainpolicy_set.exists())

        # Restrictive default policy created when setting auto_policy=true
        url = DomainOwnerTestCase.reverse("v1:token-detail", pk=self.token.id)
        response = self.client._request(
            self.client.patch, url, using=self.token_manage, data={"auto_policy": True}
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(self.token.tokendomainpolicy_set.count(), 1)
        default_policy = self.token.get_policy()
        self.assertFalse(default_policy.perm_write)

        # Can't relax default policy
        response = self.client.patch_policy(
            self.token,
            using=self.token_manage,
            policy_id=default_policy.id,
            data={"perm_write": True},
        )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["perm_write"][0],
            "Must be false when auto_policy is in effect for the token.",
        )

        # Can't delete default policy
        response = self.client.delete_policy(
            self.token, using=self.token_manage, policy_id=default_policy.id
        )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "Can't delete default policy when auto_policy is in effect for the token.",
        )

        # Can relax default policy when auto_policy=false
        self.token.auto_policy = False
        self.token.save()
        connection.check_constraints()  # simulate transaction commit

        response = self.client.patch_policy(
            self.token,
            using=self.token_manage,
            policy_id=default_policy.id,
            data={"perm_write": True},
        )
        self.assertStatus(response, status.HTTP_200_OK)
        connection.check_constraints()  # simulate transaction commit

        # Can't set auto_policy when default policy is permissive
        response = self.client._request(
            self.client.patch, url, using=self.token_manage, data={"auto_policy": True}
        )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["auto_policy"][0],
            "Auto policy requires a restrictive default policy.",
        )

        # Can delete default policy when auto_policy=false
        response = self.client.delete_policy(
            self.token, using=self.token_manage, policy_id=default_policy.id
        )
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

    def test_auto_policy_from_creation(self):
        url = DomainOwnerTestCase.reverse("v1:token-list")
        response = self.client._request(
            self.client.post, url, using=self.token_manage, data={"auto_policy": True}
        )
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertTrue(response.data["auto_policy"])

        # Check that restrictive default policy has been created
        token = models.Token.objects.get(pk=response.data["id"])
        self.assertEqual(token.tokendomainpolicy_set.count(), 1)
        self.assertFalse(token.get_policy().perm_write)

    def test_create_domain(self):
        self.token.auto_policy = True
        self.token.save()
        self.token_manage.perm_create_domain = True
        self.token_manage.save()

        name_auto = "domain.example"
        name_other = "other.example"
        with self.assertRequests(self.requests_desec_domain_creation(name_other)):
            response = self.client._request(
                self.client.post,
                self.reverse("v1:domain-list"),
                using=self.token_manage,
                data={"name": name_other},
            )
            self.assertStatus(response, status.HTTP_201_CREATED)
        with self.assertRequests(self.requests_desec_domain_creation(name_auto)):
            response = self.client._request(
                self.client.post,
                self.reverse("v1:domain-list"),
                using=self.token,
                data={"name": name_auto},
            )
            self.assertStatus(response, status.HTTP_201_CREATED)

        self.assertEqual(self.token.tokendomainpolicy_set.count(), 2)
        rrset = models.RRset(domain=models.Domain.objects.get(name=name_auto))
        self.assertTrue(self.token.get_policy(rrset).perm_write)
        rrset = models.RRset(domain=models.Domain.objects.get(name=name_other))
        self.assertFalse(self.token.get_policy(rrset).perm_write)

    def test_delete_token_with_autopolicy(self):
        self.token_manage.auto_policy = True
        self.token_manage.save()
        connection.check_constraints()  # simulate transaction commit

        response = self.client._request(
            self.client.delete,
            self.reverse("v1:token-detail", pk=self.token_manage.id),
            using=self.token_manage,
        )
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)
