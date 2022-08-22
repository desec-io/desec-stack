from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


class IdempotentDestroyMixin:
    def destroy(self, request, *args, **kwargs):
        try:
            # noinspection PyUnresolvedReferences
            super().destroy(request, *args, **kwargs)
        except Http404:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class Root(APIView):
    def get(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            routes = {
                'account': {
                    'show': reverse('account', request=request),
                    'delete': reverse('account-delete', request=request),
                    'change-email': reverse('account-change-email', request=request),
                    'reset-password': reverse('account-reset-password', request=request),
                },
                'logout': reverse('logout', request=request),
                'tokens': reverse('token-list', request=request),
                'domains': reverse('domain-list', request=request),
            }
        else:
            routes = {
                'register': reverse('register', request=request),
                'login': reverse('login', request=request),
                'reset-password': reverse('account-reset-password', request=request),
            }
        return Response(routes)
