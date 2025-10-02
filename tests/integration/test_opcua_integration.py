"""
OPC-UA Integration Tests
Tests OPC-UA client → Sparkplug MQTT → TimescaleDB pipeline
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_opcua,
    pytest.mark.requires_mqtt,
    pytest.mark.requires_timescaledb,
]


@pytest.mark.asyncio
async def test_opcua_connection_and_discovery(
    opcua_simulator,
    test_config
):
    """
    Test OPC-UA client connection and namespace discovery
    """

    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAClient, OPCUAConfig

    config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
    )

    client = OPCUAClient(config)

    # Connect
    success = await client.connect()
    assert success, "Failed to connect to OPC-UA server"

    # Verify namespace index
    assert client.namespace_idx is not None
    assert client.namespace_idx > 0
    print(f"✅ Connected to OPC-UA server, namespace index: {client.namespace_idx}")

    # Browse nodes
    objects = await client.client.nodes.objects.get_children()
    assert len(objects) > 0, "No objects found in OPC-UA server"

    # Find test machine
    test_machine = None
    for obj in objects:
        browse_name = await obj.read_browse_name()
        if browse_name.Name == "TestMachine":
            test_machine = obj
            break

    assert test_machine is not None, "TestMachine not found"
    print(f"✅ Found TestMachine object")

    # Browse machine variables
    variables = await test_machine.get_children()
    var_names = []
    for var in variables:
        browse_name = await var.read_browse_name()
        var_names.append(browse_name.Name)

    assert 'ProductionCount' in var_names
    assert 'GoodCount' in var_names
    assert 'Temperature' in var_names
    print(f"✅ Found variables: {var_names}")

    await client.disconnect()


@pytest.mark.asyncio
async def test_opcua_read_values(
    opcua_simulator
):
    """
    Test reading values from OPC-UA server
    """

    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAClient, OPCUAConfig

    config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
    )

    client = OPCUAClient(config)
    await client.connect()

    # Build node ID
    from asyncua import ua
    node_id = ua.NodeId(Identifier="ProductionCount", NamespaceIndex=client.namespace_idx, NodeIdType=ua.NodeIdType.String)

    # Read value
    value = await client.read_value(node_id)
    assert value is not None
    assert isinstance(value, (int, float))
    print(f"✅ Read ProductionCount: {value}")

    # Write new value
    production_var = opcua_simulator['variables']['production_count']
    await production_var.write_value(150)
    await asyncio.sleep(0.1)

    # Read again
    new_value = await client.read_value(node_id)
    assert new_value == 150
    print(f"✅ Value updated: {new_value}")

    await client.disconnect()


@pytest.mark.asyncio
async def test_opcua_subscription_monitoring(
    opcua_simulator
):
    """
    Test OPC-UA subscriptions and data change notifications
    """

    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAClient, OPCUAConfig, MonitoredItem

    config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        sampling_interval=100,
    )

    client = OPCUAClient(config)
    await client.connect()

    # Create subscription
    await client.create_subscription(publishing_interval=100)

    # Track data changes
    data_changes = []

    def on_data_change(node_id, value, timestamp):
        data_changes.append({
            'node_id': str(node_id),
            'value': value,
            'timestamp': timestamp
        })

    client.data_change_callback = on_data_change

    # Add monitored item
    from asyncua import ua
    temp_node = ua.NodeId(Identifier="Temperature", NamespaceIndex=client.namespace_idx, NodeIdType=ua.NodeIdType.String)

    item = MonitoredItem(
        node_id=temp_node,
        name='temperature',
        sampling_interval=100
    )

    await client.add_monitored_item(item)
    await asyncio.sleep(0.5)

    # Change temperature value
    temp_var = opcua_simulator['variables']['temperature']
    await temp_var.write_value(80.0)
    await asyncio.sleep(0.3)

    await temp_var.write_value(85.0)
    await asyncio.sleep(0.3)

    await temp_var.write_value(90.0)
    await asyncio.sleep(0.3)

    # Verify notifications received
    assert len(data_changes) >= 3, f"Expected at least 3 data changes, got {len(data_changes)}"

    # Verify values
    values = [dc['value'] for dc in data_changes]
    assert 80.0 in values or any(abs(v - 80.0) < 0.1 for v in values)
    print(f"✅ Received {len(data_changes)} data change notifications")
    print(f"📊 Values: {values[:5]}")

    await client.disconnect()


@pytest.mark.asyncio
async def test_opcua_to_sparkplug_mapping(
    opcua_simulator,
    test_config,
    mqtt_test_client,
    test_node_id
):
    """
    Test mapping OPC-UA data changes to Sparkplug messages
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig
    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAConfig, MonitoredItem
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig
    from asyncua import ua

    # Configure edge gateway
    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
    )

    opcua_config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        sampling_interval=100,
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[opcua_config],
    )

    gateway = EdgeGateway(gateway_config)

    # Subscribe to MQTT messages
    received_messages = []

    def on_message(client, userdata, msg):
        received_messages.append({
            'topic': msg.topic,
            'payload': msg.payload,
            'timestamp': datetime.now(timezone.utc)
        })

    mqtt_test_client.subscribe(f"spBv1.0/TEST_GROUP/#")
    mqtt_test_client.on_message = on_message

    # Start gateway
    await gateway.start()
    await asyncio.sleep(2)

    # Wait for NBIRTH
    await asyncio.sleep(1)
    nbirth_received = any('NBIRTH' in m['topic'] for m in received_messages)
    assert nbirth_received, "NBIRTH message not received"
    print(f"✅ NBIRTH received")

    initial_count = len(received_messages)

    # Change OPC-UA values
    temp_var = opcua_simulator['variables']['temperature']
    prod_var = opcua_simulator['variables']['production_count']

    await temp_var.write_value(95.0)
    await asyncio.sleep(0.5)

    await prod_var.write_value(200)
    await asyncio.sleep(0.5)

    # Verify NDATA messages
    ndata_count = sum(1 for m in received_messages if 'NDATA' in m['topic'])
    assert ndata_count >= 2, f"Expected at least 2 NDATA messages, got {ndata_count}"
    print(f"✅ Received {ndata_count} NDATA messages")

    await gateway.stop()


