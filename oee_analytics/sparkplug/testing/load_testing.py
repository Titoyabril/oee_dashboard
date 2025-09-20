"""
Sparkplug B Load Testing Utilities
Performance testing and load generation for Sparkplug B MQTT systems
"""

import asyncio
import time
import random
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading
from queue import Queue
import statistics

import paho.mqtt.client as mqtt
from eclipse_tahu.core import sparkplug_b_pb2
from eclipse_tahu.core.sparkplug_b import SparkplugMessageBuilder
import numpy as np


@dataclass
class LoadTestConfig:
    """Configuration for load testing"""
    # MQTT broker settings
    broker_host: str = "localhost"
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = False
    
    # Test parameters
    num_nodes: int = 10
    num_devices_per_node: int = 5
    num_metrics_per_device: int = 20
    
    # Message rates
    birth_interval: float = 300.0  # seconds
    data_interval: float = 1.0     # seconds
    burst_mode: bool = False
    burst_size: int = 100
    burst_interval: float = 10.0
    
    # Test duration
    test_duration: float = 300.0   # seconds
    ramp_up_time: float = 60.0     # seconds
    
    # Message patterns
    message_types: List[str] = field(default_factory=lambda: ["NDATA", "DDATA"])
    quality_distribution: Dict[str, float] = field(default_factory=lambda: {
        "good": 0.95,
        "uncertain": 0.03,
        "bad": 0.02
    })
    
    # Performance targets
    target_latency_ms: float = 100.0
    target_throughput_msg_sec: float = 1000.0
    max_memory_mb: float = 512.0


@dataclass
class LoadTestResults:
    """Results from load testing"""
    # Test configuration
    config: LoadTestConfig
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    
    # Message statistics
    messages_sent: int = 0
    messages_confirmed: int = 0
    messages_failed: int = 0
    
    # Performance metrics
    latencies_ms: List[float] = field(default_factory=list)
    throughput_msg_sec: List[float] = field(default_factory=list)
    memory_usage_mb: List[float] = field(default_factory=list)
    cpu_usage_percent: List[float] = field(default_factory=list)
    
    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def avg_latency_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0
    
    @property
    def p95_latency_ms(self) -> float:
        return np.percentile(self.latencies_ms, 95) if self.latencies_ms else 0.0
    
    @property
    def p99_latency_ms(self) -> float:
        return np.percentile(self.latencies_ms, 99) if self.latencies_ms else 0.0
    
    @property
    def avg_throughput_msg_sec(self) -> float:
        return statistics.mean(self.throughput_msg_sec) if self.throughput_msg_sec else 0.0
    
    @property
    def success_rate(self) -> float:
        total = self.messages_sent
        return (self.messages_confirmed / total * 100) if total > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        total = self.messages_sent
        return (self.messages_failed / total * 100) if total > 0 else 0.0


