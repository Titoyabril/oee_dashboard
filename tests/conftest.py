"""
Pytest Configuration and Shared Fixtures for OEE Analytics Tests
"""

import os
import sys
import pytest
import asyncio
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# ========================================
# Event Loop Configuration
# ========================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ========================================
# Environment Configuration
# ========================================

@pytest.fixture(scope="session")
def test_config():
    """Test environment configuration"""
    return {
        'mqtt_broker': os.getenv('TEST_MQTT_BROKER', 'localhost'),
        'mqtt_port': int(os.getenv('TEST_MQTT_PORT', '1883')),
        'mqtt_port_ssl': int(os.getenv('TEST_MQTT_PORT_SSL', '8883')),
        'timescale_host': os.getenv('TEST_TIMESCALE_HOST', 'localhost'),
        'timescale_port': int(os.getenv('TEST_TIMESCALE_PORT', '5432')),
        'timescale_db': os.getenv('TEST_TIMESCALE_DB', 'oee_analytics_test'),
        'timescale_user': os.getenv('TEST_TIMESCALE_USER', 'oeeuser'),
        'timescale_password': os.getenv('TEST_TIMESCALE_PASSWORD', 'OEE_Analytics2024!'),
        'redis_host': os.getenv('TEST_REDIS_HOST', 'localhost'),
        'redis_port': int(os.getenv('TEST_REDIS_PORT', '6379')),
        'cert_dir': Path(__file__).parent.parent / 'docker' / 'compose' / 'certs',
    }


@pytest.fixture(scope="session")
def test_certs(test_config):
    """Test certificate paths"""
    cert_dir = test_config['cert_dir']
    return {
        'ca_cert': cert_dir / 'ca.crt',
        'client_cert': cert_dir / 'client_edge_TEST.crt',
        'client_key': cert_dir / 'client_edge_TEST.key',
    }


# ========================================
# Database Fixtures
# ========================================

@pytest.fixture(scope="session")
async def timescaledb_connection(test_config):
    """TimescaleDB connection for tests"""
    import asyncpg

    conn = await asyncpg.connect(
        host=test_config['timescale_host'],
        port=test_config['timescale_port'],
        database=test_config['timescale_db'],
        user=test_config['timescale_user'],
        password=test_config['timescale_password'],
    )

    yield conn

    await conn.close()


@pytest.fixture(scope="function")
async def clean_timescaledb(timescaledb_connection):
    """Clean TimescaleDB before each test"""
    conn = timescaledb_connection

    # Truncate test tables
    await conn.execute("TRUNCATE TABLE telemetry, events RESTART IDENTITY CASCADE")

    yield conn

    # Cleanup after test
    await conn.execute("TRUNCATE TABLE telemetry, events RESTART IDENTITY CASCADE")


# ========================================
# Redis Fixtures
# ========================================

@pytest.fixture(scope="session")
async def redis_connection(test_config):
    """Redis connection for tests"""
    import redis.asyncio as redis

    client = redis.Redis(
        host=test_config['redis_host'],
        port=test_config['redis_port'],
        db=15,  # Use separate DB for tests
        decode_responses=True
    )

    yield client

    await client.close()


@pytest.fixture(scope="function")
async def clean_redis(redis_connection):
    """Clean Redis before each test"""
    await redis_connection.flushdb()
    yield redis_connection
    await redis_connection.flushdb()


# ========================================
# MQTT Fixtures
# ========================================

@pytest.fixture(scope="session")
def mqtt_test_client(test_config):
    """MQTT test client (synchronous)"""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(client_id="test_client")
    client.connect(test_config['mqtt_broker'], test_config['mqtt_port'], 60)
    client.loop_start()

    yield client

    client.loop_stop()
    client.disconnect()


@pytest.fixture(scope="function")
async def mqtt_test_client_async(test_config):
    """MQTT test client (async)"""
    import asyncio_mqtt

    async with asyncio_mqtt.Client(
        hostname=test_config['mqtt_broker'],
        port=test_config['mqtt_port']
    ) as client:
        yield client


# ========================================
# Sparkplug Fixtures
# ========================================

