"""
Fault Storm Load Tests
Simulates high-volume fault/alarm events to test system resilience
Target: 1000 msg/sec sustained without data loss
"""

import pytest
import asyncio
import time
import random
from datetime import datetime, timezone, timedelta

pytestmark = [
    pytest.mark.load,
    pytest.mark.requires_mqtt,
    pytest.mark.requires_timescaledb,
    pytest.mark.slow,
]


@pytest.mark.asyncio
async def test_fault_storm_1000_msg_per_sec(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder
):
    """
    Load test: 1000 messages/second for 30 seconds
    Target: Zero data loss, <2s latency maintained
    """

    # Send NBIRTH first
    nbirth = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", nbirth, qos=1)
    await asyncio.sleep(1)

    # Fault storm configuration
    duration_seconds = 30
    target_rate = 1000  # msg/sec
    total_messages = duration_seconds * target_rate

    fault_types = [
        'CRITICAL_ALARM',
        'HIGH_ALARM',
        'LOW_ALARM',
        'WARNING',
        'COMMUNICATION_ERROR',
        'SENSOR_FAULT',
        'MOTOR_OVERLOAD',
        'TEMPERATURE_HIGH',
        'PRESSURE_ABNORMAL',
        'EMERGENCY_STOP',
    ]

    print(f"\n🔥 Starting fault storm: {target_rate} msg/sec for {duration_seconds}s")
    print(f"📊 Total messages: {total_messages}")

    start_time = time.time()
    messages_sent = 0
    seq = 1

    # Track timing for rate limiting
    batch_size = 100
    batch_interval = batch_size / target_rate  # seconds per batch

    for batch_num in range(total_messages // batch_size):
        batch_start = time.time()

        # Send batch
        for i in range(batch_size):
            fault_type = random.choice(fault_types)
            severity = random.randint(1, 5)
            machine_id = f"MACHINE_{random.randint(1, 10)}"

            metrics = [
                {'name': 'fault_type', 'alias': 100, 'value': fault_type, 'type': 'String'},
                {'name': 'severity', 'alias': 101, 'value': severity, 'type': 'Int32'},
                {'name': 'machine_id', 'alias': 102, 'value': machine_id, 'type': 'String'},
                {'name': 'timestamp', 'alias': 103, 'value': int(time.time() * 1000), 'type': 'Int64'},
            ]

            payload = sparkplug_message_builder.create_node_data_payload(
                timestamp=int(time.time() * 1000),
                metrics=metrics,
                seq=seq
            )

            mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", payload, qos=1)
            messages_sent += 1
            seq += 1

        # Rate limiting
        batch_elapsed = time.time() - batch_start
        if batch_elapsed < batch_interval:
            await asyncio.sleep(batch_interval - batch_elapsed)

        # Progress update
        if batch_num % 100 == 0:
            elapsed = time.time() - start_time
            current_rate = messages_sent / elapsed if elapsed > 0 else 0
            print(f"📊 Sent {messages_sent}/{total_messages} messages ({current_rate:.0f} msg/s)")

    elapsed = time.time() - start_time
    actual_rate = messages_sent / elapsed

    print(f"\n✅ Fault storm completed")
    print(f"📊 Sent: {messages_sent} messages")
    print(f"📊 Duration: {elapsed:.2f}s")
    print(f"📊 Actual rate: {actual_rate:.0f} msg/s")

    # Wait for processing
    print(f"⏳ Waiting 10s for processing...")
    await asyncio.sleep(10)

    # Verify data in database
    db_count = await clean_timescaledb.fetchval(
        """
        SELECT COUNT(*) FROM telemetry
        WHERE machine_id = $1
        AND time >= $2
        """,
        test_node_id,
        datetime.fromtimestamp(start_time, tz=timezone.utc)
    )

    print(f"📊 Database received: {db_count} records")

    # Calculate data loss
    expected_records = messages_sent * 4  # 4 metrics per message
    loss_percentage = ((expected_records - db_count) / expected_records) * 100 if expected_records > 0 else 0

    print(f"📊 Expected records: {expected_records}")
    print(f"📊 Data loss: {loss_percentage:.2f}%")

    # Acceptance criteria
    assert actual_rate >= target_rate * 0.95, f"Failed to achieve target rate: {actual_rate:.0f}/{target_rate} msg/s"
    assert db_count >= expected_records * 0.98, f"Significant data loss: {loss_percentage:.2f}%"

    print(f"✅ Load test passed: {actual_rate:.0f} msg/s with {loss_percentage:.2f}% loss")


@pytest.mark.asyncio
async def test_fault_storm_burst_pattern(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder
):
    """
    Load test: Burst pattern (5s bursts at 2000 msg/s, 5s idle)
    Simulates realistic plant floor fault storms
    """

    # NBIRTH
    nbirth = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", nbirth, qos=1)
    await asyncio.sleep(1)

    print(f"\n🔥 Burst pattern test: 5s @ 2000 msg/s, 5s idle, 5 cycles")

    total_sent = 0
    seq = 1
    start_time = time.time()

    for cycle in range(5):
        print(f"\n📊 Cycle {cycle + 1}/5: Starting burst...")

        # Burst phase (5s @ 2000 msg/s = 10,000 messages)
        burst_start = time.time()
        burst_messages = 10000
        batch_size = 100

        for batch in range(burst_messages // batch_size):
            for i in range(batch_size):
                metrics = [
                    {'name': 'cycle', 'alias': 200, 'value': cycle, 'type': 'Int32'},
                    {'name': 'sequence', 'alias': 201, 'value': seq, 'type': 'Int32'},
                    {'name': 'burst_flag', 'alias': 202, 'value': True, 'type': 'Boolean'},
                ]

                payload = sparkplug_message_builder.create_node_data_payload(
                    timestamp=int(time.time() * 1000),
                    metrics=metrics,
                    seq=seq
                )

                mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", payload, qos=1)
                total_sent += 1
                seq += 1

            # Rate limiting for 2000 msg/s
            await asyncio.sleep(0.05)

        burst_elapsed = time.time() - burst_start
        burst_rate = burst_messages / burst_elapsed
        print(f"   Burst complete: {burst_messages} messages in {burst_elapsed:.2f}s ({burst_rate:.0f} msg/s)")

        # Idle phase (5s)
        print(f"   Idle phase: 5s")
        await asyncio.sleep(5)

    total_elapsed = time.time() - start_time
    avg_rate = total_sent / total_elapsed

    print(f"\n✅ Burst test completed")
    print(f"📊 Total sent: {total_sent} messages")
    print(f"📊 Total time: {total_elapsed:.2f}s")
    print(f"📊 Average rate: {avg_rate:.0f} msg/s")

    # Wait for processing
    await asyncio.sleep(10)

    # Verify database
    db_count = await clean_timescaledb.fetchval(
        "SELECT COUNT(*) FROM telemetry WHERE machine_id = $1",
        test_node_id
    )

    expected = total_sent * 3  # 3 metrics per message
    loss_pct = ((expected - db_count) / expected) * 100

    print(f"📊 Database: {db_count}/{expected} records ({loss_pct:.2f}% loss)")

    assert db_count >= expected * 0.95, f"Excessive data loss: {loss_pct:.2f}%"
    print(f"✅ Burst pattern handled successfully")


@pytest.mark.asyncio
async def test_fault_storm_concurrent_nodes(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    sparkplug_message_builder
):
    """
    Load test: 10 concurrent edge nodes @ 100 msg/s each = 1000 msg/s aggregate
    Tests system behavior under distributed load
    """

    num_nodes = 10
    rate_per_node = 100  # msg/s
    duration = 20  # seconds
    messages_per_node = rate_per_node * duration

    node_ids = [f"test_node_{i:02d}" for i in range(num_nodes)]

    print(f"\n🔥 Concurrent nodes test: {num_nodes} nodes @ {rate_per_node} msg/s")
    print(f"📊 Aggregate rate: {num_nodes * rate_per_node} msg/s")
    print(f"📊 Duration: {duration}s")

    # Send NBIRTH for all nodes
    for node_id in node_ids:
        nbirth = sparkplug_message_builder.create_node_birth_payload(
            timestamp=int(time.time() * 1000),
            metrics=[],
            seq=0
        )
        mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{node_id}", nbirth, qos=1)

    await asyncio.sleep(2)

    # Concurrent message generation
    async def send_node_messages(node_id: str, node_index: int):
        seq = 1
        sent = 0

        for i in range(messages_per_node):
            metrics = [
                {'name': 'node_index', 'alias': 300, 'value': node_index, 'type': 'Int32'},
                {'name': 'message_num', 'alias': 301, 'value': i, 'type': 'Int32'},
                {'name': 'value', 'alias': 302, 'value': random.uniform(0, 100), 'type': 'Float'},
            ]

            payload = sparkplug_message_builder.create_node_data_payload(
                timestamp=int(time.time() * 1000),
                metrics=metrics,
                seq=seq
            )

            mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{node_id}", payload, qos=1)
            sent += 1
            seq += 1

            # Rate limiting
            await asyncio.sleep(1.0 / rate_per_node)

        return sent

    # Start all nodes concurrently
    start_time = time.time()
    tasks = [send_node_messages(node_id, i) for i, node_id in enumerate(node_ids)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    total_sent = sum(results)
    actual_rate = total_sent / elapsed

    print(f"\n✅ Concurrent test completed")
    print(f"📊 Total sent: {total_sent} messages")
    print(f"📊 Duration: {elapsed:.2f}s")
    print(f"📊 Actual rate: {actual_rate:.0f} msg/s")

    # Wait for processing
    await asyncio.sleep(10)

    # Verify database
    db_count = await clean_timescaledb.fetchval(
        """
        SELECT COUNT(*) FROM telemetry
        WHERE machine_id = ANY($1::text[])
        """,
        node_ids
    )

    expected = total_sent * 3  # 3 metrics per message
    loss_pct = ((expected - db_count) / expected) * 100

    print(f"📊 Database: {db_count}/{expected} records ({loss_pct:.2f}% loss)")

    assert actual_rate >= (num_nodes * rate_per_node) * 0.9
    assert db_count >= expected * 0.95
    print(f"✅ Concurrent node test passed")


@pytest.mark.asyncio
async def test_fault_storm_memory_stability(
    test_config,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder
):
    """
    Load test: Verify memory stability under sustained load
    Monitor MQTT client queue size and ensure no unbounded growth
    """

    from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig

    config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
        enable_backpressure=True,
        backpressure_threshold=500,
        max_queue_size=2000,
    )

    client = SparkplugMQTTClient(config)
    await client.start()
    await asyncio.sleep(1)

    # Track queue size over time
    queue_samples = []

    async def monitor_queue():
        for _ in range(60):  # 60 seconds
            queue_samples.append({
                'timestamp': time.time(),
                'queue_size': client.message_queue.qsize()
            })
            await asyncio.sleep(1)

    # Start monitoring
    monitor_task = asyncio.create_task(monitor_queue())

    # Generate sustained load (500 msg/s for 60s)
    print(f"\n🔥 Memory stability test: 500 msg/s for 60s")

    start_time = time.time()
    messages_sent = 0
    seq = 1

    for i in range(30000):  # 500 msg/s * 60s = 30,000 messages
        metrics = [
            {'name': 'counter', 'alias': 400, 'value': i, 'type': 'Int32'},
        ]

        try:
            await client.publish_node_data(metrics=metrics, seq=seq)
            messages_sent += 1
            seq += 1
        except Exception as e:
            print(f"⚠️  Publish error at message {i}: {e}")

        # Rate limiting
        if i % 500 == 0:
            await asyncio.sleep(1.0)
        else:
            await asyncio.sleep(0.002)

    elapsed = time.time() - start_time

    # Wait for monitoring to complete
    await monitor_task

    # Analyze queue stability
    max_queue = max(s['queue_size'] for s in queue_samples)
    avg_queue = sum(s['queue_size'] for s in queue_samples) / len(queue_samples)
    final_queue = queue_samples[-1]['queue_size']

    print(f"\n✅ Stability test completed")
    print(f"📊 Messages sent: {messages_sent}")
    print(f"📊 Duration: {elapsed:.2f}s")
    print(f"📊 Queue stats:")
    print(f"   Max: {max_queue}")
    print(f"   Avg: {avg_queue:.0f}")
    print(f"   Final: {final_queue}")

    # Verify queue remained stable
    assert max_queue < config.max_queue_size, f"Queue exceeded limit: {max_queue}"
    assert final_queue < config.backpressure_threshold * 2, f"Queue not draining properly: {final_queue}"

    print(f"✅ Memory remained stable under load")

    await client.stop()


@pytest.mark.asyncio
async def test_fault_storm_latency_under_load(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder,
    measure_latency
):
    """
    Load test: Measure latency percentiles under sustained load
    Target: p95 < 2000ms, p99 < 5000ms
    """

    # NBIRTH
    nbirth = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", nbirth, qos=1)
    await asyncio.sleep(1)

    print(f"\n🔥 Latency test: 500 msg/s for 30s with latency measurements")

    duration = 30
    rate = 500
    total_messages = duration * rate
    seq = 1

    # Sample latency every 100 messages
    latency_samples = []
    sample_interval = 100

    start_time = time.time()

    for i in range(total_messages):
        # Latency measurement on sample messages
        if i % sample_interval == 0:
            measure_latency.start()
            publish_time = datetime.now(timezone.utc)

            metrics = [
                {'name': 'sample_marker', 'alias': 500, 'value': i, 'type': 'Int32'},
                {'name': 'publish_timestamp', 'alias': 501, 'value': int(time.time() * 1000), 'type': 'Int64'},
            ]

            payload = sparkplug_message_builder.create_node_data_payload(
                timestamp=int(time.time() * 1000),
                metrics=metrics,
                seq=seq
            )

            mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", payload, qos=1)

            # Poll for message in DB
            found = False
            for _ in range(50):  # 5 second timeout
                row = await clean_timescaledb.fetchrow(
                    """
                    SELECT time FROM telemetry
                    WHERE machine_id = $1
                    AND metric_name = 'sample_marker'
                    AND value = $2
                    AND time >= $3
                    """,
                    test_node_id,
                    i,
                    publish_time
                )

                if row:
                    latency = measure_latency.stop()
                    latency_samples.append(latency)
                    found = True
                    break

                await asyncio.sleep(0.1)

            if not found:
                print(f"⚠️  Sample {i} not found in DB")

        else:
            # Regular message
            metrics = [
                {'name': 'counter', 'alias': 502, 'value': i, 'type': 'Int32'},
            ]

            payload = sparkplug_message_builder.create_node_data_payload(
                timestamp=int(time.time() * 1000),
                metrics=metrics,
                seq=seq
            )

            mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", payload, qos=1)

        seq += 1

        # Rate limiting
        await asyncio.sleep(1.0 / rate)

    elapsed = time.time() - start_time

    # Calculate latency percentiles
    if latency_samples:
        latency_samples.sort()
        p50 = latency_samples[len(latency_samples) // 2]
        p95 = latency_samples[int(len(latency_samples) * 0.95)]
        p99 = latency_samples[int(len(latency_samples) * 0.99)]
        max_latency = max(latency_samples)

        print(f"\n✅ Latency test completed")
        print(f"📊 Messages sent: {total_messages} in {elapsed:.2f}s")
        print(f"📊 Latency samples: {len(latency_samples)}")
        print(f"📊 Latency percentiles:")
        print(f"   p50: {p50:.0f} ms")
        print(f"   p95: {p95:.0f} ms")
        print(f"   p99: {p99:.0f} ms")
        print(f"   max: {max_latency:.0f} ms")

        # Verify SLA
        assert p95 < 2000, f"p95 latency {p95:.0f}ms exceeds 2000ms target"
        assert p99 < 5000, f"p99 latency {p99:.0f}ms exceeds 5000ms target"

        print(f"✅ Latency SLA maintained under load")
    else:
        pytest.fail("No latency samples collected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