class SparkplugLoadTester:
    """Load tester for Sparkplug B MQTT systems"""
    
    def __init__(self, config: LoadTestConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # MQTT clients pool
        self.mqtt_clients: List[mqtt.Client] = []
        self.client_pool_size = min(50, max(1, config.num_nodes // 5))
        
        # Test state
        self.running = False
        self.start_time: Optional[datetime] = None
        self.results = LoadTestResults(
            config=config,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            duration_seconds=0.0
        )
        
        # Message tracking
        self.message_queue = Queue()
        self.sent_messages: Dict[str, float] = {}  # message_id -> timestamp
        self.lock = threading.Lock()
        
        # Performance monitoring
        self.performance_samples = []
        self.executor = ThreadPoolExecutor(max_workers=self.client_pool_size)
        
        # Sparkplug message builder
        self.message_builder = SparkplugMessageBuilder()
    
    async def run_load_test(self) -> LoadTestResults:
        """Run the complete load test"""
        try:
            self.logger.info("Starting Sparkplug B load test")
            self.results.start_time = datetime.now(timezone.utc)
            self.start_time = time.time()
            self.running = True
            
            # Initialize MQTT clients
            await self._initialize_clients()
            
            # Start monitoring
            monitor_task = asyncio.create_task(self._monitor_performance())
            
            # Send birth messages
            await self._send_birth_messages()
            
            # Run main test
            test_task = asyncio.create_task(self._run_test_scenario())
            
            # Wait for test completion
            await test_task
            
            # Send death messages
            await self._send_death_messages()
            
            # Stop monitoring
            monitor_task.cancel()
            
            # Finalize results
            self._finalize_results()
            
            self.logger.info("Load test completed")
            return self.results
            
        except Exception as e:
            self.logger.error(f"Load test failed: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def _initialize_clients(self):
        """Initialize MQTT client pool"""
        self.logger.info(f"Initializing {self.client_pool_size} MQTT clients")
        
        for i in range(self.client_pool_size):
            client = mqtt.Client(f"load_test_client_{i}")
            
            # Set credentials
            if self.config.username and self.config.password:
                client.username_pw_set(self.config.username, self.config.password)
            
            # Set callbacks
            client.on_publish = self._on_publish
            client.on_log = self._on_log
            
            # Connect
            try:
                client.connect(self.config.broker_host, self.config.broker_port, 60)
                client.loop_start()
                self.mqtt_clients.append(client)
                
            except Exception as e:
                self.logger.error(f"Failed to connect client {i}: {e}")
        
        self.logger.info(f"Connected {len(self.mqtt_clients)} MQTT clients")
    
    async def _send_birth_messages(self):
        """Send node and device birth messages"""
        self.logger.info("Sending birth messages")
        
        for node_id in range(self.config.num_nodes):
            group_id = "LoadTest"
            node_name = f"Node_{node_id:03d}"
            
            # Send node birth
            await self._send_node_birth(group_id, node_name)
            
            # Send device births
            for device_id in range(self.config.num_devices_per_node):
                device_name = f"Device_{device_id:03d}"
                await self._send_device_birth(group_id, node_name, device_name)
            
            # Small delay to avoid overwhelming
            await asyncio.sleep(0.1)
    
    async def _send_node_birth(self, group_id: str, node_id: str):
        """Send node birth message"""
        try:
            # Create metrics for node
            metrics = []
            for i in range(5):  # 5 node-level metrics
                metrics.append({
                    'name': f'Node_Metric_{i}',
                    'alias': 1000 + i,
                    'value': random.uniform(0, 100),
                    'datatype': sparkplug_b_pb2.Double
                })
            
            # Create birth payload
            payload = self.message_builder.create_node_birth_payload(
                timestamp=int(time.time() * 1000),
                metrics=metrics
            )
            
            # Publish
            topic = f"spBv1.0/{group_id}/NBIRTH/{node_id}"
            await self._publish_message(topic, payload, "NBIRTH")
            
        except Exception as e:
            self.logger.error(f"Failed to send node birth for {node_id}: {e}")
    
    async def _send_device_birth(self, group_id: str, node_id: str, device_id: str):
        """Send device birth message"""
        try:
            # Create metrics for device
            metrics = []
            for i in range(self.config.num_metrics_per_device):
                metric_type = random.choice([
                    sparkplug_b_pb2.Double,
                    sparkplug_b_pb2.Float,
                    sparkplug_b_pb2.Int32,
                    sparkplug_b_pb2.Boolean
                ])
                
                if metric_type == sparkplug_b_pb2.Boolean:
                    value = random.choice([True, False])
                elif metric_type in [sparkplug_b_pb2.Int32]:
                    value = random.randint(0, 1000)
                else:
                    value = random.uniform(0, 100)
                
                metrics.append({
                    'name': f'Device_Metric_{i}',
                    'alias': 2000 + i,
                    'value': value,
                    'datatype': metric_type
                })
            
            # Create birth payload
            payload = self.message_builder.create_device_birth_payload(
                timestamp=int(time.time() * 1000),
                metrics=metrics
            )
            
            # Publish
            topic = f"spBv1.0/{group_id}/DBIRTH/{device_id}"
            await self._publish_message(topic, payload, "DBIRTH")
            
        except Exception as e:
            self.logger.error(f"Failed to send device birth for {device_id}: {e}")
    
    async def _run_test_scenario(self):
        """Run the main test scenario"""
        self.logger.info("Starting main test scenario")
        
        test_start = time.time()
        ramp_up_end = test_start + self.config.ramp_up_time
        test_end = test_start + self.config.test_duration
        
        # Create tasks for different message types
        tasks = []
        
        if self.config.burst_mode:
            # Burst mode
            task = asyncio.create_task(self._burst_message_loop(test_start, test_end))
            tasks.append(task)
        else:
            # Steady rate mode
            if "NDATA" in self.config.message_types:
                task = asyncio.create_task(self._ndata_message_loop(test_start, test_end, ramp_up_end))
                tasks.append(task)
            
            if "DDATA" in self.config.message_types:
                task = asyncio.create_task(self._ddata_message_loop(test_start, test_end, ramp_up_end))
                tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.logger.info("Main test scenario completed")
    
    async def _ndata_message_loop(self, test_start: float, test_end: float, ramp_up_end: float):
        """Send NDATA messages continuously"""
        node_seq = {}
        
        while time.time() < test_end and self.running:
            current_time = time.time()
            
            # Calculate current rate (ramp up)
            if current_time < ramp_up_end:
                rate_factor = (current_time - test_start) / self.config.ramp_up_time
            else:
                rate_factor = 1.0
            
            current_interval = self.config.data_interval / rate_factor if rate_factor > 0 else self.config.data_interval
            
            # Send messages for each node
            for node_id in range(self.config.num_nodes):
                group_id = "LoadTest"
                node_name = f"Node_{node_id:03d}"
                
                # Track sequence number
                if node_name not in node_seq:
                    node_seq[node_name] = 0
                node_seq[node_name] += 1
                
                # Create NDATA message
                await self._send_ndata_message(group_id, node_name, node_seq[node_name])
            
            await asyncio.sleep(current_interval)
    
    async def _ddata_message_loop(self, test_start: float, test_end: float, ramp_up_end: float):
        """Send DDATA messages continuously"""
        device_seq = {}
        
        while time.time() < test_end and self.running:
            current_time = time.time()
            
            # Calculate current rate (ramp up)
            if current_time < ramp_up_end:
                rate_factor = (current_time - test_start) / self.config.ramp_up_time
            else:
                rate_factor = 1.0
            
            current_interval = self.config.data_interval / rate_factor if rate_factor > 0 else self.config.data_interval
            
            # Send messages for random devices
            for _ in range(self.config.num_nodes * self.config.num_devices_per_node // 10):
                node_id = random.randint(0, self.config.num_nodes - 1)
                device_id = random.randint(0, self.config.num_devices_per_node - 1)
                
                group_id = "LoadTest"
                node_name = f"Node_{node_id:03d}"
                device_name = f"Device_{device_id:03d}"
                
                # Track sequence number
                device_key = f"{node_name}/{device_name}"
                if device_key not in device_seq:
                    device_seq[device_key] = 0
                device_seq[device_key] += 1
                
                # Create DDATA message
                await self._send_ddata_message(group_id, node_name, device_name, device_seq[device_key])
            
            await asyncio.sleep(current_interval)
    
    async def _burst_message_loop(self, test_start: float, test_end: float):
        """Send messages in bursts"""
        while time.time() < test_end and self.running:
            # Send burst
            for _ in range(self.config.burst_size):
                node_id = random.randint(0, self.config.num_nodes - 1)
                device_id = random.randint(0, self.config.num_devices_per_node - 1)
                
                group_id = "LoadTest"
                node_name = f"Node_{node_id:03d}"
                device_name = f"Device_{device_id:03d}"
                
                await self._send_ddata_message(group_id, node_name, device_name, 1)
            
            # Wait for next burst
            await asyncio.sleep(self.config.burst_interval)
    
    async def _send_ndata_message(self, group_id: str, node_id: str, sequence: int):
        """Send NDATA message"""
        try:
            # Create random metrics
            metrics = []
            for i in range(3):  # 3 metrics per NDATA
                quality = self._get_random_quality()
                metrics.append({
                    'name': f'Runtime_Metric_{i}',
                    'value': random.uniform(0, 100),
                    'datatype': sparkplug_b_pb2.Double,
                    'quality': quality
                })
            
            # Create data payload
            payload = self.message_builder.create_node_data_payload(
                timestamp=int(time.time() * 1000),
                seq=sequence,
                metrics=metrics
            )
            
            # Publish
            topic = f"spBv1.0/{group_id}/NDATA/{node_id}"
            await self._publish_message(topic, payload, "NDATA")
            
        except Exception as e:
            self.logger.error(f"Failed to send NDATA for {node_id}: {e}")
    
    async def _send_ddata_message(self, group_id: str, node_id: str, device_id: str, sequence: int):
        """Send DDATA message"""
        try:
            # Create random metrics
            metrics = []
            num_metrics = random.randint(1, 5)
            
            for i in range(num_metrics):
                quality = self._get_random_quality()
                metric_type = random.choice([
                    sparkplug_b_pb2.Double,
                    sparkplug_b_pb2.Float,
                    sparkplug_b_pb2.Int32,
                    sparkplug_b_pb2.Boolean
                ])
                
                if metric_type == sparkplug_b_pb2.Boolean:
                    value = random.choice([True, False])
                elif metric_type == sparkplug_b_pb2.Int32:
                    value = random.randint(0, 1000)
                else:
                    value = random.uniform(0, 100)
                
                metrics.append({
                    'alias': 2000 + i,
                    'value': value,
                    'datatype': metric_type,
                    'quality': quality
                })
            
            # Create data payload
            payload = self.message_builder.create_device_data_payload(
                timestamp=int(time.time() * 1000),
                seq=sequence,
                metrics=metrics
            )
            
            # Publish
            topic = f"spBv1.0/{group_id}/DDATA/{device_id}"
            await self._publish_message(topic, payload, "DDATA")
            
        except Exception as e:
            self.logger.error(f"Failed to send DDATA for {device_id}: {e}")
    
    def _get_random_quality(self) -> int:
        """Get random quality value based on distribution"""
        rand = random.random()
        if rand < self.config.quality_distribution["good"]:
            return 192  # Good quality
        elif rand < self.config.quality_distribution["good"] + self.config.quality_distribution["uncertain"]:
            return 64   # Uncertain quality
        else:
            return 0    # Bad quality
    
    async def _publish_message(self, topic: str, payload: bytes, message_type: str):
        """Publish message using available client"""
        try:
            if not self.mqtt_clients:
                return
            
            # Select random client
            client = random.choice(self.mqtt_clients)
            
            # Generate message ID for tracking
            message_id = f"{topic}_{time.time()}_{random.randint(1000, 9999)}"
            
            # Record send time
            send_time = time.time()
            with self.lock:
                self.sent_messages[message_id] = send_time
                self.results.messages_sent += 1
            
            # Publish
            result = client.publish(topic, payload, qos=1)
            
            # Handle immediate errors
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                with self.lock:
                    self.results.messages_failed += 1
                    self.results.errors.append({
                        'timestamp': datetime.now(timezone.utc),
                        'type': 'publish_error',
                        'message': f"Publish failed: {result.rc}",
                        'topic': topic,
                        'message_type': message_type
                    })
            
        except Exception as e:
            with self.lock:
                self.results.messages_failed += 1
                self.results.errors.append({
                    'timestamp': datetime.now(timezone.utc),
                    'type': 'exception',
                    'message': str(e),
                    'topic': topic,
                    'message_type': message_type
                })
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        try:
            confirm_time = time.time()
            
            with self.lock:
                self.results.messages_confirmed += 1
                
                # Calculate latency (simplified - we don't have exact message mapping)
                if self.sent_messages:
                    # Use most recent send time as approximation
                    latest_send_time = max(self.sent_messages.values())
                    latency_ms = (confirm_time - latest_send_time) * 1000
                    self.results.latencies_ms.append(latency_ms)
                    
                    # Clean up old entries
                    cutoff_time = confirm_time - 60  # Keep last minute
                    self.sent_messages = {
                        k: v for k, v in self.sent_messages.items() 
                        if v > cutoff_time
                    }
            
        except Exception as e:
            self.logger.error(f"Error in publish callback: {e}")
    
    def _on_log(self, client, userdata, level, buf):
        """MQTT log callback"""
        if level == mqtt.MQTT_LOG_ERR:
            with self.lock:
                self.results.errors.append({
                    'timestamp': datetime.now(timezone.utc),
                    'type': 'mqtt_error',
                    'message': buf
                })
    
    async def _monitor_performance(self):
        """Monitor system performance during test"""
        try:
            import psutil
            
            while self.running:
                # Collect performance metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                # Calculate throughput
                current_time = time.time()
                if hasattr(self, '_last_monitor_time'):
                    time_delta = current_time - self._last_monitor_time
                    msg_delta = self.results.messages_sent - getattr(self, '_last_msg_count', 0)
                    throughput = msg_delta / time_delta if time_delta > 0 else 0
                    
                    self.results.throughput_msg_sec.append(throughput)
                
                self._last_monitor_time = current_time
                self._last_msg_count = self.results.messages_sent
                
                # Store metrics
                self.results.cpu_usage_percent.append(cpu_percent)
                self.results.memory_usage_mb.append(memory.used / 1024 / 1024)
                
                await asyncio.sleep(5.0)  # Monitor every 5 seconds
                
        except ImportError:
            self.logger.warning("psutil not available, skipping performance monitoring")
        except Exception as e:
            self.logger.error(f"Performance monitoring error: {e}")
    
    async def _send_death_messages(self):
        """Send death messages"""
        self.logger.info("Sending death messages")
        
        for node_id in range(self.config.num_nodes):
            group_id = "LoadTest"
            node_name = f"Node_{node_id:03d}"
            
            # Send device deaths first
            for device_id in range(self.config.num_devices_per_node):
                device_name = f"Device_{device_id:03d}"
                await self._send_device_death(group_id, node_name, device_name)
            
            # Send node death
            await self._send_node_death(group_id, node_name)
            
            await asyncio.sleep(0.1)
    
    async def _send_node_death(self, group_id: str, node_id: str):
        """Send node death message"""
        try:
            payload = self.message_builder.create_node_death_payload(
                timestamp=int(time.time() * 1000)
            )
            
            topic = f"spBv1.0/{group_id}/NDEATH/{node_id}"
            await self._publish_message(topic, payload, "NDEATH")
            
        except Exception as e:
            self.logger.error(f"Failed to send node death for {node_id}: {e}")
    
    async def _send_device_death(self, group_id: str, node_id: str, device_id: str):
        """Send device death message"""
        try:
            payload = self.message_builder.create_device_death_payload(
                timestamp=int(time.time() * 1000)
            )
            
            topic = f"spBv1.0/{group_id}/DDEATH/{device_id}"
            await self._publish_message(topic, payload, "DDEATH")
            
        except Exception as e:
            self.logger.error(f"Failed to send device death for {device_id}: {e}")
    
    def _finalize_results(self):
        """Finalize test results"""
        self.results.end_time = datetime.now(timezone.utc)
        self.results.duration_seconds = time.time() - self.start_time
        
        # Log summary
        self.logger.info(f"Load test summary:")
        self.logger.info(f"  Duration: {self.results.duration_seconds:.1f} seconds")
        self.logger.info(f"  Messages sent: {self.results.messages_sent}")
        self.logger.info(f"  Messages confirmed: {self.results.messages_confirmed}")
        self.logger.info(f"  Success rate: {self.results.success_rate:.1f}%")
        self.logger.info(f"  Average latency: {self.results.avg_latency_ms:.1f} ms")
        self.logger.info(f"  P95 latency: {self.results.p95_latency_ms:.1f} ms")
        self.logger.info(f"  Average throughput: {self.results.avg_throughput_msg_sec:.1f} msg/sec")
        self.logger.info(f"  Errors: {len(self.results.errors)}")
    
    async def _cleanup(self):
        """Cleanup resources"""
        self.running = False
        
        # Disconnect MQTT clients
        for client in self.mqtt_clients:
            try:
                client.loop_stop()
                client.disconnect()
            except:
                pass
        
        self.mqtt_clients.clear()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)


# Convenience functions for common test scenarios
async def run_basic_load_test(broker_host: str = "localhost", duration: float = 60.0) -> LoadTestResults:
    """Run a basic load test with default settings"""
    config = LoadTestConfig(
        broker_host=broker_host,
        test_duration=duration,
        num_nodes=5,
        num_devices_per_node=3,
        data_interval=2.0
    )
    
    tester = SparkplugLoadTester(config)
    return await tester.run_load_test()


async def run_burst_load_test(broker_host: str = "localhost", duration: float = 120.0) -> LoadTestResults:
    """Run a burst load test"""
    config = LoadTestConfig(
        broker_host=broker_host,
        test_duration=duration,
        num_nodes=20,
        num_devices_per_node=5,
        burst_mode=True,
        burst_size=200,
        burst_interval=10.0
    )
    
    tester = SparkplugLoadTester(config)
    return await tester.run_load_test()


async def run_high_volume_test(broker_host: str = "localhost", duration: float = 300.0) -> LoadTestResults:
    """Run a high volume load test"""
    config = LoadTestConfig(
        broker_host=broker_host,
        test_duration=duration,
        num_nodes=50,
        num_devices_per_node=10,
        num_metrics_per_device=50,
        data_interval=0.5,
        ramp_up_time=120.0
    )
    
    tester = SparkplugLoadTester(config)
    return await tester.run_load_test()


def analyze_test_results(results: LoadTestResults) -> Dict[str, Any]:
    """Analyze test results and provide recommendations"""
    analysis = {
        'performance_grade': 'A',
        'issues': [],
        'recommendations': [],
        'metrics': {
            'success_rate': results.success_rate,
            'avg_latency_ms': results.avg_latency_ms,
            'p95_latency_ms': results.p95_latency_ms,
            'avg_throughput': results.avg_throughput_msg_sec,
            'error_count': len(results.errors)
        }
    }
    
    # Analyze success rate
    if results.success_rate < 95:
        analysis['performance_grade'] = 'D'
        analysis['issues'].append(f"Low success rate: {results.success_rate:.1f}%")
        analysis['recommendations'].append("Check broker capacity and network connectivity")
    elif results.success_rate < 99:
        analysis['performance_grade'] = 'C'
        analysis['issues'].append(f"Moderate success rate: {results.success_rate:.1f}%")
    
    # Analyze latency
    if results.p95_latency_ms > results.config.target_latency_ms * 2:
        analysis['performance_grade'] = 'D'
        analysis['issues'].append(f"High P95 latency: {results.p95_latency_ms:.1f} ms")
        analysis['recommendations'].append("Optimize message processing and reduce broker load")
    elif results.p95_latency_ms > results.config.target_latency_ms:
        if analysis['performance_grade'] == 'A':
            analysis['performance_grade'] = 'B'
        analysis['issues'].append(f"Elevated P95 latency: {results.p95_latency_ms:.1f} ms")
    
    # Analyze throughput
    if results.avg_throughput_msg_sec < results.config.target_throughput_msg_sec * 0.5:
        analysis['performance_grade'] = 'D'
        analysis['issues'].append(f"Low throughput: {results.avg_throughput_msg_sec:.1f} msg/sec")
        analysis['recommendations'].append("Scale up broker resources or optimize client connections")
    
    # Analyze errors
    if len(results.errors) > results.messages_sent * 0.05:  # More than 5% errors
        analysis['performance_grade'] = 'D'
        analysis['issues'].append(f"High error count: {len(results.errors)}")
        analysis['recommendations'].append("Investigate error patterns and fix underlying issues")
    
    return analysis