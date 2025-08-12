from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from django.utils.dateparse import parse_datetime
from oee_analytics.events.models import DowntimeEvent

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