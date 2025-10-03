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


class MLFeatureStore(models.Model):
    """Model for storing ML features for analytics"""
    
    timestamp = models.DateTimeField(db_index=True)
    line_id = models.CharField(max_length=50, db_index=True)
    feature_name = models.CharField(max_length=100, db_index=True)
    feature_value = models.FloatField()
    feature_type = models.CharField(max_length=20, choices=[
        ('realtime', 'Real-time'),
        ('aggregated', 'Aggregated'),
        ('derived', 'Derived'),
    ])
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'line_id', 'feature_name']),
            models.Index(fields=['line_id', 'feature_name', 'timestamp']),
        ]
        unique_together = ['timestamp', 'line_id', 'feature_name']
    
    def __str__(self):
        return f"{self.line_id} - {self.feature_name}: {self.feature_value}"


class MLModelRegistry(models.Model):
    """Model for tracking ML models and versions"""
    
    model_name = models.CharField(max_length=100, unique=True)
    model_version = models.CharField(max_length=20)
    model_path = models.CharField(max_length=500)
    model_type = models.CharField(max_length=50, choices=[
        ('downtime_prediction', 'Downtime Prediction'),
        ('quality_risk', 'Quality Risk'),
        ('oee_forecast', 'OEE Forecast'),
        ('anomaly_detection', 'Anomaly Detection'),
        ('operator_efficiency', 'Operator Efficiency'),
    ])
    performance_metrics = models.JSONField(default=dict)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model_type', 'is_active']),
            models.Index(fields=['model_name', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.model_name} v{self.model_version} ({'Active' if self.is_active else 'Inactive'})"


class MLInference(models.Model):
    """Model for storing ML predictions and explanations"""
    
    timestamp = models.DateTimeField(db_index=True)
    line_id = models.CharField(max_length=50, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    prediction_type = models.CharField(max_length=50, choices=[
        ('risk_score', 'Risk Score'),
        ('downtime_probability', 'Downtime Probability'),
        ('quality_prediction', 'Quality Prediction'),
        ('oee_forecast', 'OEE Forecast'),
        ('anomaly_score', 'Anomaly Score'),
    ])
    prediction_value = models.FloatField()
    confidence_score = models.FloatField()
    explanation_data = models.JSONField(default=dict)  # SHAP values and feature importance
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'line_id', 'model_name']),
            models.Index(fields=['line_id', 'prediction_type', 'timestamp']),
            models.Index(fields=['model_name', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.line_id} - {self.prediction_type}: {self.prediction_value:.3f} (conf: {self.confidence_score:.3f})"
