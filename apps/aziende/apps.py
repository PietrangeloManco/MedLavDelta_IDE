from django.apps import AppConfig


class AziendeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.aziende'

    def ready(self):
        from . import signals  # noqa: F401
