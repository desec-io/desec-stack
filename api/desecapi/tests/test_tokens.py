from rest_framework import status

from desecapi.models import Token
from desecapi.tests.base import DomainOwnerTestCase


class TokenTestCase(DomainOwnerTestCase):

    def setUp(self):
        super().setUp()
        self.token2 = self.create_token(self.owner, name='testtoken')
        self.other_token = self.create_token(self.user)

    def test_list_tokens(self):
        response = self.client.get(self.reverse('v1:token-list'))
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertIn('id', response.data[0])
        self.assertFalse(any(field in response.data[0] for field in ['token', 'key', 'value']))
        self.assertNotContains(response, self.token.plain)

    def test_delete_my_token(self):
        token_id = Token.objects.get(user=self.owner, name='testtoken').id
        url = self.reverse('v1:token-detail', pk=token_id)

        response = self.client.delete(url)
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(pk=token_id).exists())

        response = self.client.get(url)
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_retrieve_my_token(self):
        token_id = Token.objects.get(user=self.owner, name='testtoken').id
        url = self.reverse('v1:token-detail', pk=token_id)

        response = self.client.get(url)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertFalse(any(field in response.data for field in ['token', 'key', 'value']))

    def test_retrieve_other_token(self):
        token_id = Token.objects.get(user=self.user).id
        url = self.reverse('v1:token-detail', pk=token_id)

        response = self.client.get(url)
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_update_my_token(self):
        token_id = Token.objects.get(user=self.user).id
        url = self.reverse('v1:token-detail', pk=token_id)

        for method in [self.client.patch, self.client.put]:
            response = method(url, data={'name': 'foobar'})
            self.assertStatus(response, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_token(self):
        n = len(Token.objects.filter(user=self.owner).all())

        response = self.client.post(self.reverse('v1:token-list'))
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertTrue(all(field in response.data for field in ['id', 'created', 'token', 'name']))
        self.assertEqual(response.data['name'], '')

        response = self.client.post(self.reverse('v1:token-list'), data={'name': 'foobar'})
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertTrue(all(field in response.data for field in ['id', 'created', 'token', 'name']))
        self.assertEqual(response.data['name'], 'foobar')

        self.assertEqual(len(Token.objects.filter(user=self.owner).all()), n + 2)
