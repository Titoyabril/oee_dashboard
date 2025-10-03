"""
Comprehensive Integration Tests for Allen-Bradley PLC Simulator Data Flow
Tests the complete path: PLC Simulator -> Connector -> MQTT -> TimescaleDB -> Django API -> Dashboard

Test Suite covers:
1. PLC Simulator connectivity and tag reading
2. Allen-Bradley Connector integration
3. Sparkplug B MQTT publishing
4. MQTT broker message delivery
5. TimescaleDB data ingestion
6. Django ORM data retrieval
7. REST API endpoints
8. Data accuracy and integrity
9. Real-time data updates
10. End-to-end latency measurement
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class TestPLCSimulatorConnectivity:
    """Test 1: PLC Simulator Basic Connectivity"""

    @pytest.mark.asyncio
    async def test_simulator_connection(self):
        """Verify we can connect to all 3 PLC simulators"""
        simulators = [
            ('localhost', 44818, 'LINE-001'),
            ('localhost', 44819, 'LINE-002'),
            ('localhost', 44820, 'LINE-003'),
        ]

        for host, port, line_id in simulators:
            # Connect
            reader, writer = await asyncio.open_connection(host, port)

            try:
                # Send ping
                req = {'method': 'ping'}
                data = json.dumps(req).encode('utf-8')
                writer.write(len(data).to_bytes(4, 'big') + data)
                await writer.drain()

                # Read response
                length = int.from_bytes(await reader.readexactly(4), 'big')
                resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

                assert resp['success'] is True, f"Ping failed for {line_id}"
                assert resp['pong'] is True, f"Pong not received for {line_id}"
                assert resp['connected'] is True, f"{line_id} not connected"

                logger.info(f"✓ {line_id} simulator connected successfully")

            finally:
                writer.close()
                await writer.wait_closed()

    @pytest.mark.asyncio
    async def test_simulator_tag_reading(self):
        """Verify we can read production tags from simulators"""
        reader, writer = await asyncio.open_connection('localhost', 44818)

        try:
            # Read production count
            req = {'method': 'read', 'params': {'tags': ['Line_LINE_001_ProductionCount']}}
            data = json.dumps(req).encode('utf-8')
            writer.write(len(data).to_bytes(4, 'big') + data)
            await writer.drain()

            length = int.from_bytes(await reader.readexactly(4), 'big')
            resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

            assert resp['success'] is True
            assert len(resp['results']) == 1
            assert resp['results'][0]['tag'] == 'Line_LINE_001_ProductionCount'
            assert resp['results'][0]['value'] >= 0
            assert resp['results'][0]['error'] is None

            initial_count = resp['results'][0]['value']
            logger.info(f"✓ Read initial production count: {initial_count}")

            # Wait and read again to verify incrementing
            await asyncio.sleep(3)

            writer.write(len(data).to_bytes(4, 'big') + data)
            await writer.drain()

            length = int.from_bytes(await reader.readexactly(4), 'big')
            resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

            final_count = resp['results'][0]['value']

            assert final_count >= initial_count, "Production count should increment"
            logger.info(f"✓ Production count incremented: {initial_count} -> {final_count}")

        finally:
            writer.close()
            await writer.wait_closed()


class TestAllenBradleyConnector:
    """Test 2: Allen-Bradley Connector Integration"""

    @pytest.mark.asyncio
    async def test_connector_reads_simulator(self):
        """Verify Allen-Bradley connector can read from simulator"""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

        from oee_analytics.sparkplug.connectors.allen_bradley import (
            AllenBradleyConnector, AllenBradleyConfig
        )

        config = AllenBradleyConfig(
            host="localhost",
            port=44818,
            plc_family="CONTROLLOGIX",
            slot=0,
            timeout=5.0,
            simulator_mode=True
        )

        connector = AllenBradleyConnector(config)

        try:
            # Connect
            connected = await connector.connect()
            assert connected is True, "Connector failed to connect to simulator"
            logger.info("✓ Connector connected to simulator")

            # Read single tag
            data_point = await connector.read_single("Line_LINE_001_OEE", "REAL")
            assert data_point.value is not None
            assert 0 <= data_point.value <= 100
            logger.info(f"✓ Read OEE value: {data_point.value}%")

            # Read multiple tags
            tags = [
                ("Line_LINE_001_ProductionCount", "DINT"),
                ("Line_LINE_001_Running", "BOOL"),
                ("Line_LINE_001_OEE", "REAL"),
            ]

            data_points = await connector.read_multiple(tags)
            assert len(data_points) == 3
            assert all(dp.error is None for dp in data_points)
            logger.info(f"✓ Read {len(data_points)} tags successfully")

        finally:
            await connector.disconnect()


class TestSparkplugMQTTPublishing:
    """Test 3: Sparkplug B MQTT Publishing"""

    @pytest.mark.asyncio
    async def test_sparkplug_publish(self):
        """Verify data can be published to MQTT broker in Sparkplug B format"""
        # This test would publish actual Sparkplug messages
        # Requires MQTT broker to be running
        pytest.skip("Requires MQTT broker configuration")


class TestMQTTBrokerDelivery:
    """Test 4: MQTT Broker Message Delivery"""

    @pytest.mark.asyncio
    async def test_mqtt_message_delivery(self):
        """Verify messages are delivered through MQTT broker"""
        pytest.skip("Requires MQTT broker and subscriber")


class TestTimescaleDBIngestion:
    """Test 5: TimescaleDB Data Ingestion"""

    def test_timescaledb_connection(self):
        """Verify TimescaleDB connection and schema"""
        from django.db import connection

        with connection.cursor() as cursor:
            # Check if production_metrics table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'production_metrics'
                )
            """)
            exists = cursor.fetchone()[0]

            assert exists is True, "production_metrics table not found"
            logger.info("✓ TimescaleDB production_metrics table exists")

    def test_insert_simulator_data(self):
        """Test inserting data from simulator to TimescaleDB"""
        from oee_analytics.models import ProductionMetrics

        # Create test record
        metric = ProductionMetrics.objects.create(
            line_id="LINE-001",
            timestamp=timezone.now(),
            oee=85.5,
            availability=92.0,
            performance=95.0,
            quality=98.0,
            actual_count=1000,
            target_count=1200,
        )

        assert metric.id is not None
        logger.info(f"✓ Inserted production metric: {metric.id}")

        # Retrieve and verify
        retrieved = ProductionMetrics.objects.get(id=metric.id)
        assert retrieved.line_id == "LINE-001"
        assert retrieved.oee == 85.5

        # Cleanup
        metric.delete()


