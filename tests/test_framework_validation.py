"""
Test Framework Validation
Simple tests to verify pytest and fixtures are working correctly
"""

import pytest
import asyncio


def test_pytest_working():
    """Verify pytest is configured correctly"""
    assert True


@pytest.mark.asyncio
async def test_async_working():
    """Verify async test support is working"""
    await asyncio.sleep(0.1)
    assert True


def test_fixtures_config(test_config):
    """Verify test_config fixture works"""
    assert 'mqtt_broker' in test_config
    assert 'timescale_host' in test_config
    assert 'redis_host' in test_config
    print(f"\n[OK] Test config loaded: MQTT={test_config['mqtt_broker']}")


def test_sparkplug_message_builder(sparkplug_message_builder):
    """Verify sparkplug_message_builder fixture works"""
    import time

    # Test NBIRTH
    payload = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )

    assert payload is not None
    assert isinstance(payload, bytes)
    print(f"\n[OK] SparkplugMessageBuilder working")


def test_node_id_generator(test_node_id):
    """Verify test_node_id fixture generates unique IDs"""
    assert test_node_id.startswith('test_node_')
    assert len(test_node_id) > 10
    print(f"\n[OK] Generated test node ID: {test_node_id}")


def test_device_id_generator(test_device_id):
    """Verify test_device_id fixture generates unique IDs"""
    assert test_device_id.startswith('test_device_')
    assert len(test_device_id) > 10
    print(f"\n[OK] Generated test device ID: {test_device_id}")


def test_telemetry_generator(generate_telemetry_data):
    """Verify telemetry data generator fixture"""
    data = generate_telemetry_data(machine_id='TEST', num_points=10)

    assert len(data) == 10
    assert all('time' in d for d in data)
    assert all('machine_id' in d for d in data)
    assert all('value' in d for d in data)
    print(f"\n[OK] Generated {len(data)} telemetry data points")


def test_latency_measurement(measure_latency):
    """Verify latency measurement fixture"""
    import time

    measure_latency.start()
    time.sleep(0.1)
    latency = measure_latency.stop()

    assert latency >= 100  # Should be at least 100ms
    assert latency < 200   # Should be less than 200ms
    print(f"\n[OK] Latency measurement: {latency:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
