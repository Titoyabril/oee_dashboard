from django.db import models

class DowntimeEvent(models.Model):
    ts = models.DateTimeField(db_index=True)
    line_id = models.CharField(max_length=64)
    station_id = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=32, default="vision")  # or "plc"
    reason = models.CharField(max_length=64)                    # BLOCKED/STARVED/FAULT/MANUAL etc.
    detail = models.CharField(max_length=128, blank=True)       # fault code or note
    duration_s = models.FloatField(default=0.0)
    severity = models.IntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=["ts"]),
            models.Index(fields=["line_id", "station_id"]),
        ]

    def __str__(self):
        return f"{self.ts.isoformat()} {self.line_id} {self.station_id} {self.reason}"
