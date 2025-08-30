from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import *
from oee_analytics.events.models import DowntimeEvent
from django.utils import timezone
from datetime import timedelta
from .tasks import process_machine_event, calculate_oee_metrics, generate_fake_event

def home(request):
    """Homepage with gamified OEE overview"""
    # Get current shift data
    context = {
        'current_oee': 85.3,
        'availability': 92.5,
        'performance': 89.1,
        'quality': 95.8,
        'production_count': 2847,
        'target_count': 3000,
        'team_name': 'Team Alpha',
        'shift_name': 'Morning Shift'
    }
    return render(request, 'oee_analytics/home.html', context)

def dashboard(request):
    return render(request, 'oee_analytics/dashboard.html')

def new_dashboard(request):
    """New dashboard with top KPI row"""
    return render(request, 'oee_analytics/new_dashboard.html')

def dash_dashboard(request):
    """Dash/Plotly version of the dashboard"""
    return render(request, 'oee_analytics/dash_dashboard.html')

def current_metrics_api(request):
    """API endpoint for real-time metrics"""
    # Calculate current OEE metrics
    now = timezone.now()
    shift_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
    
    # Get events for current shift
    events = DowntimeEvent.objects.filter(
        ts__gte=shift_start,
        ts__lte=now
    )
    
    # Calculate metrics (simplified)
    total_downtime = sum(event.duration_s for event in events) / 60  # minutes
    shift_duration = (now - shift_start).total_seconds() / 60  # minutes
    
    availability = max(0, (shift_duration - total_downtime) / shift_duration * 100) if shift_duration > 0 else 100
    performance = 89.1  # Mock data - replace with actual calculation
    quality = 95.8     # Mock data - replace with actual calculation
    oee = (availability * performance * quality) / 10000
    
    return JsonResponse({
        'oee': oee,
        'availability': availability,
        'performance': performance,
        'quality': quality,
        'production_count': 2847,  # Mock - replace with actual
        'timestamp': now.isoformat()
    })

@csrf_exempt
def trigger_event_api(request):
    """API endpoint to trigger a test event via Celery"""
    if request.method == 'POST':
        # Trigger fake event generation
        task = generate_fake_event.delay()
        return JsonResponse({
            'status': 'success',
            'task_id': task.id,
            'message': 'Event generation triggered'
        })
    return JsonResponse({'error': 'POST method required'}, status=400)

def trigger_oee_calculation(request):
    """API endpoint to trigger OEE calculation via Celery"""
    task = calculate_oee_metrics.delay()
    return JsonResponse({
        'status': 'success', 
        'task_id': task.id,
        'message': 'OEE calculation triggered'
    })
