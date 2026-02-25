from django.apps import AppConfig
from importlib import import_module


class CommunityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'community'

    def ready(self):
        # Import signal handlers
        import_module('community.signals')