@pytest.mark.asyncio
async def test_opcua_to_database_pipeline(
    opcua_simulator,
    test_config,
    clean_timescaledb,
    test_node_id,
    measure_latency
):
    """
    End-to-end test: OPC-UA → Sparkplug MQTT → TimescaleDB

    Measures complete pipeline latency from OPC-UA write to database read
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig
    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAConfig
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig

    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
    )

    opcua_config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        sampling_interval=100,
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[opcua_config],
    )

    gateway = EdgeGateway(gateway_config)

    # Start gateway and wait for NBIRTH
    await gateway.start()
    await asyncio.sleep(3)

    # Start latency measurement
    measure_latency.start()
    write_time = datetime.now(timezone.utc)

    # Write to OPC-UA
    temp_var = opcua_simulator['variables']['temperature']
    test_value = 99.9
    await temp_var.write_value(test_value)

    # Poll database for value
    max_wait = 5.0
    interval = 0.1
    elapsed = 0
    found = False

    while elapsed < max_wait:
        row = await clean_timescaledb.fetchrow(
            """
            SELECT value, time FROM telemetry
            WHERE machine_id = $1
            AND metric_name = 'Temperature'
            AND time >= $2
            ORDER BY time DESC
            LIMIT 1
            """,
            test_node_id,
            write_time
        )

        if row and abs(row['value'] - test_value) < 0.1:
            latency = measure_latency.stop()
            found = True
            print(f"✅ Value found in database: {row['value']}")
            print(f"📊 End-to-end latency: {latency:.2f} ms")
            break

        await asyncio.sleep(interval)
        elapsed += interval

    assert found, f"Value not found in database after {max_wait}s"
    assert latency < 2000, f"Latency {latency:.2f}ms exceeds 2000ms threshold"

    await gateway.stop()


@pytest.mark.asyncio
async def test_opcua_connection_resilience(
    opcua_simulator,
    test_config
):
    """
    Test OPC-UA client reconnection after server restart
    """

    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAClient, OPCUAConfig

    config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        reconnect_interval=2,
    )

    client = OPCUAClient(config)

    # Initial connection
    success = await client.connect()
    assert success

    # Simulate disconnect
    await client.client.disconnect()
    await asyncio.sleep(0.5)

    # Client should detect disconnect
    assert not client.connected

    # Attempt reconnection
    reconnected = await client.connect()
    assert reconnected, "Failed to reconnect"

    print(f"✅ Successfully reconnected to OPC-UA server")

    await client.disconnect()


@pytest.mark.asyncio
async def test_opcua_multiple_endpoints(
    opcua_simulator,
    test_config,
    test_node_id
):
    """
    Test edge gateway with multiple OPC-UA servers
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig
    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAConfig
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig

    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
    )

    # Configure two OPC-UA endpoints (same server for testing)
    opcua_config_1 = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        client_id='client_1',
    )

    opcua_config_2 = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        client_id='client_2',
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[opcua_config_1, opcua_config_2],
    )

    gateway = EdgeGateway(gateway_config)

    # Start gateway
    await gateway.start()
    await asyncio.sleep(2)

    # Verify both clients connected
    assert len(gateway.opcua_clients) == 2
    assert all(client.connected for client in gateway.opcua_clients)
    print(f"✅ Connected to {len(gateway.opcua_clients)} OPC-UA servers")

    await gateway.stop()


