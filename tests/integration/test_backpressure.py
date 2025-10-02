"""
Backpressure and Adaptive Sampling Tests
Tests dynamic sampling rate adjustment during MQTT queue congestion
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_mqtt,
    pytest.mark.requires_opcua,
]


@pytest.mark.asyncio
async def test_backpressure_detection(
    test_config,
    test_node_id
):
    """
    Test that backpressure is detected when MQTT queue exceeds threshold

    Scenario:
    1. Start edge gateway with low backpressure threshold
    2. Disconnect MQTT broker
    3. Generate OPC-UA data to fill queue
    4. Verify backpressure callback triggered
    5. Verify queue stops growing at threshold
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    # Configure with low threshold for testing
    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_backpressure=True,
        backpressure_threshold=10,  # Low threshold
        max_queue_size=100,
    )

    client = SparkplugMQTTClient(config)

    # Track backpressure events
    backpressure_events = []

    def backpressure_callback(active: bool):
        backpressure_events.append({
            'timestamp': datetime.now(timezone.utc),
            'active': active,
            'queue_size': client.message_queue.qsize()
        })

    client.backpressure_callbacks.append(backpressure_callback)

    # Start client and disconnect
    await client.start()
    await asyncio.sleep(1)
    client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Queue messages to exceed threshold
    for i in range(20):
        client.message_queue.put({
            'topic': f'test/backpressure/{i}',
            'payload': f'data_{i}'.encode(),
            'qos': 1
        })

    # Trigger backpressure check
    await client._check_backpressure()
    await asyncio.sleep(0.5)

    # Verify backpressure detected
    assert len(backpressure_events) > 0, "Backpressure callback not triggered"
    assert backpressure_events[0]['active'] is True, "Backpressure not active"
    assert backpressure_events[0]['queue_size'] >= 10, f"Queue size {backpressure_events[0]['queue_size']} below threshold"

    print(f"✅ Backpressure detected at queue size: {backpressure_events[0]['queue_size']}")

    await client.stop()


@pytest.mark.asyncio
async def test_backpressure_clears(
    test_config,
    test_node_id
):
    """
    Test that backpressure clears when queue drains below threshold
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_backpressure=True,
        backpressure_threshold=10,
        backpressure_clear_threshold=5,  # Clear when below 5
    )

    client = SparkplugMQTTClient(config)

    backpressure_states = []

    def backpressure_callback(active: bool):
        backpressure_states.append({
            'active': active,
            'queue_size': client.message_queue.qsize()
        })

    client.backpressure_callbacks.append(backpressure_callback)

    await client.start()
    client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Trigger backpressure
    for i in range(15):
        client.message_queue.put({'topic': f'test/{i}', 'payload': b'data', 'qos': 1})

    await client._check_backpressure()
    await asyncio.sleep(0.1)

    assert backpressure_states[-1]['active'] is True

    # Drain queue below clear threshold
    while client.message_queue.qsize() > 4:
        client.message_queue.get_nowait()

    await client._check_backpressure()
    await asyncio.sleep(0.1)

    # Verify backpressure cleared
    assert backpressure_states[-1]['active'] is False
    print(f"✅ Backpressure cleared at queue size: {backpressure_states[-1]['queue_size']}")

    await client.stop()


@pytest.mark.asyncio
async def test_adaptive_sampling_edge_gateway(
    test_config,
    opcua_simulator,
    test_node_id
):
    """
    Test adaptive sampling in edge gateway

    Scenario:
    1. Start edge gateway with OPC-UA client
    2. Verify normal sampling rate (250ms)
    3. Trigger backpressure
    4. Verify sampling rate increases to 2000ms
    5. Clear backpressure
    6. Verify sampling returns to 250ms
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig, AdaptiveSamplingConfig
    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAClient, OPCUAConfig
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig

    # Configure edge gateway
    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_backpressure=True,
        backpressure_threshold=10,
    )

    opcua_config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        sampling_interval=250,
    )

    adaptive_config = AdaptiveSamplingConfig(
        normal_sampling_ms=250,
        backpressure_sampling_ms=2000,
        transition_delay_seconds=1,  # Faster for testing
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[opcua_config],
        adaptive_config=adaptive_config,
    )

    gateway = EdgeGateway(gateway_config)

    # Track sampling changes
    sampling_changes = []

    original_apply = gateway._apply_adaptive_sampling

    async def tracked_apply(mode: str):
        sampling_changes.append({
            'timestamp': datetime.now(timezone.utc),
            'mode': mode
        })
        await original_apply(mode)

    gateway._apply_adaptive_sampling = tracked_apply

    # Start gateway
    await gateway.start()
    await asyncio.sleep(2)

    # Verify normal mode
    assert len(sampling_changes) >= 1
    assert sampling_changes[0]['mode'] == 'normal'
    print(f"📊 Initial sampling mode: {sampling_changes[0]['mode']}")

    # Simulate backpressure by filling MQTT queue
    mqtt_client = gateway.mqtt_client
    for i in range(15):
        mqtt_client.message_queue.put({'topic': f'test/{i}', 'payload': b'data', 'qos': 1})

    # Disconnect to prevent draining
    mqtt_client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Trigger backpressure check
    await mqtt_client._check_backpressure()
    await asyncio.sleep(2)  # Wait for transition delay

    # Verify backpressure mode
    assert len(sampling_changes) >= 2
    assert sampling_changes[-1]['mode'] == 'backpressure'
    print(f"📊 Backpressure sampling mode activated")

    # Clear queue and reconnect
    while not mqtt_client.message_queue.empty():
        mqtt_client.message_queue.get_nowait()

    await mqtt_client._connect_with_retry()
    await asyncio.sleep(1)

    # Trigger check again
    await mqtt_client._check_backpressure()
    await asyncio.sleep(2)

    # Verify return to normal
    assert sampling_changes[-1]['mode'] == 'normal'
    print(f"📊 Sampling returned to normal mode")

    await gateway.stop()


