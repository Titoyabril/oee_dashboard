from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from django.utils.dateparse import parse_datetime
from django.db import models
from oee_analytics.events.models import DowntimeEvent
from oee_analytics.models import MLFeatureStore, MLModelRegistry, MLInference, ProductionMetrics

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

@shared_task(bind=True, ignore_result=True)
def process_machine_event(self, event_data):
    """
    Process incoming machine events asynchronously
    
    Args:
        event_data (dict): Machine event data containing:
            - ts: timestamp
            - line_id: production line ID
            - station_id: station identifier
            - reason: downtime reason
            - duration_s: duration in seconds
            - severity: event severity
            - detail: additional details
    """
    try:
        # Parse timestamp if it's a string
        ts = event_data['ts']
        if isinstance(ts, str):
            ts = parse_datetime(ts)
        
        # Create database record
        event = DowntimeEvent.objects.create(
            ts=ts,
            line_id=event_data.get('line_id', ''),
            station_id=event_data.get('station_id', ''),
            reason=event_data.get('reason', 'Unknown'),
            duration_s=event_data.get('duration_s', 0),
            severity=event_data.get('severity', 1),
            detail=event_data.get('detail', '')
        )
        
        # Send real-time update via WebSocket
        async_to_sync(channel_layer.group_send)(
            "events",
            {
                "type": "event_message",
                "message": {
                    "ts": event.ts.isoformat(),
                    "line_id": event.line_id,
                    "station_id": event.station_id,
                    "reason": event.reason,
                    "duration_s": event.duration_s,
                    "severity": event.severity,
                    "detail": event.detail
                }
            }
        )
        
        # Trigger OEE recalculation if significant event
        if event.duration_s > 60:  # Events longer than 1 minute
            calculate_oee_metrics.delay()
            
        logger.info(f"Processed event: {event.reason} ({event.duration_s}s)")
        return f"Event processed: {event.id}"
        
    except Exception as exc:
        logger.error(f"Error processing event: {exc}")
        # Retry task with exponential backoff
        raise self.retry(exc=exc, countdown=60, max_retries=3)

@shared_task(ignore_result=True)
def calculate_oee_metrics():
    """
    Calculate OEE metrics for the current shift
    """
    try:
        now = timezone.now()
        shift_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
        
        # If it's before 6 AM, use previous day's 6 AM
        if now.hour < 6:
            shift_start = shift_start - timedelta(days=1)
            
        # Get events for current shift
        events = DowntimeEvent.objects.filter(
            ts__gte=shift_start,
            ts__lte=now
        )
        
        # Calculate metrics
        total_downtime = sum(event.duration_s for event in events) / 60  # minutes
        shift_duration = (now - shift_start).total_seconds() / 60  # minutes
        
        # OEE calculations
        availability = max(0, (shift_duration - total_downtime) / shift_duration * 100) if shift_duration > 0 else 100
        performance = 89.1  # Mock - replace with actual calculation based on production data
        quality = 95.8     # Mock - replace with actual quality metrics
        oee = (availability * performance * quality) / 10000
        
        # Broadcast metrics update
        metrics = {
            'oee': round(oee, 1),
            'availability': round(availability, 1), 
            'performance': round(performance, 1),
            'quality': round(quality, 1),
            'production_count': 2847,  # Mock - replace with actual count
            'timestamp': now.isoformat()
        }
        
        async_to_sync(channel_layer.group_send)(
            "metrics",
            {
                "type": "metrics_update", 
                "metrics": metrics
            }
        )
        
        logger.info(f"OEE calculated: {oee:.1f}% (A:{availability:.1f}% P:{performance:.1f}% Q:{quality:.1f}%)")
        return metrics
        
    except Exception as exc:
        logger.error(f"Error calculating OEE: {exc}")
        raise

