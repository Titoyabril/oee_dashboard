"""
End-to-End Sparkplug B Integration Test
Tests complete data flow: Edge → MQTT → Processor → TimescaleDB
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timezone

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_mqtt,
    pytest.mark.requires_timescaledb,
]


@pytest.mark.asyncio
async def test_e2e_sparkplug_nbirth_to_database(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder
):
    """
    Test NBIRTH message flow from MQTT to TimescaleDB

    Flow: MQTT Publish → Sparkplug Decoder → DB Write → Verification
    """

    # 1. Create NBIRTH payload
    metrics = [
        {'name': 'Node Control/Rebirth', 'alias': 0, 'value': False, 'type': 'Boolean'},
        {'name': 'Properties/Software_Version', 'alias': 1, 'value': '1.0.0', 'type': 'String'},
    ]

    payload = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=metrics,
        seq=0
    )

    # 2. Publish to MQTT
    topic = f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}"
    mqtt_test_client.publish(topic, payload, qos=1)

    # 3. Wait for processing
    await asyncio.sleep(2)

    # 4. Verify node created in database
    result = await clean_timescaledb.fetchrow(
        "SELECT * FROM sparkplug_nodes WHERE node_id = $1",
        test_node_id
    )

    assert result is not None, "Node not found in database"
    assert result['status'] in ['ONLINE', 'BIRTH']
    assert result['group_id'] == 'TEST_GROUP'


@pytest.mark.asyncio
async def test_e2e_sparkplug_ndata_telemetry(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder,
    measure_latency
):
    """
    Test NDATA telemetry flow with latency measurement

    Target: <1s end-to-end latency (MQTT publish → DB write)
    """

    # 1. Send NBIRTH first
    birth_payload = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", birth_payload, qos=1)
    await asyncio.sleep(1)

    # 2. Send NDATA with telemetry
    metrics = [
        {'name': 'temperature', 'alias': 10, 'value': 75.5, 'type': 'Float'},
        {'name': 'pressure', 'alias': 11, 'value': 14.7, 'type': 'Float'},
        {'name': 'vibration', 'alias': 12, 'value': 2.1, 'type': 'Float'},
    ]

    measure_latency.start()
    publish_time = datetime.now(timezone.utc)

    ndata_payload = sparkplug_message_builder.create_node_data_payload(
        timestamp=int(time.time() * 1000),
        metrics=metrics,
        seq=1
    )

    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", ndata_payload, qos=1)

    # 3. Poll database for data (with timeout)
    max_wait = 5.0  # 5 second timeout
    interval = 0.1
    elapsed = 0
    found = False

    while elapsed < max_wait:
        count = await clean_timescaledb.fetchval(
            """
            SELECT COUNT(*) FROM telemetry
            WHERE machine_id = $1
            AND time >= $2
            """,
            test_node_id,
            publish_time
        )

        if count >= 3:  # All 3 metrics
            latency = measure_latency.stop()
            found = True
            break

        await asyncio.sleep(interval)
        elapsed += interval

    assert found, f"Telemetry not found in database after {max_wait}s"

    # 4. Verify data quality
    rows = await clean_timescaledb.fetch(
        """
        SELECT metric_name, value, quality
        FROM telemetry
        WHERE machine_id = $1
        AND time >= $2
        ORDER BY metric_name
        """,
        test_node_id,
        publish_time
    )

    assert len(rows) == 3

    # Verify metric values
    metrics_dict = {row['metric_name']: row for row in rows}
    assert 'temperature' in metrics_dict
    assert abs(metrics_dict['temperature']['value'] - 75.5) < 0.01
    assert metrics_dict['temperature']['quality'] == 192  # GOOD

    # 5. Verify latency SLA
    print(f"\n📊 End-to-End Latency: {latency:.2f} ms")
    assert latency < 1000, f"Latency {latency:.2f}ms exceeds 1000ms SLA"


@pytest.mark.asyncio
async def test_e2e_sparkplug_dbirth_ddata(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    test_device_id,
    sparkplug_message_builder
):
    """
    Test device birth and data messages
    """

    # 1. NBIRTH
    nbirth = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", nbirth, qos=1)
    await asyncio.sleep(0.5)

    # 2. DBIRTH (device birth)
    device_metrics = [
        {'name': 'Device/ProductionCount', 'alias': 100, 'value': 0, 'type': 'Int32'},
        {'name': 'Device/GoodCount', 'alias': 101, 'value': 0, 'type': 'Int32'},
        {'name': 'Device/State', 'alias': 102, 'value': 'RUNNING', 'type': 'String'},
    ]

    dbirth = sparkplug_message_builder.create_device_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=device_metrics,
        seq=1
    )

    topic_dbirth = f"spBv1.0/TEST_GROUP/DBIRTH/{test_node_id}/{test_device_id}"
    mqtt_test_client.publish(topic_dbirth, dbirth, qos=1)
    await asyncio.sleep(1)

    # 3. Verify device created
    device = await clean_timescaledb.fetchrow(
        """
        SELECT * FROM sparkplug_devices
        WHERE node_id = $1 AND device_id = $2
        """,
        test_node_id,
        test_device_id
    )

    assert device is not None, "Device not created in database"
    assert device['status'] in ['ONLINE', 'BIRTH']

    # 4. Send DDATA (device data)
    ddata_metrics = [
        {'name': 'Device/ProductionCount', 'alias': 100, 'value': 150, 'type': 'Int32'},
        {'name': 'Device/GoodCount', 'alias': 101, 'value': 145, 'type': 'Int32'},
    ]

    ddata = sparkplug_message_builder.create_device_data_payload(
        timestamp=int(time.time() * 1000),
        metrics=ddata_metrics,
        seq=2
    )

    topic_ddata = f"spBv1.0/TEST_GROUP/DDATA/{test_node_id}/{test_device_id}"
    mqtt_test_client.publish(topic_ddata, ddata, qos=1)
    await asyncio.sleep(1)

    # 5. Verify data in telemetry table
    count = await clean_timescaledb.fetchval(
        "SELECT COUNT(*) FROM telemetry WHERE machine_id = $1",
        test_device_id
    )

    assert count >= 2, f"Expected at least 2 telemetry records, got {count}"


@pytest.mark.asyncio
async def test_e2e_sequence_number_validation(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder
):
    """
    Test sequence number validation and gap detection
    """

    # 1. NBIRTH (seq=0)
    nbirth = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", nbirth, qos=1)
    await asyncio.sleep(0.5)

    # 2. NDATA (seq=1) - correct
    ndata1 = sparkplug_message_builder.create_node_data_payload(
        timestamp=int(time.time() * 1000),
        metrics=[{'name': 'test1', 'value': 1}],
        seq=1
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", ndata1, qos=1)
    await asyncio.sleep(0.5)

    # 3. NDATA (seq=5) - gap! Should trigger error
    ndata2 = sparkplug_message_builder.create_node_data_payload(
        timestamp=int(time.time() * 1000),
        metrics=[{'name': 'test2', 'value': 2}],
        seq=5
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", ndata2, qos=1)
    await asyncio.sleep(1)

    # 4. Check sequence errors were logged
    node = await clean_timescaledb.fetchrow(
        "SELECT error_count, last_error_message FROM sparkplug_nodes WHERE node_id = $1",
        test_node_id
    )

    assert node['error_count'] > 0, "Sequence error not detected"
    assert 'gap' in node['last_error_message'].lower() or 'sequence' in node['last_error_message'].lower()


@pytest.mark.asyncio
async def test_e2e_message_ordering(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder
):
    """
    Test that messages are processed in order even under load
    """

    # 1. NBIRTH
    nbirth = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", nbirth, qos=1)
    await asyncio.sleep(0.5)

    # 2. Send 100 NDATA messages rapidly
    for seq in range(1, 101):
        ndata = sparkplug_message_builder.create_node_data_payload(
            timestamp=int(time.time() * 1000),
            metrics=[{'name': 'counter', 'alias': 10, 'value': seq, 'type': 'Int32'}],
            seq=seq
        )
        mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", ndata, qos=1)

    # 3. Wait for processing
    await asyncio.sleep(5)

    # 4. Verify all messages received and in order
    rows = await clean_timescaledb.fetch(
        """
        SELECT value FROM telemetry
        WHERE machine_id = $1 AND metric_name = 'counter'
        ORDER BY time ASC
        """,
        test_node_id
    )

    assert len(rows) == 100, f"Expected 100 messages, got {len(rows)}"

    # Check ordering
    for i, row in enumerate(rows, start=1):
        assert int(row['value']) == i, f"Order violation at index {i}: expected {i}, got {row['value']}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_e2e_continuous_aggregate_updates(
    test_config,
    clean_timescaledb,
    mqtt_test_client,
    test_node_id,
    sparkplug_message_builder
):
    """
    Test that continuous aggregates are updated correctly
    """

    # 1. NBIRTH
    nbirth = sparkplug_message_builder.create_node_birth_payload(
        timestamp=int(time.time() * 1000),
        metrics=[],
        seq=0
    )
    mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NBIRTH/{test_node_id}", nbirth, qos=1)
    await asyncio.sleep(0.5)

    # 2. Send telemetry over 2 minutes
    import random
    for i in range(120):  # 120 data points (1 per second)
        metrics = [
            {'name': 'temperature', 'alias': 10, 'value': 70 + random.uniform(-5, 5), 'type': 'Float'}
        ]

        ndata = sparkplug_message_builder.create_node_data_payload(
            timestamp=int((time.time() - (120 - i)) * 1000),  # Backdated
            metrics=metrics,
            seq=i + 1
        )

        mqtt_test_client.publish(f"spBv1.0/TEST_GROUP/NDATA/{test_node_id}", ndata, qos=1)

        if i % 10 == 0:
            await asyncio.sleep(0.1)  # Brief pause every 10 messages

    # 3. Wait for aggregates to refresh
    await asyncio.sleep(10)

    # 4. Manually refresh continuous aggregate
    await clean_timescaledb.execute(
        "CALL refresh_continuous_aggregate('telemetry_1min', NULL, NULL)"
    )

    # 5. Query 1-minute aggregate
    agg_rows = await clean_timescaledb.fetch(
        """
        SELECT bucket, avg_value, min_value, max_value, sample_count
        FROM telemetry_1min
        WHERE machine_id = $1 AND metric_name = 'temperature'
        ORDER BY bucket
        """,
        test_node_id
    )

    assert len(agg_rows) >= 2, f"Expected at least 2 1-minute buckets, got {len(agg_rows)}"

    # Verify aggregation math
    for row in agg_rows:
        assert row['sample_count'] > 0
        assert row['min_value'] <= row['avg_value'] <= row['max_value']
        print(f"Bucket: {row['bucket']}, Avg: {row['avg_value']:.2f}, Samples: {row['sample_count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
