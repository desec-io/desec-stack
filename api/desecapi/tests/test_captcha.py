from base64 import b64decode
from io import BytesIO
from unittest import mock

from PIL import Image
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api import settings
from desecapi.models import Captcha
from desecapi.serializers import CaptchaSolutionSerializer
from desecapi.tests.base import DesecTestCase


class CaptchaClient(APIClient):

    def obtain(self, **kwargs):
        return self.post(reverse('v1:captcha'), data=kwargs)


class CaptchaModelTestCase(TestCase):
    captcha_class = Captcha

    def test_random_initialization(self):
        captcha = [self.captcha_class() for _ in range(2)]
        self.assertNotEqual(captcha[0].content, None)
        self.assertNotEqual(captcha[0].content, '')
        self.assertNotEqual(captcha[0].content, captcha[1].content)

    def test_verify_solution(self):
        for _ in range(10):
            c = self.captcha_class.objects.create()
            self.assertFalse(c.verify('likely the wrong solution!'))
            c = self.captcha_class.objects.create()
            self.assertTrue(c.verify(c.content))


class CaptchaWorkflowTestCase(DesecTestCase):
    client_class = CaptchaClient
    captcha_class = Captcha
    serializer_class = CaptchaSolutionSerializer
    kind = None

    def verify(self, id, solution):
        """
        Given unsafe (user-input) id and solution, this is how the CAPTCHA module expects you to
        verify that id and solution are valid.
        :param id: unsafe ID
        :param solution: unsafe proposed solution
        :return: whether the id/solution pair is correct
        """
        # use the serializer to validate the solution; id is validated implicitly on DB lookup
        return self.serializer_class(data={'id': id, 'solution': solution}).is_valid()

    def obtain(self):
        if self.kind is None:
            return self.client.obtain()
        else:
            return self.client.obtain(kind=self.kind)

    def test_obtain(self):
        response = self.obtain()
        self.assertContains(response, 'id', status_code=status.HTTP_201_CREATED)
        self.assertContains(response, 'challenge', status_code=status.HTTP_201_CREATED)
        self.assertTrue('content' not in response.data)
        self.assertTrue(len(response.data) == 3)
        self.assertEqual(self.captcha_class.objects.all().count(), 1)
        # use the value of f'<img src="data:image/png;base64,{response.data["challenge"].decode()}" />'
        # to display the CAPTCHA in a browser

    def test_verify_correct(self):
        id = self.obtain().data['id']
        correct_solution = Captcha.objects.get(id=id).content
        self.assertTrue(self.verify(id, correct_solution))

    def test_verify_incorrect(self):
        id = self.obtain().data['id']
        wrong_solution = 'most certainly wrong!'
        self.assertFalse(self.verify(id, wrong_solution))

    def test_expired(self):
        id = self.obtain().data['id']
        correct_solution = Captcha.objects.get(id=id).content

        with mock.patch('desecapi.models.timezone.now', return_value=timezone.now() + settings.CAPTCHA_VALIDITY_PERIOD):
            self.assertFalse(self.verify(id, correct_solution))


class ImageCaptchaWorkflowTestCase(CaptchaWorkflowTestCase):
    kind = 'image'

    def test_length(self):
        self.assertTrue(5000 < len(self.obtain().data['challenge']) < 50000)

    def test_parses(self):
        for _ in range(10):
            # use the show method on the Image object to see the actual image during test run
            # This also allows an impression of how the CAPTCHAs will look like.
            cap = self.obtain().data
            challenge = b64decode(cap['challenge'])
            Image.open(BytesIO(challenge))  # .show()


class AudioCaptchaWorkflowTestCase(CaptchaWorkflowTestCase):
    kind = 'audio'

    def test_length(self):
        self.assertTrue(10**5 < len(self.obtain().data['challenge']) < 10**6)

    def test_parses(self):
        for _ in range(10):
            challenge = b64decode(self.obtain().data['challenge'])
            self.assertTrue(b'WAVE' in challenge)
