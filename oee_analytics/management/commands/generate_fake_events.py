import random
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from oee_analytics.events.models import DowntimeEvent


class Command(BaseCommand):
    help = "Generates fake downtime events for testing WebSocket and dashboard"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of events to generate'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='Delay in seconds between events'
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously until stopped'
        )

    def handle(self, *args, **options):
        count = options['count']
        delay = options['delay']
        continuous = options['continuous']
        
        lines = ["LINE_A", "LINE_B", "LINE_C"]
        stations = ["STATION_1", "STATION_2", "STATION_3", "STATION_4", ""]
        reasons = ["BLOCKED", "STARVED", "FAULT", "MANUAL", "CHANGEOVER"]
        sources = ["vision", "plc"]
        details = [
            "Conveyor jam",
            "Material shortage",
            "Sensor fault",
            "Operator intervention",
            "Product changeover",
            "Belt misalignment",
            "Quality check",
            "Emergency stop",
            ""
        ]
        
        self.stdout.write(self.style.SUCCESS(
            f"Starting to generate fake events (continuous={continuous})..."
        ))
        
        events_created = 0
        try:
            while True:
                event = DowntimeEvent.objects.create(
                    ts=timezone.now(),
                    line_id=random.choice(lines),
                    station_id=random.choice(stations),
                    source=random.choice(sources),
                    reason=random.choice(reasons),
                    detail=random.choice(details),
                    duration_s=round(random.uniform(0.5, 120.0), 1),
                    severity=random.randint(1, 5)
                )
                
                events_created += 1
                self.stdout.write(
                    f"Created event #{events_created}: {event.ts.isoformat()} "
                    f"{event.line_id}/{event.station_id} - {event.reason} ({event.duration_s}s)"
                )
                
                if not continuous and events_created >= count:
                    break
                    
                time.sleep(delay)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nStopped by user"))
        
        self.stdout.write(self.style.SUCCESS(
            f"\nGenerated {events_created} downtime events"
        ))