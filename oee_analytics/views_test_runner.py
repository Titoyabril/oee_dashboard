"""
Test Runner Dashboard Views
Provides UI for executing the 500-point test plan with real-time monitoring
"""

from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
import subprocess
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


# Test phase configuration
TEST_PHASES = [
    {
        'id': 1,
        'name': 'Phase 1: Edge Layer',
        'file': 'test_300_point_phase1_edge_layer.py',
        'tests': 100,
        'description': 'OPC-UA, MQTT Sparkplug B, Direct Drivers, Protocol Selection',
        'critical_tests': 15
    },
    {
        'id': 2,
        'name': 'Phase 2: Processing & Storage',
        'file': 'test_300_point_phase2_processing.py',
        'tests': 100,
        'description': 'Sparkplug Lifecycle, MQTT Broker, Stream Processing, TimescaleDB',
        'critical_tests': 13
    },
    {
        'id': 3,
        'name': 'Phase 3: APIs & Security',
        'file': 'test_300_point_phase3_apis_security.py',
        'tests': 100,
        'description': 'REST/GraphQL, WebSocket, Network Security, Certificates, Access Control',
        'critical_tests': 15
    },
    {
        'id': 4,
        'name': 'Phase 4: Performance & Resilience',
        'file': 'test_300_point_phase4_performance.py',
        'tests': 100,
        'description': 'Throughput, Scale, Resource Utilization, Edge/Broker/Backend Resilience',
        'critical_tests': 10
    },
    {
        'id': 5,
        'name': 'Phase 5: Observability & Quality',
        'file': 'test_300_point_phase5_observability.py',
        'tests': 100,
        'description': 'Metrics, Logging, Tracing, Quality Codes, Data Validation, Clock Sync',
        'critical_tests': 8
    }
]


def test_runner_dashboard(request):
    """Main test runner dashboard view"""
    context = {
        'phases': TEST_PHASES,
        'total_tests': sum(p['tests'] for p in TEST_PHASES),
        'total_critical': sum(p['critical_tests'] for p in TEST_PHASES),
    }
    return render(request, 'test_runner/dashboard.html', context)


@csrf_exempt
def run_test_phase(request):
    """Execute a specific test phase"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        phase_id = data.get('phase_id')

        # Find the phase
        phase = next((p for p in TEST_PHASES if p['id'] == phase_id), None)
        if not phase:
            return JsonResponse({'error': 'Invalid phase ID'}, status=400)

        # Build test file path
        test_dir = Path(__file__).parent.parent / 'tests' / 'integration'
        test_file = test_dir / phase['file']

        if not test_file.exists():
            return JsonResponse({'error': f'Test file not found: {phase["file"]}'}, status=404)

        # Create log directory if needed
        log_dir = test_dir.parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        # Generate log filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'phase{phase_id}_{timestamp}.log'

        # Execute pytest
        cmd = [
            'py', '-m', 'pytest',
            str(test_file),
            '-v', '--tb=short',
            '--color=yes'
        ]

        result = subprocess.run(
            cmd,
            cwd=str(test_dir.parent.parent),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Save output to log file
        with open(log_file, 'w') as f:
            f.write(f"=== Phase {phase_id}: {phase['name']} ===\n")
            f.write(f"Executed: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"Command: {' '.join(cmd)}\n\n")
            f.write("=== STDOUT ===\n")
            f.write(result.stdout)
            f.write("\n\n=== STDERR ===\n")
            f.write(result.stderr)

        # Parse pytest output for results
        output = result.stdout
        passed = output.count(' PASSED')
        failed = output.count(' FAILED')

        # Count only actual pytest warnings (from summary line)
        import re
        warning_match = re.search(r'(\d+)\s+warning', output)
        warnings = int(warning_match.group(1)) if warning_match else 0

        # Extract execution time
        import re
        time_match = re.search(r'in ([\d.]+)s', output)
        execution_time = float(time_match.group(1)) if time_match else 0

        response_data = {
            'success': result.returncode == 0,
            'phase_id': phase_id,
            'phase_name': phase['name'],
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'execution_time': execution_time,
            'log_file': str(log_file.name),
            'output': output,
            'return_code': result.returncode
        }

        return JsonResponse(response_data)

    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'Test execution timeout (5 minutes)'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def run_all_tests(request):
    """Execute all 500 tests"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        # Build test file paths
        test_dir = Path(__file__).parent.parent / 'tests' / 'integration'
        test_files = [str(test_dir / phase['file']) for phase in TEST_PHASES]

        # Create log directory
        log_dir = test_dir.parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        # Generate log filename
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'all_500_tests_{timestamp}.log'

        # Execute all tests
        cmd = [
            'py', '-m', 'pytest',
            *test_files,
            '-v', '--tb=short',
            '--color=yes'
        ]

        result = subprocess.run(
            cmd,
            cwd=str(test_dir.parent.parent),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # Save output
        with open(log_file, 'w') as f:
            f.write("=== ALL 500 TESTS ===\n")
            f.write(f"Executed: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"Command: {' '.join(cmd)}\n\n")
            f.write("=== STDOUT ===\n")
            f.write(result.stdout)
            f.write("\n\n=== STDERR ===\n")
            f.write(result.stderr)

        # Parse results
        output = result.stdout
        passed = output.count(' PASSED')
        failed = output.count(' FAILED')

        # Count only actual pytest warnings (from summary line)
        import re
        warning_match = re.search(r'(\d+)\s+warning', output)
        warnings = int(warning_match.group(1)) if warning_match else 0

        time_match = re.search(r'in ([\d.]+)s', output)
        execution_time = float(time_match.group(1)) if time_match else 0

        response_data = {
            'success': result.returncode == 0,
            'total_tests': 500,
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'execution_time': execution_time,
            'log_file': str(log_file.name),
            'output': output,
            'return_code': result.returncode
        }

        return JsonResponse(response_data)

    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'Test execution timeout (10 minutes)'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_log_file(request):
    """Retrieve a log file"""
    log_name = request.GET.get('file')
    if not log_name:
        return JsonResponse({'error': 'No file specified'}, status=400)

    test_dir = Path(__file__).parent.parent / 'tests'
    log_file = test_dir / 'logs' / log_name

    if not log_file.exists():
        return JsonResponse({'error': 'Log file not found'}, status=404)

    try:
        with open(log_file, 'r') as f:
            content = f.read()
        return JsonResponse({'content': content})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def list_log_files(request):
    """List all available log files"""
    test_dir = Path(__file__).parent.parent / 'tests'
    log_dir = test_dir / 'logs'

    if not log_dir.exists():
        return JsonResponse({'logs': []})

    logs = []
    for log_file in sorted(log_dir.glob('*.log'), reverse=True):
        stat = log_file.stat()
        logs.append({
            'name': log_file.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            'path': str(log_file.name)
        })

    return JsonResponse({'logs': logs})


def get_test_status(request):
    """Get overall test status summary"""
    # This could be enhanced to track running tests, history, etc.
    test_dir = Path(__file__).parent.parent / 'tests' / 'logs'

    latest_log = None
    if test_dir.exists():
        log_files = sorted(test_dir.glob('all_500_tests_*.log'), reverse=True)
        if log_files:
            latest_log = log_files[0].name

    return JsonResponse({
        'phases': TEST_PHASES,
        'total_tests': 500,
        'total_critical': 71,
        'latest_log': latest_log
    })
