"""
Django Management Command: Run OEE Calculations
Real-time OEE calculation engine for manufacturing analytics
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.utils import timezone
from django.conf import settings
import time
import logging
import threading
from datetime import datetime, timedelta
import signal
import sys


class Command(BaseCommand):
    help = 'Run real-time OEE calculations and data processing'
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.calculation_thread = None
        self.rollup_thread = None
        self.logger = self._setup_logging()
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Calculation interval in seconds (default: 30)'
        )
        
        parser.add_argument(
            '--rollup-interval',
            type=int,
            default=300,  # 5 minutes
            help='Rollup calculation interval in seconds (default: 300)'
        )
        
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run as daemon process'
        )
        
        parser.add_argument(
            '--log-level',
            type=str,
            default='INFO',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            help='Logging level'
        )
        
        parser.add_argument(
            '--machines',
            type=str,
            help='Comma-separated list of machine IDs to process (default: all)'
        )
    
    def handle(self, *args, **options):
        self.interval = options['interval']
        self.rollup_interval = options['rollup_interval']
        self.daemon = options['daemon']
        self.machine_filter = options['machines'].split(',') if options['machines'] else None
        
        # Set logging level
        log_level = getattr(logging, options['log_level'])
        self.logger.setLevel(log_level)
        
        self.logger.info(f'Starting OEE calculation engine')
        self.logger.info(f'Calculation interval: {self.interval} seconds')
        self.logger.info(f'Rollup interval: {self.rollup_interval} seconds')
        
        if self.machine_filter:
            self.logger.info(f'Processing machines: {", ".join(self.machine_filter)}')
        else:
            self.logger.info('Processing all active machines')
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            self._start_calculation_engine()
        except KeyboardInterrupt:
            self.logger.info('Received interrupt signal')
        except Exception as e:
            self.logger.error(f'Calculation engine failed: {str(e)}')
            raise CommandError(f'OEE calculation engine failed: {str(e)}')
        finally:
            self._stop_calculation_engine()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logger = logging.getLogger('oee_calculations')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f'Received signal {signum}, shutting down...')
        self.running = False
    
    def _start_calculation_engine(self):
        """Start the OEE calculation engine"""
        self.running = True
        
        # Start calculation thread
        self.calculation_thread = threading.Thread(
            target=self._calculation_worker,
            name='OEE-Calculator'
        )
        self.calculation_thread.daemon = True
        self.calculation_thread.start()
        
        # Start rollup thread
        self.rollup_thread = threading.Thread(
            target=self._rollup_worker,
            name='OEE-Rollup'
        )
        self.rollup_thread.daemon = True
        self.rollup_thread.start()
        
        if self.daemon:
            # Run as daemon
            while self.running:
                time.sleep(1)
        else:
            # Interactive mode - show status
            self._interactive_mode()
    
    def _stop_calculation_engine(self):
        """Stop the calculation engine gracefully"""
        self.logger.info('Stopping OEE calculation engine...')
        self.running = False
        
        if self.calculation_thread and self.calculation_thread.is_alive():
            self.calculation_thread.join(timeout=10)
        
        if self.rollup_thread and self.rollup_thread.is_alive():
            self.rollup_thread.join(timeout=10)
        
        self.logger.info('OEE calculation engine stopped')
    
    def _calculation_worker(self):
        """Worker thread for real-time OEE calculations"""
        self.logger.info('Starting OEE calculation worker')
        
        while self.running:
            try:
                start_time = time.time()
                
                # Calculate real-time OEE for active machines
                machines_processed = self._calculate_realtime_oee()
                
                execution_time = time.time() - start_time
                self.logger.debug(
                    f'Processed {machines_processed} machines in {execution_time:.2f}s'
                )
                
                # Log performance if slow
                if execution_time > self.interval * 0.8:
                    self.logger.warning(
                        f'OEE calculation took {execution_time:.2f}s (target: {self.interval}s)'
                    )
                
                # Sleep until next interval
                sleep_time = max(0, self.interval - execution_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f'Error in calculation worker: {str(e)}')
                time.sleep(self.interval)
    
    def _rollup_worker(self):
        """Worker thread for rollup calculations"""
        self.logger.info('Starting rollup calculation worker')
        
        while self.running:
            try:
                start_time = time.time()
                
                # Calculate hourly rollups
                self._calculate_hourly_rollups()
                
                # Calculate shift rollups if needed
                self._calculate_shift_rollups()
                
                execution_time = time.time() - start_time
                self.logger.debug(f'Rollup calculations completed in {execution_time:.2f}s')
                
                # Sleep until next interval
                sleep_time = max(0, self.rollup_interval - execution_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f'Error in rollup worker: {str(e)}')
                time.sleep(self.rollup_interval)
    
    def _calculate_realtime_oee(self):
        """Calculate real-time OEE for all active machines"""
        connection = connections['default']
        machines_processed = 0
        
        try:
            with connection.cursor() as cursor:
                # Get active machines
                if self.machine_filter:
                    machine_filter_sql = "AND machine_id IN ({})".format(
                        ','.join(['%s'] * len(self.machine_filter))
                    )
                    cursor.execute(
                        f"SELECT machine_id FROM dbo.Machines WHERE is_active = 1 {machine_filter_sql}",
                        self.machine_filter
                    )
                else:
                    cursor.execute("SELECT machine_id FROM dbo.Machines WHERE is_active = 1")
                
                machines = [row[0] for row in cursor.fetchall()]
                
                # Calculate OEE for each machine
                for machine_id in machines:
                    try:
                        cursor.execute(
                            "EXEC dbo.sp_CalculateRealTimeOEE @MachineId = %s",
                            [machine_id]
                        )
                        
                        # Fetch result
                        result = cursor.fetchone()
                        if result:
                            oee_percent = result[12]  # OEE percentage from stored procedure
                            
                            # Log low OEE alerts
                            if hasattr(settings, 'OEE_REALTIME_CONFIG'):
                                low_threshold = settings.OEE_REALTIME_CONFIG.get('LOW_OEE_THRESHOLD', 60.0)
                                if oee_percent < low_threshold:
                                    self.logger.warning(
                                        f'Low OEE alert: {machine_id} = {oee_percent:.1f}%'
                                    )
                        
                        machines_processed += 1
                        
                    except Exception as e:
                        self.logger.error(f'Error calculating OEE for {machine_id}: {str(e)}')
                
        except Exception as e:
            self.logger.error(f'Error in real-time OEE calculation: {str(e)}')
        
        return machines_processed
    
    def _calculate_hourly_rollups(self):
        """Calculate hourly rollups"""
        connection = connections['default']
        
        try:
            with connection.cursor() as cursor:
                # Calculate rollups for last completed hour
                cursor.execute("EXEC dbo.sp_CalculateHourlyRollups")
                
                # Get result
                result = cursor.fetchone()
                if result:
                    rows_affected = result[0]
                    self.logger.debug(f'Hourly rollups: {rows_affected} rows processed')
                
        except Exception as e:
            self.logger.error(f'Error calculating hourly rollups: {str(e)}')
    
    def _calculate_shift_rollups(self):
        """Calculate shift rollups when needed"""
        connection = connections['default']
        
        try:
            # Only calculate shift rollups at specific times (e.g., end of shifts)
            current_hour = timezone.now().hour
            if current_hour in [6, 14, 22]:  # End of shifts
                with connection.cursor() as cursor:
                    cursor.execute("EXEC dbo.sp_CalculateShiftRollups")
                    
                    result = cursor.fetchone()
                    if result:
                        rows_affected = result[0]
                        self.logger.info(f'Shift rollups: {rows_affected} rows processed')
                
        except Exception as e:
            self.logger.error(f'Error calculating shift rollups: {str(e)}')
    
    def _interactive_mode(self):
        """Interactive mode with status display"""
        self.stdout.write('\nOEE Calculation Engine Status')
        self.stdout.write('Press Ctrl+C to stop\n')
        
        last_status_time = 0
        status_interval = 30  # Show status every 30 seconds
        
        while self.running:
            current_time = time.time()
            
            if current_time - last_status_time >= status_interval:
                self._display_status()
                last_status_time = current_time
            
            time.sleep(1)
    
    def _display_status(self):
        """Display current status"""
        try:
            connection = connections['default']
            
            with connection.cursor() as cursor:
                # Get current shift OEE summary
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_machines,
                        AVG(current_oee_percent) as avg_oee,
                        MIN(current_oee_percent) as min_oee,
                        MAX(current_oee_percent) as max_oee,
                        SUM(CASE WHEN oee_status = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count
                    FROM dbo.vw_CurrentShiftOEE
                """)
                
                result = cursor.fetchone()
                if result:
                    total, avg_oee, min_oee, max_oee, critical = result
                    
                    self.stdout.write(f'\n[{timezone.now().strftime("%H:%M:%S")}] Status:')
                    self.stdout.write(f'  Machines: {total}')
                    self.stdout.write(f'  Avg OEE: {avg_oee:.1f}%')
                    self.stdout.write(f'  Range: {min_oee:.1f}% - {max_oee:.1f}%')
                    
                    if critical > 0:
                        self.stdout.write(
                            self.style.ERROR(f'  Critical alerts: {critical}')
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS('  All systems normal')
                        )
                
                # Show recent events count
                cursor.execute("""
                    SELECT COUNT(*) FROM dbo.MachineEvents 
                    WHERE timestamp_utc >= DATEADD(MINUTE, -5, GETUTCDATE())
                """)
                
                event_count = cursor.fetchone()[0]
                self.stdout.write(f'  Events (5min): {event_count}')
                
        except Exception as e:
            self.logger.error(f'Error displaying status: {str(e)}')
    
    def _check_database_health(self):
        """Check database connectivity and performance"""
        try:
            connection = connections['default']
            
            with connection.cursor() as cursor:
                start_time = time.time()
                cursor.execute("SELECT 1")
                response_time = (time.time() - start_time) * 1000
                
                if response_time > 1000:  # 1 second
                    self.logger.warning(
                        f'Slow database response: {response_time:.0f}ms'
                    )
                
                return True
                
        except Exception as e:
            self.logger.error(f'Database health check failed: {str(e)}')
            return False