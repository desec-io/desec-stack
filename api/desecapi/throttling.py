from hashlib import sha1

from rest_framework import throttling
from rest_framework.settings import api_settings

from desecapi import metrics


class ScopedRatesThrottle(throttling.ScopedRateThrottle):
    """
    Like DRF's ScopedRateThrottle, but supports several rates per scope, e.g. for burst vs. sustained limit.
    """

    durations = {"s": 1, "m": 60, "2m": 120, "h": 3600, "d": 86400}

    def _parse_rate(self, rate):
        if rate is None:
            return (None, None)
        num, period = rate.split("/")
        num_requests = int(num)
        duration = self.durations[
            "".join(filter(str.isdigit, period)) + next(filter(str.isalpha, period))
        ]
        return (num_requests, duration)

    def parse_rate(self, rates):
        return [self._parse_rate(rate) for rate in rates]

    def allow_request(self, request, view):
        # We can only determine the scope once we're called by the view.  Always allow request if scope not set.
        scope = getattr(view, self.scope_attr, None)
        if not scope:
            return True

        # Determine the allowed request rate as we normally would during
        # the `__init__` call.
        self.scope = scope
        self.rate = self.get_rate()
        if self.rate is None:
            return True

        # Amend scope with optional bucket
        bucket = getattr(view, self.scope_attr + "_bucket", None)
        if bucket is not None:
            self.scope += ":" + sha1(bucket.encode()).hexdigest()

        self.now = self.timer()
        self.num_requests, self.duration = zip(*self.parse_rate(self.rate))
        self.key = self.get_cache_key(request, view)
        self.history = {key: [] for key in self.key}
        self.history.update(self.cache.get_many(self.key))

        for num_requests, duration, key in zip(
            self.num_requests, self.duration, self.key
        ):
            history = self.history[key]
            # Drop any requests from the history which have now passed the
            # throttle duration
            while history and history[-1] <= self.now - duration:
                history.pop()
            if len(history) >= num_requests:
                # Prepare variables used by the Throttle's wait() method that gets called by APIView.check_throttles()
                self.num_requests, self.duration, self.key, self.history = (
                    num_requests,
                    duration,
                    key,
                    history,
                )
                response = self.throttle_failure()
                metrics.get("desecapi_throttle_failure").labels(
                    request.method, scope, request.user.pk, bucket
                ).inc()
                return response
            self.history[key] = history
        return self.throttle_success()

    def throttle_success(self):
        for key in self.history:
            self.history[key].insert(0, self.now)
        self.cache.set_many(self.history, max(self.duration))
        return True

    # Override the static attribute of the parent class so that we can dynamically apply override settings for testing
    @property
    def THROTTLE_RATES(self):
        return api_settings.DEFAULT_THROTTLE_RATES

    def get_cache_key(self, request, view):
        key = super().get_cache_key(request, view)
        return [f"{key}_{duration}" for duration in self.duration]


class UserRateThrottle(throttling.UserRateThrottle):
    """
    Like DRF's UserRateThrottle, but supports individual rates per user.
    """

    def __init__(self):
        pass  # defer to allow_request() where request object is available

    def allow_request(self, request, view):
        self.request = request
        super().__init__()  # gets and parses rate
        return super().allow_request(request, view)

    def get_rate(self):
        try:
            return f"{self.request.user.throttle_daily_rate:d}/d"
        except (
            AttributeError,  # request.user is AnonymousUser
            TypeError,  # .throttle_daily_rate is None
        ):
            return super().get_rate()

    # Override the static attribute of the parent class so that we can dynamically apply override settings for testing
    @property
    def THROTTLE_RATES(self):
        return api_settings.DEFAULT_THROTTLE_RATES
