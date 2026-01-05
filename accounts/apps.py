from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'


    def ready(self):
        # Import signals so they get registered
        import accounts.signals  # noqa: F401
