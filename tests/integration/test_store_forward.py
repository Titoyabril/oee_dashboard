"""
Store-and-Forward Resilience Tests
Tests edge gateway behavior during broker outages and reconnection
"""

import pytest
import asyncio
import time
import subprocess
from datetime import datetime, timezone

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_mqtt,
    pytest.mark.requires_redis,
]


@pytest.mark.asyncio
async def test_store_forward_broker_outage(
    test_config,
    clean_redis,
    test_node_id
):
    """
    Test that messages are queued to Redis when broker is unavailable

    Scenario:
    1. Start edge gateway
    2. Stop MQTT broker
    3. Publish messages (should queue to Redis)
    4. Verify queue in Redis
    5. Start broker
    6. Verify messages replayed
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig
    from oee_analytics.edge.cache import EdgeCache, CacheConfig

    # 1. Configure edge gateway with store-and-forward
    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_store_forward=True,
        store_forward_max_size_mb=100,
    )

    client = SparkplugMQTTClient(config)

    # Verify edge cache is initialized
    assert client.edge_cache is not None, "Edge cache not initialized"

    # 2. Start client (connect to broker)
    success = await client.start()
    assert success, "Failed to start MQTT client"

    # Give it time to connect
    await asyncio.sleep(2)
    assert client.connected, "Client not connected to broker"

    initial_stats = client.get_statistics()
    print(f"\n📊 Initial Stats: {initial_stats}")

    # 3. Simulate broker outage (disconnect)
    client.mqtt_client.disconnect()
    await asyncio.sleep(1)
    assert not client.connected, "Client still showing as connected"

    # 4. Try to publish messages while broker is down
    num_messages = 10
    for i in range(num_messages):
        topic = f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}"
        payload = f"test_message_{i}".encode()

        # Queue message for later delivery
        await client._queue_message_for_later(topic, payload, qos=1)

    # 5. Verify messages are in Redis cache
    queued_count = await clean_redis.llen('oee:queue:mqtt')
    print(f"📦 Messages queued in Redis: {queued_count}")
    assert queued_count == num_messages, f"Expected {num_messages} queued, got {queued_count}"

    # 6. Verify statistics updated
    stats = client.get_statistics()
    assert stats['messages_queued'] == num_messages

    # 7. Reconnect to broker
    await client._connect_with_retry()
    await asyncio.sleep(2)
    assert client.connected, "Client failed to reconnect"

    # 8. Trigger replay
    await client._replay_stored_messages()
    await asyncio.sleep(1)

    # 9. Verify queue drained
    remaining = await clean_redis.llen('oee:queue:mqtt')
    assert remaining == 0, f"Queue not drained, {remaining} messages remaining"

    # 10. Verify replay statistics
    final_stats = client.get_statistics()
    print(f"📊 Final Stats: {final_stats}")
    assert final_stats['messages_replayed'] == num_messages

    # Cleanup
    await client.stop()


@pytest.mark.asyncio
async def test_store_forward_queue_persistence(
    test_config,
    clean_redis,
    test_node_id
):
    """
    Test that queued messages persist across edge gateway restarts
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    # 1. Create first client instance
    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_store_forward=True,
    )

    client1 = SparkplugMQTTClient(config)
    await client1.start()
    await asyncio.sleep(1)

    # 2. Disconnect and queue messages
    client1.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    num_messages = 5
    for i in range(num_messages):
        await client1._queue_message_for_later(
            f"test/topic/{i}",
            f"message_{i}".encode(),
            qos=1
        )

    # 3. Stop first client (simulate gateway restart)
    await client1.stop()

    # 4. Verify messages still in Redis
    queued = await clean_redis.llen('oee:queue:mqtt')
    assert queued == num_messages, "Messages lost after client stop"

    # 5. Start new client instance (simulates restart)
    client2 = SparkplugMQTTClient(config)
    await client2.start()
    await asyncio.sleep(2)

    # 6. Replay should happen automatically on reconnect
    await asyncio.sleep(1)

    # 7. Verify messages replayed
    stats = client2.get_statistics()
    assert stats['messages_replayed'] == num_messages

    # Cleanup
    await client2.stop()


