from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = 'desecapi'

    def ready(self):
        from desecapi import signals  # connect signals