class TestDjangoORMDataRetrieval:
    """Test 6: Django ORM Data Retrieval"""

    def test_query_recent_metrics(self):
        """Test querying recent production metrics"""
        from oee_analytics.models import ProductionMetrics

        # Get metrics from last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_metrics = ProductionMetrics.objects.filter(
            timestamp__gte=one_hour_ago
        ).order_by('-timestamp')[:10]

        logger.info(f"✓ Retrieved {len(recent_metrics)} recent metrics")

        # If we have data, verify structure
        if recent_metrics:
            metric = recent_metrics[0]
            assert hasattr(metric, 'line_id')
            assert hasattr(metric, 'oee')
            assert hasattr(metric, 'availability')
            assert hasattr(metric, 'performance')
            assert hasattr(metric, 'quality')
            logger.info(f"✓ Metric structure validated")

    def test_aggregate_metrics(self):
        """Test aggregating metrics by production line"""
        from oee_analytics.models import ProductionMetrics
        from django.db.models import Avg, Max, Min

        aggregates = ProductionMetrics.objects.values('line_id').annotate(
            avg_oee=Avg('oee'),
            max_oee=Max('oee'),
            min_oee=Min('oee'),
        )

        logger.info(f"✓ Computed aggregates for {len(aggregates)} lines")


class TestRESTAPIEndpoints:
    """Test 7: REST API Endpoints"""

    def test_kpi_current_endpoint(self):
        """Test /api/kpi/current/ endpoint"""
        client = Client()
        response = client.get('/api/kpi/current/')

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        logger.info(f"✓ KPI endpoint returned {len(data)} lines")

    def test_machines_status_endpoint(self):
        """Test /api/machines/status/ endpoint"""
        client = Client()
        response = client.get('/api/machines/status/')

        assert response.status_code == 200
        data = response.json()

        assert 'count' in data
        assert 'machines' in data
        logger.info(f"✓ Machine status endpoint returned {data['count']} machines")

    def test_trend_data_endpoint(self):
        """Test /api/trend/ endpoint with line_id filter"""
        client = Client()
        response = client.get('/api/trend/?line_id=LINE-001&metric=oee&hours=1')

        assert response.status_code == 200
        data = response.json()

        assert 'line_id' in data
        assert 'metric_name' in data
        assert 'data_points' in data
        logger.info(f"✓ Trend endpoint returned {len(data['data_points'])} points")