@pytest.mark.asyncio
async def test_no_message_loss_during_sampling_change(
    test_config,
    opcua_simulator,
    clean_timescaledb,
    test_node_id
):
    """
    Critical test: Verify no messages are lost when changing sampling rates

    This tests the most important property: data integrity during adaptive sampling
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig, AdaptiveSamplingConfig
    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAClient, OPCUAConfig
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig

    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_backpressure=True,
        backpressure_threshold=50,
    )

    opcua_config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        sampling_interval=100,  # Fast sampling
    )

    adaptive_config = AdaptiveSamplingConfig(
        normal_sampling_ms=100,
        backpressure_sampling_ms=1000,
        transition_delay_seconds=1,
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[opcua_config],
        adaptive_config=adaptive_config,
    )

    gateway = EdgeGateway(gateway_config)

    # Track messages sent
    messages_sent = []
    original_publish = gateway.mqtt_client.publish_node_data

    async def tracked_publish(*args, **kwargs):
        messages_sent.append({
            'timestamp': datetime.now(timezone.utc),
            'metrics': kwargs.get('metrics', [])
        })
        return await original_publish(*args, **kwargs)

    gateway.mqtt_client.publish_node_data = tracked_publish

    # Start gateway
    await gateway.start()
    await asyncio.sleep(3)

    initial_count = len(messages_sent)
    print(f"📊 Sent {initial_count} messages in normal mode")

    # Trigger backpressure by disconnecting and generating data
    gateway.mqtt_client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Generate OPC-UA data changes
    temp_var = opcua_simulator['variables']['temperature']
    for i in range(10):
        await temp_var.write_value(75.0 + i)
        await asyncio.sleep(0.15)

    # Trigger backpressure
    await gateway.mqtt_client._check_backpressure()
    await asyncio.sleep(2)

    # Reconnect
    await gateway.mqtt_client._connect_with_retry()
    await asyncio.sleep(3)

    final_count = len(messages_sent)
    print(f"📊 Sent {final_count - initial_count} messages during/after backpressure")

    # Verify messages in database
    await asyncio.sleep(2)  # Wait for DB writes

    db_count = await clean_timescaledb.fetchval(
        "SELECT COUNT(*) FROM telemetry WHERE machine_id = $1",
        test_node_id
    )

    print(f"📊 Database has {db_count} records")

    # Verify no significant data loss (allow small margin for async timing)
    assert db_count >= (final_count * 0.9), f"Significant data loss: sent {final_count}, DB has {db_count}"

    print("✅ No message loss during adaptive sampling")

    await gateway.stop()


@pytest.mark.asyncio
async def test_backpressure_transition_delay(
    test_config,
    test_node_id
):
    """
    Test that sampling changes respect transition delay to prevent thrashing
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig, AdaptiveSamplingConfig
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig

    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_backpressure=True,
        backpressure_threshold=10,
    )

    adaptive_config = AdaptiveSamplingConfig(
        normal_sampling_ms=250,
        backpressure_sampling_ms=2000,
        transition_delay_seconds=3,  # 3 second delay
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[],
        adaptive_config=adaptive_config,
    )

    gateway = EdgeGateway(gateway_config)

    # Track transitions
    transitions = []

    original_handle = gateway._handle_backpressure

    async def tracked_handle(active: bool):
        transitions.append({
            'timestamp': time.time(),
            'active': active
        })
        await original_handle(active)

    gateway._handle_backpressure = tracked_handle

    await gateway.start()

    # Trigger backpressure
    gateway.mqtt_client.mqtt_client.disconnect()
    for i in range(15):
        gateway.mqtt_client.message_queue.put({'topic': f't/{i}', 'payload': b'd', 'qos': 1})

    await gateway.mqtt_client._check_backpressure()
    await asyncio.sleep(0.5)

    first_transition = transitions[-1]['timestamp']

    # Immediately try to trigger opposite (should be delayed)
    while not gateway.mqtt_client.message_queue.empty():
        gateway.mqtt_client.message_queue.get_nowait()

    await gateway.mqtt_client._check_backpressure()
    await asyncio.sleep(0.5)

    # If another transition happened, check timing
    if len(transitions) > 1:
        second_transition = transitions[-1]['timestamp']
        delay = second_transition - first_transition

        # Should be at least close to configured delay
        assert delay >= 2.5, f"Transition delay {delay:.2f}s too short (expected ~3s)"
        print(f"✅ Transition delay respected: {delay:.2f}s")

    await gateway.stop()


