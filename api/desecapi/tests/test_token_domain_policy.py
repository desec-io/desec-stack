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
            kwargs.update(HTTP_AUTHORIZATION=f'Token {using.plain}')
        return method(url, **kwargs)

    def _request_policy(self, method, target, *, using, domain, **kwargs):
        domain = domain or 'default'
        url = DomainOwnerTestCase.reverse('v1:token_domain_policies-detail', token_id=target.id, domain__name=domain)
        return self._request(method, url, using=using, **kwargs)

    def _request_policies(self, method, target, *, using, **kwargs):
        url = DomainOwnerTestCase.reverse('v1:token_domain_policies-list', token_id=target.id)
        return self._request(method, url, using=using, **kwargs)

    def list_policies(self, target, *, using):
        return self._request_policies(self.get, target, using=using)

    def create_policy(self, target, *, using, **kwargs):
        return self._request_policies(self.post, target, using=using, **kwargs)

    def get_policy(self, target, *, using, domain):
        return self._request_policy(self.get, target, using=using, domain=domain)

    def patch_policy(self, target, *, using, domain, **kwargs):
        return self._request_policy(self.patch, target, using=using, domain=domain, **kwargs)

    def delete_policy(self, target, *, using, domain):
        return self._request_policy(self.delete, target, using=using, domain=domain)