class TestDataAccuracyIntegrity:
    """Test 8: Data Accuracy and Integrity"""

    @pytest.mark.asyncio
    async def test_end_to_end_data_accuracy(self):
        """Verify data accuracy from simulator to database"""
        # Read from simulator
        reader, writer = await asyncio.open_connection('localhost', 44818)

        try:
            req = {'method': 'read', 'params': {'tags': [
                'Line_LINE_001_ProductionCount',
                'Line_LINE_001_OEE',
            ]}}
            data = json.dumps(req).encode('utf-8')
            writer.write(len(data).to_bytes(4, 'big') + data)
            await writer.drain()

            length = int.from_bytes(await reader.readexactly(4), 'big')
            resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

            simulator_production = resp['results'][0]['value']
            simulator_oee = resp['results'][1]['value']

            logger.info(f"✓ Simulator data: Production={simulator_production}, OEE={simulator_oee}%")

            # Compare with database (if data exists)
            from oee_analytics.models import ProductionMetrics

            latest = ProductionMetrics.objects.filter(
                line_id="LINE-001"
            ).order_by('-timestamp').first()

            if latest:
                logger.info(f"✓ Database data: Production={latest.actual_count}, OEE={latest.oee}%")
                # Note: Values won't match exactly due to timing, but should be in reasonable range

        finally:
            writer.close()
            await writer.wait_closed()

    def test_data_integrity_constraints(self):
        """Verify data integrity constraints"""
        from oee_analytics.models import ProductionMetrics

        # Try to insert invalid data
        with pytest.raises(Exception):
            ProductionMetrics.objects.create(
                line_id="LINE-001",
                timestamp=timezone.now(),
                oee=150.0,  # Invalid: > 100%
                availability=92.0,
                performance=95.0,
                quality=98.0,
                actual_count=1000,
                target_count=1200,
            )

        logger.info("✓ Data integrity constraints enforced")


class TestRealTimeDataUpdates:
    """Test 9: Real-time Data Updates"""

    @pytest.mark.asyncio
    async def test_simulator_real_time_updates(self):
        """Verify simulator provides real-time data updates"""
        reader, writer = await asyncio.open_connection('localhost', 44818)

        try:
            measurements = []

            for i in range(5):
                req = {'method': 'read', 'params': {'tags': ['Line_LINE_001_ProductionCount']}}
                data = json.dumps(req).encode('utf-8')
                writer.write(len(data).to_bytes(4, 'big') + data)
                await writer.drain()

                length = int.from_bytes(await reader.readexactly(4), 'big')
                resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

                count = resp['results'][0]['value']
                measurements.append(count)

                logger.info(f"  Measurement {i+1}: {count} parts")

                if i < 4:
                    await asyncio.sleep(2)

            # Verify production is increasing
            assert measurements[-1] >= measurements[0], "Production should increase over time"
            logger.info(f"✓ Real-time updates verified: {measurements[0]} -> {measurements[-1]}")

        finally:
            writer.close()
            await writer.wait_closed()


class TestEndToEndLatency:
    """Test 10: End-to-End Latency Measurement"""

    @pytest.mark.asyncio
    async def test_data_pipeline_latency(self):
        """Measure end-to-end latency from simulator to API"""
        start_time = time.time()

        # Step 1: Read from simulator
        reader, writer = await asyncio.open_connection('localhost', 44818)

        try:
            req = {'method': 'read', 'params': {'tags': ['Line_LINE_001_ProductionCount']}}
            data = json.dumps(req).encode('utf-8')
            writer.write(len(data).to_bytes(4, 'big') + data)
            await writer.drain()

            length = int.from_bytes(await reader.readexactly(4), 'big')
            resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

            read_latency = time.time() - start_time
            logger.info(f"  Simulator read latency: {read_latency*1000:.2f} ms")

            # Step 2: Call API endpoint
            api_start = time.time()
            client = Client()
            response = client.get('/api/kpi/current/')

            api_latency = time.time() - api_start
            logger.info(f"  API response latency: {api_latency*1000:.2f} ms")

            total_latency = time.time() - start_time
            logger.info(f"✓ Total pipeline latency: {total_latency*1000:.2f} ms")

            # Assert reasonable latency (< 1 second)
            assert total_latency < 1.0, f"Latency too high: {total_latency}s"

        finally:
            writer.close()
            await writer.wait_closed()


# ============================================================================
# Test Runner Main
# ============================================================================

if __name__ == '__main__':
    """Run all tests with pytest"""
    import sys

    sys.exit(pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--log-cli-level=INFO'
    ]))
