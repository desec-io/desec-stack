from contextlib import nullcontext

from django.db import transaction
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
    default_data = dict(perm_dyndns=False, perm_write=False)

    def setUp(self):
        super().setUp()
        self.client.credentials()  # remove default credential (corresponding to domain owner)
        self.token_manage = self.create_token(self.owner, perm_manage_tokens=True)
        self.other_token = self.create_token(self.user)

    def test_get_policy(self):
        def get_policy(domain, subname, type):
            return self.token.get_policy(domain=domain, subname=subname, type=type)

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
            data = dict(perm_dyndns=False, perm_write=True)
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

        # Create
        ## default policy
        data = {"domain": None, "subname": None, "type": None, "perm_write": True}
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
            "perm_dyndns": True,
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
            perm_dyndns=False,
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
        data = dict(perm_dyndns=True)
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

        def _perform_requests(name, perm, value, **kwargs):
            responses = []
            if value:
                pdns_name = self._normalize_name(name).lower()
                cm = self.assertNoRequestsBut(
                    self.request_pdns_zone_update(name=pdns_name),
                    self.request_pdns_zone_axfr(name=pdns_name),
                )
            else:
                cm = nullcontext()

            if perm == "perm_dyndns":
                data = {"username": name, "password": self.token.plain}
                with cm:
                    responses.append(
                        self.client.get(self.reverse("v1:dyndns12update"), data)
                    )
                return responses

            if perm == "perm_write":
                url_detail = self.reverse("v1:rrset@", name=name, subname="", type="A")
                url_list = self.reverse("v1:rrsets", name=name)

                responses.append(self.client.get(url_list, **kwargs))
                responses.append(self.client.patch(url_list, [], **kwargs))
                responses.append(self.client.put(url_list, [], **kwargs))
                responses.append(self.client.post(url_list, [], **kwargs))

                data = {"subname": "", "type": "A", "ttl": 3600, "records": ["1.2.3.4"]}
                with cm:
                    responses += [
                        self.client.delete(url_detail, **kwargs),
                        self.client.post(url_list, data=data, **kwargs),
                        self.client.put(url_detail, data=data, **kwargs),
                        self.client.patch(url_detail, data=data, **kwargs),
                        self.client.get(url_detail, **kwargs),
                    ]
                return responses

            raise ValueError(f"Unexpected permission: {perm}")

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

                    # Perform requests that test this permission and inspect responses
                    for response in _perform_requests(
                        domain.name, perm, value, **kwargs
                    ):
                        if value:
                            self.assertIn(response.status_code, range(200, 300))
                        else:
                            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

                    # Can't create domain
                    data = {"name": self.random_domain_name()}
                    response = self.client.post(
                        self.reverse("v1:domain-list"), data, **kwargs
                    )
                    self.assertStatus(response, status.HTTP_403_FORBIDDEN)

                    # Can't access account details
                    response = self.client.get(self.reverse("v1:account"), **kwargs)
                    self.assertStatus(response, status.HTTP_403_FORBIDDEN)

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

    def test_domain_deletion(self):
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