class TokenDomainPolicyTestCase(DomainOwnerTestCase):
    client_class = TokenDomainPolicyClient
    default_data = dict(perm_dyndns=False, perm_rrsets=False)

    def setUp(self):
        super().setUp()
        self.client.credentials()  # remove default credential (corresponding to domain owner)
        self.token_manage = self.create_token(self.owner, perm_manage_tokens=True)
        self.other_token = self.create_token(self.user)

    def test_policy_lifecycle_without_management_permission(self):
        # Prepare (with management token)
        data = dict(domain=None, perm_rrsets=True)
        response = self.client.create_policy(self.token, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_201_CREATED)
        response = self.client.create_policy(self.token_manage, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_201_CREATED)

        # Self-inspection is fine
        ## List
        response = self.client.list_policies(self.token, using=self.token)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        ## Get
        response = self.client.get_policy(self.token, using=self.token, domain=None)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data)

        # Inspection of other tokens forbidden
        ## List
        response = self.client.list_policies(self.token_manage, using=self.token)
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)

        ## Get
        response = self.client.get_policy(self.token_manage, using=self.token, domain=None)
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)

        # Write operations forbidden (self and other)
        for target in [self.token, self.token_manage]:
            # Create
            response = self.client.create_policy(target, using=self.token)
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

            # Change
            data = dict(domain=self.my_domains[1].name, perm_dyndns=False, perm_rrsets=True)
            response = self.client.patch_policy(target, using=self.token, domain=self.my_domains[0].name, data=data)
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

            # Delete
            response = self.client.delete_policy(target, using=self.token, domain=None)
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
        self.assertEqual(response.data['domain'], ['This field is required.'])

        ## without a default policy
        data = dict(domain=self.my_domains[0].name)
        with transaction.atomic():
            response = self.client.create_policy(self.token, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['domain'], ['Policy precedence: The first policy must be the default policy.'])

        # List: still empty
        response = self.client.list_policies(self.token, using=self.token_manage)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

        # Create
        ## default policy
        data = dict(domain=None, perm_rrsets=True)
        response = self.client.create_policy(self.token, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_201_CREATED)

        ## can't create another default policy
        with transaction.atomic():
            response = self.client.create_policy(self.token, using=self.token_manage, data=dict(domain=None))
        self.assertStatus(response, status.HTTP_409_CONFLICT)

        ## verify object creation
        response = self.client.get_policy(self.token, using=self.token_manage, domain=None)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data)

        ## can't create policy for other user's domain
        data = dict(domain=self.other_domain.name, perm_dyndns=True, perm_rrsets=True)
        response = self.client.create_policy(self.token, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['domain'][0].code, 'does_not_exist')

        ## another policy
        data = dict(domain=self.my_domains[0].name, perm_dyndns=True)
        response = self.client.create_policy(self.token, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_201_CREATED)

        ## can't create policy for the same domain
        with transaction.atomic():
            response = self.client.create_policy(self.token, using=self.token_manage,
                                                 data=dict(domain=self.my_domains[0].name, perm_dyndns=False))
        self.assertStatus(response, status.HTTP_409_CONFLICT)

        ## verify object creation
        response = self.client.get_policy(self.token, using=self.token_manage, domain=self.my_domains[0].name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data)

        # List: now has two elements
        response = self.client.list_policies(self.token, using=self.token_manage)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Change
        ## all fields of a policy
        data = dict(domain=self.my_domains[1].name, perm_dyndns=False, perm_rrsets=True)
        response = self.client.patch_policy(self.token, using=self.token_manage, domain=self.my_domains[0].name,
                                            data=data)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data)

        ## verify modification
        response = self.client.get_policy(self.token, using=self.token_manage, domain=self.my_domains[1].name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data)

        ## verify that policy for former domain is gone
        response = self.client.get_policy(self.token, using=self.token_manage, domain=self.my_domains[0].name)
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

        ## verify that the default policy can't be changed to a non-default policy
        with transaction.atomic():
            response = self.client.patch_policy(self.token, using=self.token_manage, domain=None, data=data)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data,
                         {'domain': ['Policy precedence: Cannot disable default policy when others exist.']})

        ## partially modify the default policy
        data = dict(perm_dyndns=True)
        response = self.client.patch_policy(self.token, using=self.token_manage, domain=None, data=data)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, {'domain': None, 'perm_rrsets': True} | data)

        # Delete
        ## can't delete default policy while others exist
        with transaction.atomic():
            response = self.client.delete_policy(self.token, using=self.token_manage, domain=None)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data,
                         {'domain': ["Policy precedence: Can't delete default policy when there exist others."]})

        ## delete other policy
        response = self.client.delete_policy(self.token, using=self.token_manage, domain=self.my_domains[1].name)
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        ## delete default policy
        response = self.client.delete_policy(self.token, using=self.token_manage, domain=None)
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        ## idempotence: delete a non-existing policy
        response = self.client.delete_policy(self.token, using=self.token_manage, domain=self.my_domains[0].name)
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        ## verify that policies are gone
        for domain in [None, self.my_domains[0].name, self.my_domains[1].name]:
            response = self.client.get_policy(self.token, using=self.token_manage, domain=domain)
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
                cm = self.assertPdnsNoRequestsBut(self.request_pdns_zone_update(name=pdns_name),
                                                  self.request_pdns_zone_axfr(name=pdns_name))
            else:
                cm = nullcontext()

            if perm == 'perm_dyndns':
                data = {'username': name, 'password': self.token.plain}
                with cm:
                    responses.append(self.client.get(self.reverse('v1:dyndns12update'), data))
                return responses

            if perm == 'perm_rrsets':
                url_detail = self.reverse('v1:rrset@', name=name, subname='', type='A')
                url_list = self.reverse('v1:rrsets', name=name)

                responses.append(self.client.get(url_list, **kwargs))
                responses.append(self.client.patch(url_list, [], **kwargs))
                responses.append(self.client.put(url_list, [], **kwargs))
                responses.append(self.client.post(url_list, [], **kwargs))

                data = {'subname': '', 'type': 'A', 'ttl': 3600, 'records': ['1.2.3.4']}
                with cm:
                    responses += [
                        self.client.delete(url_detail, **kwargs),
                        self.client.post(url_list, data=data, **kwargs),
                        self.client.put(url_detail, data=data, **kwargs),
                        self.client.patch(url_detail, data=data, **kwargs),
                        self.client.get(url_detail, **kwargs),
                    ]
                return responses

            raise ValueError(f'Unexpected permission: {perm}')

        # Create
        ## default policy
        data = dict(domain=None)
        response = self.client.create_policy(self.token, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_201_CREATED)

        ## another policy
        data = dict(domain=self.my_domains[0].name)
        response = self.client.create_policy(self.token, using=self.token_manage, data=data)
        self.assertStatus(response, status.HTTP_201_CREATED)

        ## verify object creation
        response = self.client.get_policy(self.token, using=self.token_manage, domain=self.my_domains[0].name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.default_data | data)

        policies = {
            self.my_domains[0]: self.token.tokendomainpolicy_set.get(domain__isnull=False),
            self.my_domains[1]: self.token.tokendomainpolicy_set.get(domain__isnull=True),
        }

        kwargs = dict(HTTP_AUTHORIZATION=f'Token {self.token.plain}')

        # For each permission type
        for perm in self.default_data.keys():
            # For the domain with specific policy and for the domain covered by the default policy
            for domain in policies.keys():
                # For both possible values of the permission
                for value in [True, False]:
                    # Set only that permission for that domain (on its effective policy)
                    _reset_policies(self.token)
                    policy = policies[domain]
                    setattr(policy, perm, value)
                    policy.save()

                    # Perform requests that test this permission and inspect responses
                    for response in _perform_requests(domain.name, perm, value, **kwargs):
                        if value:
                            self.assertIn(response.status_code, range(200, 300))
                        else:
                            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

                    # Can't create domain
                    data = {'name': self.random_domain_name()}
                    response = self.client.post(self.reverse('v1:domain-list'), data, **kwargs)
                    self.assertStatus(response, status.HTTP_403_FORBIDDEN)

                    # Can't access account details
                    response = self.client.get(self.reverse('v1:account'), **kwargs)
                    self.assertStatus(response, status.HTTP_403_FORBIDDEN)

    def test_domain_owner_consistency(self):
        models.TokenDomainPolicy(token=self.token, domain=None).save()

        domain = self.my_domains[0]
        policy = models.TokenDomainPolicy(token=self.token, domain=domain)
        policy.save()

        domain.owner = self.other_domains[0].owner
        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                domain.save()

        policy.delete()
        domain.save()

    def test_token_user_consistency(self):
        policy = models.TokenDomainPolicy(token=self.token, domain=None)
        policy.save()

        self.token.user = self.other_domains[0].owner
        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                self.token.save()

        policy.delete()
        self.token.save()

    def test_domain_owner_equals_token_user(self):
        models.TokenDomainPolicy(token=self.token, domain=None).save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                models.TokenDomainPolicy(token=self.token, domain=self.other_domains[0]).save()

        self.token.user = self.other_domain.owner
        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # https://stackoverflow.com/a/23326971/6867099
                self.token.save()

    def test_domain_deletion(self):
        domains = [None] + self.my_domains[:2]
        for domain in domains:
            models.TokenDomainPolicy(token=self.token, domain=domain).save()

        domain = domains.pop()
        domain.delete()
        self.assertEqual(list(map(lambda x: x.domain, self.token.tokendomainpolicy_set.all())), domains)

    def test_token_deletion(self):
        domains = [None] + self.my_domains[:2]
        policies = {}
        for domain in domains:
            policy = models.TokenDomainPolicy(token=self.token, domain=domain)
            policies[domain] = policy
            policy.save()

        self.token.delete()
        for domain, policy in policies.items():
            self.assertFalse(models.TokenDomainPolicy.objects.filter(pk=policy.pk).exists())
            if domain:
                self.assertTrue(models.Domain.objects.filter(pk=domain.pk).exists())

    def test_user_deletion(self):
        domains = [None] + self.my_domains[:2]
        for domain in domains:
            models.TokenDomainPolicy(token=self.token, domain=domain).save()

        # User can only be deleted when domains are deleted
        for domain in self.my_domains:
            domain.delete()

        # Only the default policy should be left, so get can simply get() it
        policy_pk = self.token.tokendomainpolicy_set.get().pk

        self.token.user.delete()
        self.assertFalse(models.TokenDomainPolicy.objects.filter(pk=policy_pk).exists())