@pytest.mark.asyncio
@pytest.mark.slow
async def test_opcua_high_frequency_updates(
    opcua_simulator,
    test_config,
    clean_timescaledb,
    test_node_id
):
    """
    Load test: High-frequency OPC-UA data changes
    Target: 100 updates/second sustained
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig
    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAConfig
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig

    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
    )

    opcua_config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        sampling_interval=10,  # 10ms = 100 Hz
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[opcua_config],
    )

    gateway = EdgeGateway(gateway_config)

    await gateway.start()
    await asyncio.sleep(2)

    # Rapid OPC-UA updates
    temp_var = opcua_simulator['variables']['temperature']
    start_time = time.time()
    num_updates = 500

    for i in range(num_updates):
        await temp_var.write_value(70.0 + (i % 20))
        await asyncio.sleep(0.01)  # 10ms = 100 Hz

    elapsed = time.time() - start_time
    update_rate = num_updates / elapsed

    print(f"📊 Generated {num_updates} updates in {elapsed:.2f}s ({update_rate:.0f} Hz)")

    # Wait for processing
    await asyncio.sleep(5)

    # Check database
    count = await clean_timescaledb.fetchval(
        "SELECT COUNT(*) FROM telemetry WHERE machine_id = $1 AND metric_name = 'Temperature'",
        test_node_id
    )

    print(f"📊 Database received {count} records")

    # Verify throughput (allow some loss due to sampling/aggregation)
    assert count >= num_updates * 0.5, f"Significant data loss: {count}/{num_updates}"

    print(f"✅ High-frequency updates handled successfully")

    await gateway.stop()


@pytest.mark.asyncio
async def test_opcua_tag_configuration(
    opcua_simulator,
    test_config,
    test_node_id
):
    """
    Test OPC-UA tag configuration and monitoring
    """

    from oee_analytics.sparkplug.edge_gateway import EdgeGateway, EdgeGatewayConfig
    from oee_analytics.sparkplug.connectors.opcua_client import OPCUAConfig, OPCUATagConfig
    from oee_analytics.sparkplug.mqtt_client import SparkplugConfig
    from asyncua import ua

    mqtt_config = SparkplugConfig(
        broker_host=test_config['mqtt_broker'],
        broker_port=test_config['mqtt_port'],
        group_id='TEST_GROUP',
        node_id=test_node_id,
    )

    # Configure specific tags to monitor
    tag_configs = [
        OPCUATagConfig(
            node_id='ns=2;s=ProductionCount',
            name='production_count',
            type='counter.total',
            sampling_interval=100
        ),
        OPCUATagConfig(
            node_id='ns=2;s=Temperature',
            name='temperature',
            type='gauge',
            sampling_interval=100
        ),
    ]

    opcua_config = OPCUAConfig(
        endpoint='opc.tcp://localhost:4840/oeetest/',
        namespace_uri='http://oee.test',
        tags=tag_configs,
    )

    gateway_config = EdgeGatewayConfig(
        mqtt_config=mqtt_config,
        opcua_configs=[opcua_config],
    )

    gateway = EdgeGateway(gateway_config)

    await gateway.start()
    await asyncio.sleep(2)

    # Verify monitored items created
    opcua_client = gateway.opcua_clients[0]
    assert len(opcua_client.monitored_items) == 2
    print(f"✅ Monitoring {len(opcua_client.monitored_items)} configured tags")

    # Verify tag names
    tag_names = [item.name for item in opcua_client.monitored_items]
    assert 'production_count' in tag_names
    assert 'temperature' in tag_names

    await gateway.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
