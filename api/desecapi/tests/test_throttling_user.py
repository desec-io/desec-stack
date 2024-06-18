from unittest import mock
import time

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory, force_authenticate

from desecapi.models import User


class MockView(APIView):
    @property
    def throttle_classes(self):
        # Need to import here so that the module is only loaded once the settings override is in effect
        from desecapi.throttling import UserRateThrottle

        return (UserRateThrottle,)

    def get(self, request):
        return Response("foo")


class ThrottlingTestCase(TestCase):
    """
    Based on DRF's test_throttling.py.
    """

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def _test_requests_are_throttled(self, counts, user=None):
        cache.clear()
        request = self.factory.get("/")
        if user is not None:
            force_authenticate(request, user=user)
        with override_settings(
            REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": {"user": "10/d"}}
        ):
            view = MockView.as_view()
            sum_delay = 0
            for delay, count, max_wait in counts:
                sum_delay += delay
                with mock.patch(
                    "desecapi.throttling.UserRateThrottle.timer",
                    return_value=time.time() + sum_delay,
                ):
                    for _ in range(count):
                        response = view(request)
                        self.assertEqual(response.status_code, status.HTTP_200_OK)

                    response = view(request)
                    self.assertEqual(
                        response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
                    )
                    self.assertTrue(
                        max_wait - 1 <= float(response["Retry-After"]) <= max_wait
                    )

    def test_requests_are_throttled_unauthenticated(self):
        self._test_requests_are_throttled(
            [(0, 10, 86400), (86399, 0, 1), (1, 10, 86400)]
        )

    def test_requests_are_throttled_user(self):
        for email, throttle_daily_rate in [
            ("foo@bar.com", None),
            ("foo@bar.net", 3),
            ("foo@bar.org", 30),
        ]:
            user = User.objects.create_user(
                email=email, password="", throttle_daily_rate=throttle_daily_rate
            )
            self._test_requests_are_throttled(
                [(0, throttle_daily_rate or 10, 86400)], user=user
            )
