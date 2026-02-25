from django.apps import AppConfig
from importlib import import_module


class SitesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sites'

    def ready(self):
        # Import signal handlers
        import_module('sites.signals')
