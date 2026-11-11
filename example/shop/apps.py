from django.apps import AppConfig


class ShopConfig(AppConfig):
    name = 'shop'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from shop import policies  # noqa: F401 - registers the order policy
