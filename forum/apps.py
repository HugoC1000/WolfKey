from django.apps import AppConfig


class ForumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forum'
    
    def ready(self):
        # Register the small set of model lifecycle safeguards in one place.
        import forum.signals  # noqa: F401
