from django.apps import AppConfig

class OeeAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'oee_analytics'
    
    def ready(self):
        from . import simple_example