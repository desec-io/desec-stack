from unittest import mock
import time

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory


def override_rates(rates):
    return override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_CLASSES': ['desecapi.throttling.ScopedRatesThrottle'],
                                             'DEFAULT_THROTTLE_RATES': {'test_scope': rates}})


class MockView(APIView):
    throttle_scope = 'test_scope'

    @property
    def throttle_classes(self):
        # Need to import here so that the module is only loaded once the settings override is in effect
        from desecapi.throttling import ScopedRatesThrottle
        return (ScopedRatesThrottle,)

    def get(self, request):
        return Response('foo')


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
            for delay, count in counts:
                sum_delay += delay
                with mock.patch('desecapi.throttling.ScopedRatesThrottle.timer', return_value=time.time() + sum_delay):
                    for _ in range(count):
                        response = view(request)
                        self.assertEqual(response.status_code, status.HTTP_200_OK)

                    response = view(request)
                    self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        cache.clear()
        request = self.factory.get('/')
        with override_rates(rates):
            do_test()
            if buckets is not None:
                for bucket in buckets:
                    MockView.throttle_scope_bucket = bucket
                    do_test()

    def test_requests_are_throttled_4sec(self):
        self._test_requests_are_throttled(['4/sec'], [(0, 4), (1, 4)])

    def test_requests_are_throttled_4min(self):
        self._test_requests_are_throttled(['4/min'], [(0, 4)])

    def test_requests_are_throttled_multiple(self):
        self._test_requests_are_throttled(['5/s', '4/day'], [(0, 4)])
        self._test_requests_are_throttled(['4/s', '5/day'], [(0, 4)])

    def test_requests_are_throttled_multiple_cascade(self):
        # We test that we can do 4 requests in the first second and only 2 in the second second
        self._test_requests_are_throttled(['4/s', '6/day'], [(0, 4), (1, 2)])

    def test_requests_are_throttled_multiple_cascade_with_buckets(self):
        # We test that we can do 4 requests in the first second and only 2 in the second second
        self._test_requests_are_throttled(['4/s', '6/day'], [(0, 4), (1, 2)], buckets=['foo', 'bar'])
