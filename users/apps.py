from django.apps import AppConfig

class UserConfig(AppConfig):  # Class name updated to singular for consistency
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        """Import signals to ensure they are connected when the app starts."""
        from . import signals  # Relative import for better app portability
