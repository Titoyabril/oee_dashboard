from django.contrib import admin
from .models import DowntimeEvent

@admin.register(DowntimeEvent)
class DowntimeEventAdmin(admin.ModelAdmin):
    list_display = ("ts","line_id","station_id","reason","duration_s","severity","source")
    list_filter = ("line_id","station_id","reason","source")
    search_fields = ("detail",)
    date_hierarchy = "ts"
