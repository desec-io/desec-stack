from contextlib import contextmanager
from unittest import mock
import time

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory


@contextmanager
def override_bucket(bucket):
    old_bucket = getattr(MockView, "throttle_scope_bucket", None)
    MockView.throttle_scope_bucket = bucket
    try:
        yield
    finally:
        MockView.throttle_scope_bucket = old_bucket


class MockView(APIView):
    throttle_scope = "test_scope"

    @property
    def throttle_classes(self):
        # Need to import here so that the module is only loaded once the settings override is in effect
        from desecapi.throttling import ScopedRatesThrottle

        return (ScopedRatesThrottle,)

    def get(self, request):
        return Response("foo")


class ThrottlingTestCase(TestCase):
    """
    Based on DRF's test_throttling.py.
    """

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def _test_requests_are_throttled(self, rates, counts, buckets=None):
        def do_test():
            view = MockView.as_view()
            sum_delay = 0
            for delay, count, max_wait in counts:
                sum_delay += delay
                with mock.patch(
                    "desecapi.throttling.ScopedRatesThrottle.timer",
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

        cache.clear()
        request = self.factory.get("/")
        with override_settings(
            REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": {MockView.throttle_scope: rates}}
        ):
            do_test()
            if buckets is not None:
                for bucket in buckets:
                    with override_bucket(bucket):
                        do_test()

    def test_requests_are_throttled_4sec(self):
        self._test_requests_are_throttled(["4/sec"], [(0, 4, 1), (1, 4, 1)])

    def test_requests_are_throttled_4min(self):
        self._test_requests_are_throttled(["4/min"], [(0, 4, 60)])

    def test_requests_are_throttled_multiple(self):
        self._test_requests_are_throttled(["5/s", "4/day"], [(0, 4, 86400)])
        self._test_requests_are_throttled(["4/s", "5/day"], [(0, 4, 1)])

    def test_requests_are_throttled_multiple_cascade(self):
        # We test that we can do 4 requests in the first second and only 2 in the second second
        self._test_requests_are_throttled(["4/s", "6/day"], [(0, 4, 1), (1, 2, 86400)])

    def test_requests_are_throttled_multiple_cascade_with_buckets(self):
        # We test that we can do 4 requests in the first second and only 2 in the second second
        self._test_requests_are_throttled(
            ["4/s", "6/day"], [(0, 4, 1), (1, 2, 86400)], buckets=["foo", "bar"]
        )
