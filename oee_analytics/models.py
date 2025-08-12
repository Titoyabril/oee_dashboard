from django.db import models
from django.utils import timezone

class ProductionMetrics(models.Model):
    """Model for storing calculated OEE metrics"""
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    shift_start = models.DateTimeField(db_index=True)
    line_id = models.CharField(max_length=50, blank=True, db_index=True)
    
    # OEE Components
    availability = models.FloatField(default=0.0)
    performance = models.FloatField(default=0.0) 
    quality = models.FloatField(default=0.0)
    oee = models.FloatField(default=0.0)
    
    # Production counts
    target_count = models.IntegerField(default=0)
    actual_count = models.IntegerField(default=0)
    good_count = models.IntegerField(default=0)
    reject_count = models.IntegerField(default=0)
    
    # Downtime
    total_downtime_minutes = models.FloatField(default=0.0)
    planned_downtime_minutes = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'line_id']),
            models.Index(fields=['shift_start', 'line_id']),
        ]
    
    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.line_id} - OEE: {self.oee:.1f}%"