@pytest.mark.asyncio
async def test_store_forward_max_queue_size(
    test_config,
    clean_redis,
    test_node_id
):
    """
    Test queue watermark (500 MB limit)
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_store_forward=True,
        store_forward_max_size_mb=1,  # Small limit for testing
    )

    client = SparkplugMQTTClient(config)
    await client.start()
    client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Try to queue large messages to exceed limit
    large_payload = b'X' * (512 * 1024)  # 512 KB each

    # Queue until we hit the limit (should stop around 2 messages for 1 MB limit)
    for i in range(10):
        try:
            await client._queue_message_for_later(
                f"test/large/{i}",
                large_payload,
                qos=1
            )
        except Exception as e:
            print(f"Queue full after {i} messages: {e}")
            break

    # Verify we didn't exceed the limit
    cache_stats = await client.edge_cache.get_stats()
    print(f"📊 Cache Stats: {cache_stats}")

    # Should have stopped before exceeding 1 MB limit
    assert cache_stats['memory_usage'] < (1.5 * 1024 * 1024), "Queue exceeded watermark"

    await client.stop()


@pytest.mark.asyncio
async def test_store_forward_no_data_loss(
    test_config,
    clean_timescaledb,
    clean_redis,
    test_node_id,
    mqtt_test_client
):
    """
    Critical test: Verify zero data loss during outage

    Acceptance Criteria:
    - All messages published during outage must be delivered after reconnection
    - Message order must be preserved
    - No duplicates
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_store_forward=True,
    )

    client = SparkplugMQTTClient(config)
    await client.start()
    await asyncio.sleep(1)

    # Subscribe to test topic to verify delivery
    received_messages = []

    def on_message(client_obj, userdata, msg):
        received_messages.append(msg.payload.decode())

    mqtt_test_client.subscribe(f"test/replay/{test_node_id}/#")
    mqtt_test_client.on_message = on_message

    # Disconnect broker
    client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Send 100 messages during outage
    sent_messages = []
    for i in range(100):
        message = f"critical_data_{i:03d}"
        sent_messages.append(message)

        await client._queue_message_for_later(
            f"test/replay/{test_node_id}/data",
            message.encode(),
            qos=1
        )

    print(f"📤 Sent {len(sent_messages)} messages during outage")

    # Reconnect
    await client._connect_with_retry()
    await asyncio.sleep(1)

    # Replay
    await client._replay_stored_messages()

    # Wait for delivery
    await asyncio.sleep(5)

    # Verify all messages received
    print(f"📥 Received {len(received_messages)} messages")

    # Check no data loss
    assert len(received_messages) == len(sent_messages), \
        f"Data loss! Sent {len(sent_messages)}, received {len(received_messages)}"

    # Check order preservation
    for i, (sent, received) in enumerate(zip(sent_messages, received_messages)):
        assert sent == received, f"Order violation at index {i}: expected '{sent}', got '{received}'"

    # Check no duplicates
    assert len(received_messages) == len(set(received_messages)), "Duplicate messages detected!"

    print("✅ Zero data loss verified!")

    await client.stop()


@pytest.mark.asyncio
@pytest.mark.slow
async def test_store_forward_long_outage(
    test_config,
    clean_redis,
    test_node_id
):
    """
    Test extended outage (simulate 1 hour of queued data)
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_store_forward=True,
        store_forward_max_size_mb=100,
    )

    client = SparkplugMQTTClient(config)
    await client.start()
    client.mqtt_client.disconnect()
    await asyncio.sleep(0.5)

    # Simulate 1 hour @ 10 messages/sec = 36,000 messages
    # Use smaller payload for reasonable test time
    num_messages = 1000  # Reduced for testing
    batch_size = 100

    start_time = time.time()

    for batch in range(num_messages // batch_size):
        for i in range(batch_size):
            msg_id = batch * batch_size + i
            await client._queue_message_for_later(
                f"test/long/{msg_id}",
                f"data_{msg_id}".encode(),
                qos=1
            )

        if batch % 10 == 0:
            print(f"Queued {(batch + 1) * batch_size}/{num_messages} messages")

    queue_time = time.time() - start_time
    print(f"⏱️  Queueing took {queue_time:.2f}s")

    # Verify queue size
    queued = await clean_redis.llen('oee:queue:mqtt')
    assert queued == num_messages

    # Reconnect and replay
    await client._connect_with_retry()
    await asyncio.sleep(1)

    replay_start = time.time()
    await client._replay_stored_messages()
    replay_time = time.time() - replay_start

    print(f"⏱️  Replay took {replay_time:.2f}s")
    print(f"📈 Replay rate: {num_messages / replay_time:.0f} msg/s")

    # Verify stats
    stats = client.get_statistics()
    assert stats['messages_replayed'] == num_messages

    await client.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
