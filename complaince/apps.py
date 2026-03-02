from django.apps import AppConfig


class ComplainceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'complaince'

    def ready(self):
        """
        Connect signals when the app is ready.
        """
        import complaince.signals  # noqa
