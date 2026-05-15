from django.apps import AppConfig


class ForumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forum'
    
    def ready(self):
        import forum.signals  # Import signals to register them
        
        # Rebuild schedule cache on server startup
        try:
            from forum.services.schedule_services import rebuild_date_row_cache
            rebuild_date_row_cache()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to rebuild schedule cache on startup: {str(e)}")
