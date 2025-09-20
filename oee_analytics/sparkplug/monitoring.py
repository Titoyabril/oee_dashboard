"""
Sparkplug B Monitoring and Health Checks
Production-grade monitoring, metrics, and health check implementation
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import psutil
import threading
from collections import defaultdict, deque

from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from django.db import connection
from django.utils import timezone as django_timezone

from .models import (
    SparkplugNode, SparkplugDevice, SparkplugEventRaw, 
    SparkplugMetricHistory, SparkplugNodeState
)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None


@dataclass
class SystemMetrics:
    """System performance metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    process_count: int
    uptime_seconds: float


class PrometheusMetrics:
    """Prometheus metrics for Sparkplug B system"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        
        # Connection metrics
        self.mqtt_connected = Gauge(
            'sparkplug_mqtt_connected',
            'MQTT connection status (1=connected, 0=disconnected)',
            registry=self.registry
        )
        
        self.active_nodes = Gauge(
            'sparkplug_active_nodes',
            'Number of active Sparkplug nodes',
            registry=self.registry
        )
        
        self.active_devices = Gauge(
            'sparkplug_active_devices', 
            'Number of active Sparkplug devices',
            registry=self.registry
        )
        
        self.plc_connections = Gauge(
            'sparkplug_plc_connections',
            'Number of active PLC connections',
            ['plc_type'],
            registry=self.registry
        )
        
        # Message metrics
        self.messages_received = Counter(
            'sparkplug_messages_received_total',
            'Total Sparkplug messages received',
            ['message_type', 'group_id', 'node_id'],
            registry=self.registry
        )
        
        self.messages_processed = Counter(
            'sparkplug_messages_processed_total',
            'Total messages successfully processed',
            ['message_type'],
            registry=self.registry
        )
        
        self.messages_failed = Counter(
            'sparkplug_messages_failed_total', 
            'Total messages that failed processing',
            ['message_type', 'error_type'],
            registry=self.registry
        )
        
        self.message_processing_time = Histogram(
            'sparkplug_message_processing_seconds',
            'Time spent processing messages',
            ['message_type'],
            registry=self.registry
        )
        
        self.message_queue_size = Gauge(
            'sparkplug_message_queue_size',
            'Current message queue size',
            registry=self.registry
        )
        
        # Data quality metrics
        self.sequence_errors = Counter(
            'sparkplug_sequence_errors_total',
            'Sequence number errors detected',
            ['group_id', 'node_id'],
            registry=self.registry
        )
        
        self.data_quality_score = Histogram(
            'sparkplug_data_quality_score',
            'Data quality scores (0-100)',
            ['metric_type'],
            registry=self.registry
        )
        
        self.message_latency = Histogram(
            'sparkplug_message_latency_seconds',
            'Message latency from timestamp to processing',
            ['message_type'],
            registry=self.registry
        )
        
        # Database metrics
        self.database_operations = Counter(
            'sparkplug_database_operations_total',
            'Database operations performed',
            ['operation', 'table'],
            registry=self.registry
        )
        
        self.database_errors = Counter(
            'sparkplug_database_errors_total',
            'Database operation errors',
            ['operation', 'error_type'],
            registry=self.registry
        )
        
        self.database_query_time = Histogram(
            'sparkplug_database_query_seconds',
            'Database query execution time',
            ['operation'],
            registry=self.registry
        )
        
        # OEE processing metrics
        self.oee_cycles_created = Counter(
            'sparkplug_oee_cycles_created_total',
            'Production cycles created',
            ['machine_id'],
            registry=self.registry
        )
        
        self.oee_events_created = Counter(
            'sparkplug_oee_events_created_total',
            'OEE events created',
            ['event_type', 'machine_id'],
            registry=self.registry
        )
        
        self.oee_processing_lag = Gauge(
            'sparkplug_oee_processing_lag_seconds',
            'OEE data processing lag',
            registry=self.registry
        )
        
        # System metrics
        self.system_cpu_percent = Gauge(
            'sparkplug_system_cpu_percent',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_percent = Gauge(
            'sparkplug_system_memory_percent',
            'System memory usage percentage',
            registry=self.registry
        )
        
        self.system_disk_percent = Gauge(
            'sparkplug_system_disk_percent',
            'System disk usage percentage',
            registry=self.registry
        )
        
        # Health check metrics
        self.health_check_status = Gauge(
            'sparkplug_health_check_status',
            'Health check status (1=healthy, 0=unhealthy)',
            ['check_name'],
            registry=self.registry
        )
        
        self.health_check_duration = Histogram(
            'sparkplug_health_check_duration_seconds',
            'Health check execution time',
            ['check_name'],
            registry=self.registry
        )


class HealthChecker:
    """Health check manager for Sparkplug B system"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, HealthCheck] = {}
        self.check_interval = 30.0  # seconds
        self.running = False
        self.check_task: Optional[asyncio.Task] = None
        
    def register_check(self, name: str, check_func: Callable, interval: Optional[float] = None):
        """Register a health check function"""
        self.checks[name] = {
            'func': check_func,
            'interval': interval or self.check_interval,
            'last_run': 0
        }
        self.logger.info(f"Registered health check: {name}")
    
    async def start(self):
        """Start the health check loop"""
        self.running = True
        self.check_task = asyncio.create_task(self._check_loop())
        self.logger.info("Health checker started")
    
    async def stop(self):
        """Stop the health check loop"""
        self.running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Health checker stopped")
    
    async def _check_loop(self):
        """Main health check loop"""
        while self.running:
            try:
                current_time = time.time()
                
                for name, check_config in self.checks.items():
                    # Check if it's time to run this check
                    if current_time - check_config['last_run'] >= check_config['interval']:
                        await self._run_check(name, check_config)
                        check_config['last_run'] = current_time
                
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(10.0)
    
    async def _run_check(self, name: str, check_config: Dict[str, Any]):
        """Run a single health check"""
        start_time = time.time()
        
        try:
            check_func = check_config['func']
            
            # Run the check function
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            # Ensure result is a HealthCheck object
            if not isinstance(result, HealthCheck):
                result = HealthCheck(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    message=str(result),
                    timestamp=datetime.now(timezone.utc)
                )
            
            duration_ms = (time.time() - start_time) * 1000
            result.duration_ms = duration_ms
            
            self.last_results[name] = result
            
            # Log status changes
            previous = self.last_results.get(f"{name}_previous")
            if not previous or previous.status != result.status:
                self.logger.info(f"Health check {name}: {result.status.value} - {result.message}")
                self.last_results[f"{name}_previous"] = result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_result = HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {e}",
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms
            )
            self.last_results[name] = error_result
            self.logger.error(f"Health check {name} failed: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        if not self.last_results:
            return {
                'status': HealthStatus.UNKNOWN.value,
                'message': 'No health checks performed',
                'checks': {}
            }
        
        # Determine overall status
        statuses = [check.status for check in self.last_results.values() 
                   if not check.name.endswith('_previous')]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        # Build response
        checks = {}
        for name, check in self.last_results.items():
            if not name.endswith('_previous'):
                checks[name] = {
                    'status': check.status.value,
                    'message': check.message,
                    'timestamp': check.timestamp.isoformat(),
                    'duration_ms': check.duration_ms,
                    'details': check.details
                }
        
        return {
            'status': overall_status.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': checks
        }


class SparkplugMonitor:
    """Comprehensive monitoring for Sparkplug B system"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.metrics = PrometheusMetrics()
        self.health_checker = HealthChecker(logger)
        
        # Performance tracking
        self.message_rates = defaultdict(lambda: deque(maxlen=60))  # 1 minute window
        self.error_rates = defaultdict(lambda: deque(maxlen=60))
        self.processing_times = defaultdict(lambda: deque(maxlen=100))
        
        # Alerting
        self.alert_callbacks: List[Callable] = []
        self.alert_thresholds = {
            'message_rate_low': 1.0,      # messages per second
            'error_rate_high': 0.05,      # 5% error rate
            'processing_time_high': 5.0,  # seconds
            'queue_size_high': 1000,      # messages
            'memory_usage_high': 90.0,    # percent
            'disk_usage_high': 90.0,      # percent
        }
        
        # Register standard health checks
        self._register_standard_checks()
    
    async def start(self):
        """Start monitoring"""
        await self.health_checker.start()
        self.logger.info("Sparkplug monitoring started")
    
    async def stop(self):
        """Stop monitoring"""
        await self.health_checker.stop()
        self.logger.info("Sparkplug monitoring stopped")
    
    def _register_standard_checks(self):
        """Register standard health checks"""
        self.health_checker.register_check('database', self._check_database)
        self.health_checker.register_check('system_resources', self._check_system_resources)
        self.health_checker.register_check('sparkplug_nodes', self._check_sparkplug_nodes)
        self.health_checker.register_check('data_freshness', self._check_data_freshness)
        self.health_checker.register_check('processing_lag', self._check_processing_lag)
    
    def _check_database(self) -> HealthCheck:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            if result[0] != 1:
                return HealthCheck(
                    name='database',
                    status=HealthStatus.UNHEALTHY,
                    message='Database query returned unexpected result',
                    timestamp=datetime.now(timezone.utc)
                )
            
            # Check connection pool
            pool_info = connection.get_connection_params()
            
            query_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name='database',
                status=HealthStatus.HEALTHY,
                message=f'Database responsive ({query_time:.1f}ms)',
                timestamp=datetime.now(timezone.utc),
                details={
                    'query_time_ms': query_time,
                    'connection_params': pool_info
                }
            )
            
        except Exception as e:
            return HealthCheck(
                name='database',
                status=HealthStatus.UNHEALTHY,
                message=f'Database connection failed: {e}',
                timestamp=datetime.now(timezone.utc)
            )
    
    def _check_system_resources(self) -> HealthCheck:
        """Check system resource usage"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Update Prometheus metrics
            self.metrics.system_cpu_percent.set(cpu_percent)
            self.metrics.system_memory_percent.set(memory.percent)
            self.metrics.system_disk_percent.set(disk.percent)
            
            # Check thresholds
            issues = []
            if cpu_percent > 90:
                issues.append(f'High CPU usage: {cpu_percent:.1f}%')
            if memory.percent > self.alert_thresholds['memory_usage_high']:
                issues.append(f'High memory usage: {memory.percent:.1f}%')
            if disk.percent > self.alert_thresholds['disk_usage_high']:
                issues.append(f'High disk usage: {disk.percent:.1f}%')
            
            if issues:
                status = HealthStatus.DEGRADED if len(issues) < 2 else HealthStatus.UNHEALTHY
                message = '; '.join(issues)
            else:
                status = HealthStatus.HEALTHY
                message = f'System resources OK (CPU: {cpu_percent:.1f}%, Memory: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%)'
            
            return HealthCheck(
                name='system_resources',
                status=status,
                message=message,
                timestamp=datetime.now(timezone.utc),
                details={
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'disk_percent': disk.percent,
                    'memory_available_mb': memory.available // 1024 // 1024,
                    'disk_free_gb': disk.free // 1024 // 1024 // 1024
                }
            )
            
        except Exception as e:
            return HealthCheck(
                name='system_resources',
                status=HealthStatus.UNHEALTHY,
                message=f'Failed to check system resources: {e}',
                timestamp=datetime.now(timezone.utc)
            )
    
    def _check_sparkplug_nodes(self) -> HealthCheck:
        """Check Sparkplug node health"""
        try:
            # Count active nodes
            active_nodes = SparkplugNode.objects.filter(
                status__in=['ONLINE', 'BIRTH'],
                is_active=True
            ).count()
            
            # Count stale nodes (no data in last 5 minutes)
            stale_threshold = django_timezone.now() - timedelta(minutes=5)
            stale_nodes = SparkplugNode.objects.filter(
                status__in=['ONLINE', 'BIRTH'],
                is_active=True,
                last_data_timestamp__lt=stale_threshold
            ).count()
            
            # Update metrics
            self.metrics.active_nodes.set(active_nodes)
            
            if active_nodes == 0:
                status = HealthStatus.UNHEALTHY
                message = 'No active Sparkplug nodes'
            elif stale_nodes > 0:
                status = HealthStatus.DEGRADED
                message = f'{stale_nodes} nodes have stale data (total active: {active_nodes})'
            else:
                status = HealthStatus.HEALTHY
                message = f'{active_nodes} active nodes, all current'
            
            return HealthCheck(
                name='sparkplug_nodes',
                status=status,
                message=message,
                timestamp=datetime.now(timezone.utc),
                details={
                    'active_nodes': active_nodes,
                    'stale_nodes': stale_nodes
                }
            )
            
        except Exception as e:
            return HealthCheck(
                name='sparkplug_nodes',
                status=HealthStatus.UNHEALTHY,
                message=f'Failed to check Sparkplug nodes: {e}',
                timestamp=datetime.now(timezone.utc)
            )
    
    def _check_data_freshness(self) -> HealthCheck:
        """Check data freshness"""
        try:
            # Check most recent metric data
            latest_metric = SparkplugMetricHistory.objects.order_by('-timestamp_utc').first()
            
            if not latest_metric:
                return HealthCheck(
                    name='data_freshness',
                    status=HealthStatus.UNHEALTHY,
                    message='No metric data found',
                    timestamp=datetime.now(timezone.utc)
                )
            
            # Calculate age of latest data
            data_age = django_timezone.now() - latest_metric.timestamp_utc
            age_minutes = data_age.total_seconds() / 60
            
            if age_minutes > 10:
                status = HealthStatus.UNHEALTHY
                message = f'Latest data is {age_minutes:.1f} minutes old'
            elif age_minutes > 5:
                status = HealthStatus.DEGRADED
                message = f'Latest data is {age_minutes:.1f} minutes old'
            else:
                status = HealthStatus.HEALTHY
                message = f'Data is fresh ({age_minutes:.1f} minutes old)'
            
            return HealthCheck(
                name='data_freshness',
                status=status,
                message=message,
                timestamp=datetime.now(timezone.utc),
                details={
                    'latest_data_age_minutes': age_minutes,
                    'latest_data_timestamp': latest_metric.timestamp_utc.isoformat()
                }
            )
            
        except Exception as e:
            return HealthCheck(
                name='data_freshness',
                status=HealthStatus.UNHEALTHY,
                message=f'Failed to check data freshness: {e}',
                timestamp=datetime.now(timezone.utc)
            )
    
    def _check_processing_lag(self) -> HealthCheck:
        """Check processing lag"""
        try:
            # Get unprocessed message count
            unprocessed_count = SparkplugEventRaw.objects.filter(processed=False).count()
            
            # Check oldest unprocessed message
            oldest_unprocessed = SparkplugEventRaw.objects.filter(
                processed=False
            ).order_by('received_at').first()
            
            if oldest_unprocessed:
                lag_seconds = (django_timezone.now() - oldest_unprocessed.received_at).total_seconds()
                self.metrics.oee_processing_lag.set(lag_seconds)
            else:
                lag_seconds = 0
                self.metrics.oee_processing_lag.set(0)
            
            if unprocessed_count > 1000:
                status = HealthStatus.UNHEALTHY
                message = f'High processing lag: {unprocessed_count} unprocessed messages'
            elif unprocessed_count > 100:
                status = HealthStatus.DEGRADED
                message = f'Moderate processing lag: {unprocessed_count} unprocessed messages'
            else:
                status = HealthStatus.HEALTHY
                message = f'Processing current: {unprocessed_count} unprocessed messages'
            
            return HealthCheck(
                name='processing_lag',
                status=status,
                message=message,
                timestamp=datetime.now(timezone.utc),
                details={
                    'unprocessed_count': unprocessed_count,
                    'lag_seconds': lag_seconds
                }
            )
            
        except Exception as e:
            return HealthCheck(
                name='processing_lag',
                status=HealthStatus.UNHEALTHY,
                message=f'Failed to check processing lag: {e}',
                timestamp=datetime.now(timezone.utc)
            )
    
    def record_message_received(self, message_type: str, group_id: str, node_id: str):
        """Record a message received"""
        self.metrics.messages_received.labels(
            message_type=message_type,
            group_id=group_id,
            node_id=node_id
        ).inc()
        
        # Track rate
        current_time = time.time()
        self.message_rates[message_type].append(current_time)
    
    def record_message_processed(self, message_type: str, processing_time: float):
        """Record a message processed"""
        self.metrics.messages_processed.labels(message_type=message_type).inc()
        self.metrics.message_processing_time.labels(message_type=message_type).observe(processing_time)
        
        # Track processing time
        self.processing_times[message_type].append(processing_time)
    
    def record_message_failed(self, message_type: str, error_type: str):
        """Record a message processing failure"""
        self.metrics.messages_failed.labels(
            message_type=message_type,
            error_type=error_type
        ).inc()
        
        # Track error rate
        current_time = time.time()
        self.error_rates[message_type].append(current_time)
    
    def record_database_operation(self, operation: str, table: str, execution_time: float, success: bool):
        """Record a database operation"""
        self.metrics.database_operations.labels(operation=operation, table=table).inc()
        
        if success:
            self.metrics.database_query_time.labels(operation=operation).observe(execution_time)
        else:
            self.metrics.database_errors.labels(operation=operation, error_type='execution_error').inc()
    
    def get_metrics_text(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest(self.metrics.registry)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary"""
        health_status = self.health_checker.get_health_status()
        
        # Add performance metrics
        performance = {}
        
        # Message rates (per second)
        for msg_type, timestamps in self.message_rates.items():
            if timestamps:
                recent = [t for t in timestamps if time.time() - t < 60]  # Last minute
                performance[f'{msg_type}_rate'] = len(recent) / 60.0
        
        # Error rates
        for msg_type, timestamps in self.error_rates.items():
            if timestamps:
                recent = [t for t in timestamps if time.time() - t < 60]
                performance[f'{msg_type}_error_rate'] = len(recent) / 60.0
        
        # Average processing times
        for msg_type, times in self.processing_times.items():
            if times:
                performance[f'{msg_type}_avg_processing_time'] = sum(times) / len(times)
        
        return {
            **health_status,
            'performance': performance,
            'thresholds': self.alert_thresholds
        }
    
    def add_alert_callback(self, callback: Callable):
        """Add alert callback function"""
        self.alert_callbacks.append(callback)
    
    def check_alerts(self):
        """Check for alert conditions and trigger callbacks"""
        alerts = []
        
        # Check message rates
        for msg_type, timestamps in self.message_rates.items():
            if timestamps:
                recent = [t for t in timestamps if time.time() - t < 60]
                rate = len(recent) / 60.0
                if rate < self.alert_thresholds['message_rate_low']:
                    alerts.append({
                        'type': 'low_message_rate',
                        'message': f'Low message rate for {msg_type}: {rate:.1f}/sec',
                        'severity': 'warning'
                    })
        
        # Trigger alert callbacks
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Alert callback error: {e}")


# HTTP health check endpoint
async def health_check_endpoint(monitor: SparkplugMonitor) -> Dict[str, Any]:
    """HTTP health check endpoint"""
    health_summary = monitor.get_health_summary()
    
    # Determine HTTP status code
    status_code = 200
    if health_summary['status'] == HealthStatus.DEGRADED.value:
        status_code = 200  # Still return 200 for degraded
    elif health_summary['status'] == HealthStatus.UNHEALTHY.value:
        status_code = 503  # Service unavailable for unhealthy
    
    return {
        'status_code': status_code,
        'body': health_summary
    }