"""
Sensor Range Configuration Model
Defines expected value ranges for sensors per machine/signal type
"""

from django.db import models


class SensorRangeConfig(models.Model):
    """Expected value ranges for sensors"""
    config_id = models.AutoField(primary_key=True)
    machine_id = models.CharField(max_length=50, db_index=True)
    signal_type = models.CharField(max_length=50, db_index=True)
    min_value = models.DecimalField(max_digits=18, decimal_places=6)
    max_value = models.DecimalField(max_digits=18, decimal_places=6)
    unit = models.CharField(max_length=20)
    violation_action = models.CharField(
        max_length=20,
        default='ALERT',
        choices=[
            ('ALERT', 'Alert only'),
            ('REJECT', 'Reject data'),
            ('FLAG', 'Flag for review')
        ]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'SensorRangeConfigs'
        indexes = [
            models.Index(fields=['machine_id', 'signal_type', 'is_active']),
        ]
        unique_together = [['machine_id', 'signal_type']]

    def __str__(self):
        return f"{self.machine_id}.{self.signal_type}: {self.min_value}-{self.max_value} {self.unit}"
