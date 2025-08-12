from django.apps import AppConfig

class OeeAnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "oee_analytics"

    def ready(self):
        # ensure these modules are imported so they register themselves
        from . import signals  # hooks post_save to push WS events
        from .dash_apps import downtime_timeline  # registers DjangoDash("DowntimeTimeline")