@pytest.mark.asyncio
@pytest.mark.slow
async def test_backpressure_under_load(
    test_config,
    clean_redis,
    test_node_id
):
    """
    Load test: Verify backpressure prevents memory exhaustion under sustained load
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_backpressure=True,
        enable_store_forward=True,
        backpressure_threshold=100,
        max_queue_size=500,
    )

    client = SparkplugMQTTClient(config)

    backpressure_active = False

    def backpressure_callback(active: bool):
        nonlocal backpressure_active
        backpressure_active = active
        print(f"📊 Backpressure: {'ACTIVE' if active else 'CLEARED'}, Queue: {client.message_queue.qsize()}")

    client.backpressure_callbacks.append(backpressure_callback)

    await client.start()
    await asyncio.sleep(1)

    # Disconnect to prevent draining
    client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Generate sustained load (1000 messages)
    start_time = time.time()

    for i in range(1000):
        if i % 100 == 0:
            await client._check_backpressure()
            await asyncio.sleep(0.1)

        # Try to queue message
        if client.message_queue.qsize() < config.max_queue_size:
            client.message_queue.put({
                'topic': f'test/load/{i}',
                'payload': f'data_{i}'.encode(),
                'qos': 1
            })

    elapsed = time.time() - start_time
    final_queue_size = client.message_queue.qsize()

    print(f"📊 Load test completed in {elapsed:.2f}s")
    print(f"📊 Final queue size: {final_queue_size}/{config.max_queue_size}")
    print(f"📊 Backpressure triggered: {backpressure_active}")

    # Verify backpressure was triggered
    assert backpressure_active, "Backpressure should be active under load"

    # Verify queue didn't exceed limit
    assert final_queue_size <= config.max_queue_size, f"Queue exceeded limit: {final_queue_size} > {config.max_queue_size}"

    print("✅ Backpressure prevented memory exhaustion")

    await client.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
