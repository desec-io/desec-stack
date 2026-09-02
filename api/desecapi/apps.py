from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "desecapi"

    def ready(self):
        from desecapi import signals  # noqa: F401 (connect signals)