@shared_task(ignore_result=True)
def cleanup_old_events():
    """
    Clean up old events to maintain database performance
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = DowntimeEvent.objects.filter(ts__lt=cutoff_date).delete()[0]
        logger.info(f"Cleaned up {deleted_count} old events")
        return f"Deleted {deleted_count} events older than 30 days"
    except Exception as exc:
        logger.error(f"Error cleaning up events: {exc}")
        raise

@shared_task(ignore_result=True)
def generate_fake_event():
    """
    Generate a fake event for testing - replaces the management command
    """
    import random
    from datetime import datetime
    
    reasons = ["Mechanical Fault", "Material Shortage", "Changeover", "Quality Check", "Maintenance"]
    severities = [1, 2, 3]  # Use integers as expected by the model
    
    event_data = {
        'ts': timezone.now().isoformat(),
        'line_id': f'LINE_{random.randint(1, 3)}',
        'station_id': f'ST{random.randint(1, 5):02d}',
        'reason': random.choice(reasons),
        'duration_s': random.randint(30, 300),
        'severity': random.choice(severities),
        'detail': f'Auto-generated test event at {datetime.now().strftime("%H:%M:%S")}'
    }
    
    # Process the event
    process_machine_event.delay(event_data)
    return "Fake event generated"

@shared_task(bind=True, ignore_result=True)
def send_alert(self, alert_type, message, severity="warning"):
    """
    Send alerts for critical OEE events
    
    Args:
        alert_type (str): Type of alert (downtime, quality, performance)
        message (str): Alert message
        severity (str): Alert severity (info, warning, error, critical)
    """
    try:
        alert_data = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': timezone.now().isoformat()
        }
        
        # Send to WebSocket clients
        async_to_sync(channel_layer.group_send)(
            "alerts",
            {
                "type": "alert_message",
                "alert": alert_data
            }
        )
        
        logger.warning(f"Alert sent: {alert_type} - {message}")
        return f"Alert sent: {alert_type}"
        
    except Exception as exc:
        logger.error(f"Error sending alert: {exc}")
        raise self.retry(exc=exc, countdown=30, max_retries=2)


# =====================================
# ML PIPELINE TASKS (Phase 2)
# =====================================

@shared_task(ignore_result=True)
def extract_ml_features():
    """
    Extract ML features from production events and store in MLFeatureStore
    """
    try:
        now = timezone.now()
        lookback_hours = 1  # Extract features from last hour
        start_time = now - timedelta(hours=lookback_hours)
        
        # Get recent downtime events
        events = DowntimeEvent.objects.filter(ts__gte=start_time, ts__lte=now)
        
        # Get unique line IDs
        line_ids = events.values_list('line_id', flat=True).distinct()
        
        for line_id in line_ids:
            line_events = events.filter(line_id=line_id)
            
            # Feature 1: Event frequency (events per hour)
            event_frequency = line_events.count() / lookback_hours
            MLFeatureStore.objects.update_or_create(
                timestamp=now,
                line_id=line_id,
                feature_name='event_frequency_per_hour',
                defaults={
                    'feature_value': event_frequency,
                    'feature_type': 'aggregated'
                }
            )
            
            # Feature 2: Average event duration
            avg_duration = line_events.aggregate(avg=models.Avg('duration_s'))['avg'] or 0
            MLFeatureStore.objects.update_or_create(
                timestamp=now,
                line_id=line_id,
                feature_name='avg_event_duration_s',
                defaults={
                    'feature_value': avg_duration,
                    'feature_type': 'aggregated'
                }
            )
            
            # Feature 3: Cumulative downtime (minutes)
            total_downtime = sum(event.duration_s for event in line_events) / 60
            MLFeatureStore.objects.update_or_create(
                timestamp=now,
                line_id=line_id,
                feature_name='total_downtime_minutes',
                defaults={
                    'feature_value': total_downtime,
                    'feature_type': 'aggregated'
                }
            )
            
            # Feature 4: Severity trend (average severity)
            avg_severity = line_events.aggregate(avg=models.Avg('severity'))['avg'] or 1
            MLFeatureStore.objects.update_or_create(
                timestamp=now,
                line_id=line_id,
                feature_name='avg_severity',
                defaults={
                    'feature_value': avg_severity,
                    'feature_type': 'aggregated'
                }
            )
        
        logger.info(f"Extracted ML features for {len(line_ids)} production lines")
        return f"Features extracted for {len(line_ids)} lines"
        
    except Exception as exc:
        logger.error(f"Error extracting ML features: {exc}")
        raise


@shared_task(ignore_result=True) 
def run_downtime_prediction():
    """
    Run ML model for downtime prediction with mock SHAP explanations
    """
    try:
        now = timezone.now()
        
        # Get active downtime prediction models
        models = MLModelRegistry.objects.filter(
            model_type='downtime_prediction',
            is_active=True
        )
        
        if not models.exists():
            # Create a mock model registry entry
            model = MLModelRegistry.objects.create(
                model_name='downtime_predictor_rf_v1',
                model_version='1.0.0',
                model_path='/models/downtime_rf.pkl',
                model_type='downtime_prediction',
                performance_metrics={'accuracy': 0.87, 'precision': 0.82, 'recall': 0.79},
                is_active=True
            )
            models = [model]
        
        # Get latest features for all lines
        recent_features = MLFeatureStore.objects.filter(
            timestamp__gte=now - timedelta(hours=1)
        ).values('line_id').distinct()
        
        for feature_group in recent_features:
            line_id = feature_group['line_id']
            
            # Get latest features for this line
            features = MLFeatureStore.objects.filter(
                line_id=line_id,
                timestamp__gte=now - timedelta(hours=1)
            ).order_by('-timestamp')
            
            if features.count() >= 3:  # Need minimum features
                # Mock prediction logic (replace with actual ML model)
                event_freq = features.filter(feature_name='event_frequency_per_hour').first()
                avg_duration = features.filter(feature_name='avg_event_duration_s').first()
                total_downtime = features.filter(feature_name='total_downtime_minutes').first()
                
                # Simple risk scoring based on features
                risk_score = 0.0
                if event_freq:
                    risk_score += min(event_freq.feature_value * 0.1, 0.4)  # Max 40% from frequency
                if avg_duration:
                    risk_score += min(avg_duration.feature_value / 300, 0.3)  # Max 30% from duration
                if total_downtime:
                    risk_score += min(total_downtime.feature_value / 60, 0.3)  # Max 30% from total downtime
                
                risk_score = min(risk_score, 1.0)  # Cap at 100%
                confidence = 0.85 + np.random.normal(0, 0.05)  # Mock confidence
                
                # Mock SHAP explanations
                shap_explanations = {
                    'feature_importance': {
                        'event_frequency_per_hour': 0.35,
                        'avg_event_duration_s': 0.28,
                        'total_downtime_minutes': 0.25,
                        'avg_severity': 0.12
                    },
                    'top_risk_factors': [
                        'High event frequency detected',
                        'Increasing average event duration',
                        'Cumulative downtime threshold exceeded'
                    ]
                }
                
                # Store prediction
                for model in models:
                    MLInference.objects.create(
                        timestamp=now,
                        line_id=line_id,
                        model_name=model.model_name,
                        prediction_type='downtime_probability',
                        prediction_value=risk_score,
                        confidence_score=confidence,
                        explanation_data=shap_explanations
                    )
                
                # Send to WebSocket for real-time dashboard updates
                async_to_sync(channel_layer.group_send)(
                    "ml_predictions",
                    {
                        "type": "ml_update",
                        "data": {
                            "line_id": line_id,
                            "prediction_type": "downtime_risk", 
                            "risk_score": risk_score,
                            "confidence": confidence,
                            "explanations": shap_explanations,
                            "timestamp": now.isoformat()
                        }
                    }
                )
        
        logger.info(f"Downtime predictions generated for {len(recent_features)} lines")
        return f"Predictions generated for {len(recent_features)} lines"
        
    except Exception as exc:
        logger.error(f"Error running downtime prediction: {exc}")
        raise


@shared_task(ignore_result=True)
def calculate_oee_forecast():
    """
    Generate OEE forecasts with confidence intervals for Three.js ForecastRibbon
    """
    try:
        now = timezone.now()
        forecast_hours = 8  # 8-hour forecast horizon
        
        # Get recent OEE metrics for trend analysis
        recent_metrics = ProductionMetrics.objects.filter(
            timestamp__gte=now - timedelta(hours=24)
        ).order_by('-timestamp')
        
        line_ids = recent_metrics.values_list('line_id', flat=True).distinct()
        
        for line_id in line_ids:
            line_metrics = recent_metrics.filter(line_id=line_id)[:12]  # Last 12 data points
            
            if line_metrics.count() >= 3:
                # Extract OEE trend data
                oee_values = [m.oee for m in line_metrics]
                timestamps = [m.timestamp for m in line_metrics]
                
                # Simple trend forecasting (replace with Prophet/ARIMA for production)
                recent_oee = np.mean(oee_values[:3])  # Last 3 values
                trend = np.mean(np.diff(oee_values[:6]))  # Trend from last 6 values
                
                # Generate forecast points
                forecast_data = []
                for hour in range(1, forecast_hours + 1):
                    forecast_time = now + timedelta(hours=hour)
                    
                    # Base forecast with trend
                    base_forecast = recent_oee + (trend * hour)
                    
                    # Add some realistic bounds
                    base_forecast = max(0, min(100, base_forecast))
                    
                    # Confidence intervals (wider with longer horizon)
                    confidence_width = 2 + (hour * 0.5)  # Expanding uncertainty
                    upper_bound = min(100, base_forecast + confidence_width)
                    lower_bound = max(0, base_forecast - confidence_width)
                    
                    forecast_data.append({
                        'timestamp': forecast_time.isoformat(),
                        'forecast_oee': round(base_forecast, 1),
                        'upper_bound': round(upper_bound, 1),
                        'lower_bound': round(lower_bound, 1),
                        'confidence': round(max(0.5, 0.9 - (hour * 0.05)), 2)
                    })
                
                # Store forecast in MLInference
                MLInference.objects.create(
                    timestamp=now,
                    line_id=line_id,
                    model_name='oee_forecast_trend_v1',
                    prediction_type='oee_forecast',
                    prediction_value=forecast_data[0]['forecast_oee'],  # Next hour forecast
                    confidence_score=forecast_data[0]['confidence'],
                    explanation_data={'forecast_series': forecast_data}
                )
                
                # Send forecast to WebSocket for Three.js ForecastRibbon
                async_to_sync(channel_layer.group_send)(
                    "ml_predictions",
                    {
                        "type": "ml_forecast",
                        "data": {
                            "line_id": line_id,
                            "forecast_type": "oee_trend",
                            "forecast_data": forecast_data,
                            "timestamp": now.isoformat()
                        }
                    }
                )
        
        logger.info(f"OEE forecasts generated for {len(line_ids)} lines")
        return f"Forecasts generated for {len(line_ids)} lines"
        
    except Exception as exc:
        logger.error(f"Error calculating OEE forecast: {exc}")
        raise


@shared_task(ignore_result=True)
def quality_risk_scoring():
    """
    Calculate real-time quality risk scores for Three.js RiskHalo3D visualization
    """
    try:
        now = timezone.now()
        
        # Get recent production metrics
        recent_metrics = ProductionMetrics.objects.filter(
            timestamp__gte=now - timedelta(hours=2)
        ).order_by('-timestamp')
        
        line_ids = recent_metrics.values_list('line_id', flat=True).distinct()
        
        for line_id in line_ids:
            line_metrics = recent_metrics.filter(line_id=line_id)[:6]  # Last 6 data points
            
            if line_metrics.count() >= 2:
                # Calculate quality trend
                quality_values = [m.quality for m in line_metrics]
                quality_trend = np.mean(np.diff(quality_values[:4])) if len(quality_values) >= 2 else 0
                current_quality = quality_values[0]
                
                # Quality risk scoring
                risk_score = 0.0
                
                # Risk factor 1: Low current quality
                if current_quality < 95:
                    risk_score += (95 - current_quality) / 50  # Scale to 0-1
                
                # Risk factor 2: Declining quality trend
                if quality_trend < -0.5:
                    risk_score += abs(quality_trend) / 10
                
                # Risk factor 3: High reject rate
                latest_metric = line_metrics.first()
                if latest_metric.reject_count > 0:
                    reject_rate = latest_metric.reject_count / max(latest_metric.actual_count, 1)
                    risk_score += reject_rate * 2
                
                risk_score = min(risk_score, 1.0)  # Cap at 100%
                
                # Mock quality explanations
                explanations = {
                    'risk_factors': [],
                    'quality_trend': quality_trend,
                    'current_quality': current_quality,
                    'recommendations': []
                }
                
                if current_quality < 95:
                    explanations['risk_factors'].append(f'Quality below target: {current_quality:.1f}%')
                    explanations['recommendations'].append('Review quality control parameters')
                
                if quality_trend < -0.5:
                    explanations['risk_factors'].append(f'Declining quality trend: {quality_trend:.2f}%/hour')
                    explanations['recommendations'].append('Investigate process drift')
                
                # Store quality risk prediction
                MLInference.objects.create(
                    timestamp=now,
                    line_id=line_id,
                    model_name='quality_risk_monitor_v1',
                    prediction_type='quality_prediction',
                    prediction_value=risk_score,
                    confidence_score=0.78,
                    explanation_data=explanations
                )
                
                # Send to WebSocket for RiskHalo3D visualization
                async_to_sync(channel_layer.group_send)(
                    "ml_predictions",
                    {
                        "type": "quality_risk",
                        "data": {
                            "line_id": line_id,
                            "risk_score": risk_score,
                            "quality_current": current_quality,
                            "quality_trend": quality_trend,
                            "explanations": explanations,
                            "timestamp": now.isoformat()
                        }
                    }
                )
        
        logger.info(f"Quality risk scores calculated for {len(line_ids)} lines") 
        return f"Quality risks calculated for {len(line_ids)} lines"
        
    except Exception as exc:
        logger.error(f"Error calculating quality risk: {exc}")
        raise