@pytest.fixture(scope="session")
def sparkplug_message_builder():
    """Sparkplug message builder - simplified implementation for testing"""
    import struct

    class SimpleSparkplugBuilder:
        """Simplified Sparkplug message builder for testing"""

        def create_node_birth_payload(self, timestamp, metrics, seq):
            """Create NBIRTH payload"""
            # For testing, return a simple encoded dict
            payload = {
                'timestamp': timestamp,
                'metrics': metrics,
                'seq': seq
            }
            import json
            return json.dumps(payload).encode()

        def create_node_data_payload(self, timestamp, metrics, seq):
            """Create NDATA payload"""
            payload = {
                'timestamp': timestamp,
                'metrics': metrics,
                'seq': seq
            }
            import json
            return json.dumps(payload).encode()

        def create_device_birth_payload(self, timestamp, metrics, seq):
            """Create DBIRTH payload"""
            payload = {
                'timestamp': timestamp,
                'metrics': metrics,
                'seq': seq
            }
            import json
            return json.dumps(payload).encode()

        def create_device_data_payload(self, timestamp, metrics, seq):
            """Create DDATA payload"""
            payload = {
                'timestamp': timestamp,
                'metrics': metrics,
                'seq': seq
            }
            import json
            return json.dumps(payload).encode()

    return SimpleSparkplugBuilder()


@pytest.fixture(scope="function")
def test_node_id():
    """Generate unique test node ID"""
    import uuid
    return f"test_node_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def test_device_id():
    """Generate unique test device ID"""
    import uuid
    return f"test_device_{uuid.uuid4().hex[:8]}"


# ========================================
# OPC-UA Fixtures
# ========================================

@pytest.fixture(scope="session")
async def opcua_simulator():
    """OPC-UA simulator for testing"""
    from asyncua import Server
    import asyncio

    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/oeetest/")
    server.set_server_name("OEE Test Server")

    # Create test namespace
    uri = "http://oee.test"
    idx = await server.register_namespace(uri)

    # Create test objects
    objects = server.get_objects_node()
    test_obj = await objects.add_object(idx, "TestMachine")

    # Add test variables
    production_count = await test_obj.add_variable(idx, "ProductionCount", 0)
    good_count = await test_obj.add_variable(idx, "GoodCount", 0)
    machine_state = await test_obj.add_variable(idx, "MachineState", "IDLE")
    temperature = await test_obj.add_variable(idx, "Temperature", 75.0)

    # Make writable
    await production_count.set_writable()
    await good_count.set_writable()
    await machine_state.set_writable()
    await temperature.set_writable()

    async with server:
        yield {
            'server': server,
            'namespace': idx,
            'variables': {
                'production_count': production_count,
                'good_count': good_count,
                'machine_state': machine_state,
                'temperature': temperature,
            }
        }


# ========================================
# Test Data Generators
# ========================================

@pytest.fixture
def generate_sparkplug_metrics():
    """Generator for Sparkplug metrics"""
    def _generate(num_metrics=10):
        import time
        metrics = []
        for i in range(num_metrics):
            metrics.append({
                'name': f'metric_{i}',
                'alias': i,
                'timestamp': int(time.time() * 1000),
                'datatype': 3,  # Int32
                'value': i * 100,
            })
        return metrics
    return _generate


@pytest.fixture
def generate_telemetry_data():
    """Generator for telemetry data"""
    from datetime import datetime, timedelta, timezone

    def _generate(machine_id='TEST_MACHINE', num_points=100, interval_seconds=1):
        import random
        data = []
        base_time = datetime.now(timezone.utc)

        for i in range(num_points):
            timestamp = base_time + timedelta(seconds=i * interval_seconds)
            data.append({
                'time': timestamp,
                'machine_id': machine_id,
                'metric_name': 'temperature',
                'value': 70.0 + random.uniform(-5, 5),
                'quality': 192,
            })

        return data

    return _generate


# ========================================
# Performance Measurement
# ========================================

@pytest.fixture
def measure_latency():
    """Measure latency for performance tests"""
    import time

    class LatencyMeasurement:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.measurements = []

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()
            latency = (self.end_time - self.start_time) * 1000  # ms
            self.measurements.append(latency)
            return latency

        def get_stats(self):
            import statistics
            return {
                'count': len(self.measurements),
                'min': min(self.measurements),
                'max': max(self.measurements),
                'mean': statistics.mean(self.measurements),
                'median': statistics.median(self.measurements),
                'p95': statistics.quantiles(self.measurements, n=20)[18] if len(self.measurements) > 20 else None,
                'p99': statistics.quantiles(self.measurements, n=100)[98] if len(self.measurements) > 100 else None,
            }

    return LatencyMeasurement()


# ========================================
# Pytest Configuration
# ========================================

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "load: mark test as load/performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_mqtt: mark test as requiring MQTT broker"
    )
    config.addinivalue_line(
        "markers", "requires_timescaledb: mark test as requiring TimescaleDB"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    # Add markers automatically based on test file location
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        if "load" in str(item.fspath):
            item.add_marker(pytest.mark.load)
