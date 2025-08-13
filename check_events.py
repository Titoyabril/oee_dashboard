#!/usr/bin/env python
import os
import sys
import django

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oee_dashboard.settings')

# Setup Django
django.setup()

from oee_analytics.events.models import DowntimeEvent

# Check total events
total = DowntimeEvent.objects.count()
print(f'Total events: {total}')

# Show recent events
print('\nRecent events:')
for event in DowntimeEvent.objects.order_by('-ts')[:5]:
    print(f'  {event.ts} - {event.reason} ({event.duration_s}s) - Line: {event.line_id}')