from rest_framework import status

from desecapi.tests.base import DomainOwnerTestCase


class TokenPoliciesTestCase(DomainOwnerTestCase):
    def setUp(self):
        super().setUp()
        self.client.credentials()  # remove default credential (corresponding to domain owner)
        self.token_manage = self.create_token(self.owner, perm_manage_tokens=True)
        self.other_token = self.create_token(self.user)

    def test_policies(self):
        url = DomainOwnerTestCase.reverse(
            "v1:token-policies-root", token_id=self.token.id
        )

        kwargs = {}
        response = self.client.get(url, **kwargs)
        self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)

        kwargs.update(HTTP_AUTHORIZATION=f"Token {self.token_manage.plain}")
        response = self.client.get(url, **kwargs)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertIn("rrsets", response.data)

        kwargs.update(HTTP_AUTHORIZATION=f"Token {self.token.plain}")
        response = self.client.get(url, **kwargs)
        self.assertStatus(response, status.HTTP_200_OK)

        url = DomainOwnerTestCase.reverse(
            "v1:token-policies-root", token_id=self.token_manage.id
        )
        response = self.client.get(url, **kwargs)
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)
