from rest_framework import generics

from desecapi.serializers import CaptchaSerializer


class CaptchaView(generics.CreateAPIView):
    serializer_class = CaptchaSerializer
    throttle_scope = 'account_management_passive'
