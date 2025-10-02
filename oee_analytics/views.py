from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import *
from oee_analytics.events.models import DowntimeEvent
from django.utils import timezone
from datetime import timedelta
from .tasks import (
    process_machine_event, calculate_oee_metrics, generate_fake_event,
    extract_ml_features, run_downtime_prediction, calculate_oee_forecast, quality_risk_scoring
)

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

def threejs_dashboard(request):
    """Three.js version of the dashboard - identical recreation"""
    return render(request, 'oee_analytics/threejs_dashboard.html')

def threejs_dashboard_clone(request):
    """Clone of Three.js dashboard for development"""
    return render(request, 'oee_analytics/threejs_dashboard_clone.html')

def dataflow_monitor(request):
    """Data flow monitoring dashboard for separate screen display"""
    return render(request, 'oee_analytics/dataflow_monitor.html')

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


# =====================================
# ML API ENDPOINTS (Phase 2)
# =====================================

@api_view(['GET'])
def ml_forecast_oee(request):
    """API endpoint: /api/ml/forecast/oee"""
    line_id = request.GET.get('line_id', 'LINE_1')
    horizon_hours = int(request.GET.get('horizon', 8))
    
    # Get latest forecast from MLInference
    latest_forecast = MLInference.objects.filter(
        line_id=line_id,
        prediction_type='oee_forecast',
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).order_by('-timestamp').first()
    
    if latest_forecast and latest_forecast.explanation_data.get('forecast_series'):
        return Response({
            'line_id': line_id,
            'forecast_data': latest_forecast.explanation_data['forecast_series'][:horizon_hours],
            'model_name': latest_forecast.model_name,
            'timestamp': latest_forecast.timestamp.isoformat(),
            'confidence': latest_forecast.confidence_score
        })
    
    # Trigger forecast generation if no recent data
    calculate_oee_forecast.delay()
    return Response({
        'line_id': line_id,
        'message': 'Forecast generation triggered, please retry in 30 seconds',
        'status': 'generating'
    })


@api_view(['GET']) 
def ml_score_quality(request):
    """API endpoint: /api/ml/score/quality"""
    line_id = request.GET.get('line_id', 'LINE_1')
    
    # Get latest quality risk score
    latest_score = MLInference.objects.filter(
        line_id=line_id,
        prediction_type='quality_prediction',
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).order_by('-timestamp').first()
    
    if latest_score:
        return Response({
            'line_id': line_id,
            'risk_score': latest_score.prediction_value,
            'confidence': latest_score.confidence_score,
            'explanations': latest_score.explanation_data,
            'timestamp': latest_score.timestamp.isoformat(),
            'model_name': latest_score.model_name
        })
    
    # Trigger quality scoring if no recent data
    quality_risk_scoring.delay()
    return Response({
        'line_id': line_id,
        'message': 'Quality scoring triggered, please retry in 30 seconds',
        'status': 'generating'
    })


@api_view(['GET'])
def ml_predict_downtime(request):
    """API endpoint: /api/ml/predict/downtime"""
    line_id = request.GET.get('line_id', 'LINE_1')
    
    # Get latest downtime prediction
    latest_prediction = MLInference.objects.filter(
        line_id=line_id,
        prediction_type='downtime_probability',
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).order_by('-timestamp').first()
    
    if latest_prediction:
        return Response({
            'line_id': line_id,
            'downtime_probability': latest_prediction.prediction_value,
            'confidence': latest_prediction.confidence_score,
            'explanations': latest_prediction.explanation_data,
            'timestamp': latest_prediction.timestamp.isoformat(),
            'model_name': latest_prediction.model_name
        })
    
    # Trigger prediction if no recent data
    run_downtime_prediction.delay()
    return Response({
        'line_id': line_id,
        'message': 'Downtime prediction triggered, please retry in 30 seconds',
        'status': 'generating'
    })


@api_view(['GET'])
def ml_explain_prediction(request):
    """API endpoint: /api/ml/explain"""
    line_id = request.GET.get('line_id', 'LINE_1')
    prediction_type = request.GET.get('type', 'downtime_probability')
    
    # Get latest prediction with explanations
    latest_prediction = MLInference.objects.filter(
        line_id=line_id,
        prediction_type=prediction_type,
        timestamp__gte=timezone.now() - timedelta(hours=2)
    ).order_by('-timestamp').first()
    
    if latest_prediction and latest_prediction.explanation_data:
        return Response({
            'line_id': line_id,
            'prediction_type': prediction_type,
            'prediction_value': latest_prediction.prediction_value,
            'confidence': latest_prediction.confidence_score,
            'explanations': latest_prediction.explanation_data,
            'timestamp': latest_prediction.timestamp.isoformat(),
            'model_name': latest_prediction.model_name
        })
    
    return Response({
        'line_id': line_id,
        'prediction_type': prediction_type,
        'message': 'No recent predictions with explanations found',
        'status': 'no_data'
    })


@api_view(['GET'])
def ml_features_current(request):
    """API endpoint: /api/ml/features/current"""
    line_id = request.GET.get('line_id', 'LINE_1')
    
    # Get latest features for the line
    latest_features = MLFeatureStore.objects.filter(
        line_id=line_id,
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).order_by('-timestamp')
    
    features_dict = {}
    for feature in latest_features:
        features_dict[feature.feature_name] = {
            'value': feature.feature_value,
            'type': feature.feature_type,
            'timestamp': feature.timestamp.isoformat()
        }
    
    if features_dict:
        return Response({
            'line_id': line_id,
            'features': features_dict,
            'feature_count': len(features_dict)
        })
    
    # Trigger feature extraction if no recent data
    extract_ml_features.delay()
    return Response({
        'line_id': line_id,
        'message': 'Feature extraction triggered, please retry in 30 seconds',
        'status': 'generating'
    })


@api_view(['POST'])
def ml_trigger_pipeline(request):
    """API endpoint: /api/ml/trigger - Trigger complete ML pipeline"""
    
    # Trigger all ML tasks in sequence
    extract_ml_features.delay()
    run_downtime_prediction.delay()
    calculate_oee_forecast.delay()
    quality_risk_scoring.delay()
    
    return Response({
        'status': 'success',
        'message': 'Complete ML pipeline triggered',
        'tasks': [
            'extract_ml_features',
            'run_downtime_prediction', 
            'calculate_oee_forecast',
            'quality_risk_scoring'
        ]
    })
