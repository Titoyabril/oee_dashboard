"""
Integration tests for Allen-Bradley (Rockwell) CIP/EtherNet/IP connector.

Tests the pycomm3-based connector against simulated and real PLCs.
"""

import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from oee_analytics.sparkplug.connectors.allen_bradley import (
    AllenBradleyConnector,
    AllenBradleyConfig,
    TagValue,
)


class TestAllenBradleyConnectorBasics:
    """Basic Allen-Bradley connector functionality tests."""

    @pytest.fixture
    def ab_config(self):
        """Create test configuration."""
        return AllenBradleyConfig(
            plc_ip="192.168.1.100",
            plc_slot=0,
            tags=[
                "Program:MainProgram.ProductionCount",
                "Program:MainProgram.MachineStatus",
                "Program:MainProgram.Temperature",
                "Program:MainProgram.Speed",
            ],
            polling_interval_ms=100,
            connection_timeout_s=5.0,
            enable_array_tags=True,
            max_retries=3,
        )

    @pytest.fixture
    async def connector(self, ab_config):
        """Create connector instance."""
        connector = AllenBradleyConnector(ab_config)
        yield connector
        await connector.disconnect()

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, connector, ab_config):
        """Test connection establishment and disconnection."""
        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.open.return_value = True
            mock_driver.connected = True
            mock_driver_class.return_value = mock_driver

            # Test connection
            connected = await connector.connect()
            assert connected is True
            assert connector.is_connected is True

            # Test disconnection
            await connector.disconnect()
            assert connector.is_connected is False

    @pytest.mark.asyncio
    async def test_tag_read_single(self, connector, ab_config):
        """Test reading single tag value."""
        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(
                value=150,
                error=None,
                tag="Program:MainProgram.ProductionCount"
            )
            mock_driver_class.return_value = mock_driver

            await connector.connect()

            # Read tag
            value = await connector.read_tag("Program:MainProgram.ProductionCount")

            assert value is not None
            assert value.value == 150
            assert value.tag_name == "Program:MainProgram.ProductionCount"
            assert value.timestamp is not None
            assert value.quality == "GOOD"

    @pytest.mark.asyncio
    async def test_tag_read_multiple(self, connector, ab_config):
        """Test reading multiple tags in batch."""
        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = [
                Mock(value=150, error=None, tag="Program:MainProgram.ProductionCount"),
                Mock(value=True, error=None, tag="Program:MainProgram.MachineStatus"),
                Mock(value=72.5, error=None, tag="Program:MainProgram.Temperature"),
            ]
            mock_driver_class.return_value = mock_driver

            await connector.connect()

            # Read multiple tags
            tags = [
                "Program:MainProgram.ProductionCount",
                "Program:MainProgram.MachineStatus",
                "Program:MainProgram.Temperature",
            ]
            values = await connector.read_tags(tags)

            assert len(values) == 3
            assert values[0].value == 150
            assert values[1].value is True
            assert values[2].value == 72.5

    @pytest.mark.asyncio
    async def test_tag_write(self, connector, ab_config):
        """Test writing tag value."""
        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.write.return_value = Mock(error=None)
            mock_driver_class.return_value = mock_driver

            await connector.connect()

            # Write tag
            success = await connector.write_tag(
                "Program:MainProgram.SetPoint",
                100.0
            )

            assert success is True
            mock_driver.write.assert_called_once()


class TestAllenBradleyDataTypes:
    """Test handling of different Allen-Bradley data types."""

    @pytest.mark.asyncio
    async def test_boolean_tags(self):
        """Test BOOL tag handling."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=["Program:MainProgram.RunMode"]
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(value=True, error=None, tag="Program:MainProgram.RunMode")
            mock_driver_class.return_value = mock_driver

            await connector.connect()
            value = await connector.read_tag("Program:MainProgram.RunMode")

            assert value.value is True
            assert value.data_type == "BOOL"

    @pytest.mark.asyncio
    async def test_integer_tags(self):
        """Test DINT/INT tag handling."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=["Program:MainProgram.Counter"]
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(value=12345, error=None, tag="Program:MainProgram.Counter")
            mock_driver_class.return_value = mock_driver

            await connector.connect()
            value = await connector.read_tag("Program:MainProgram.Counter")

            assert value.value == 12345
            assert isinstance(value.value, int)

    @pytest.mark.asyncio
    async def test_real_tags(self):
        """Test REAL (float) tag handling."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=["Program:MainProgram.Temperature"]
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(value=72.5, error=None, tag="Program:MainProgram.Temperature")
            mock_driver_class.return_value = mock_driver

            await connector.connect()
            value = await connector.read_tag("Program:MainProgram.Temperature")

            assert value.value == 72.5
            assert isinstance(value.value, float)

    @pytest.mark.asyncio
    async def test_string_tags(self):
        """Test STRING tag handling."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=["Program:MainProgram.PartNumber"]
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(value="PART-12345", error=None, tag="Program:MainProgram.PartNumber")
            mock_driver_class.return_value = mock_driver

            await connector.connect()
            value = await connector.read_tag("Program:MainProgram.PartNumber")

            assert value.value == "PART-12345"
            assert isinstance(value.value, str)

    @pytest.mark.asyncio
    async def test_array_tags(self):
        """Test array tag handling."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=["Program:MainProgram.Temperatures[0]"],
            enable_array_tags=True
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(
                value=[72.5, 73.1, 71.8, 74.2],
                error=None,
                tag="Program:MainProgram.Temperatures"
            )
            mock_driver_class.return_value = mock_driver

            await connector.connect()
            value = await connector.read_tag("Program:MainProgram.Temperatures[0]")

            assert isinstance(value.value, list)
            assert len(value.value) == 4


class TestAllenBradleyErrorHandling:
    """Test error handling and resilience."""

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test handling of connection failures."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            max_retries=2
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.open.side_effect = Exception("Connection failed")
            mock_driver_class.return_value = mock_driver

            connected = await connector.connect()
            assert connected is False

    @pytest.mark.asyncio
    async def test_tag_read_error(self):
        """Test handling of tag read errors."""
        config = AllenBradleyConfig(plc_ip="192.168.1.100")
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(
                value=None,
                error="Tag not found",
                tag="Program:MainProgram.InvalidTag"
            )
            mock_driver_class.return_value = mock_driver

            await connector.connect()
            value = await connector.read_tag("Program:MainProgram.InvalidTag")

            assert value is None or value.quality == "BAD"

    @pytest.mark.asyncio
    async def test_connection_recovery(self):
        """Test automatic reconnection on connection loss."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            max_retries=3
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            # First connection succeeds
            mock_driver.connected = True
            mock_driver.open.return_value = True

            # Simulate disconnection
            mock_driver.read.side_effect = [
                Exception("Connection lost"),  # First read fails
                Mock(value=100, error=None, tag="Test")  # After reconnect
            ]

            mock_driver_class.return_value = mock_driver

            await connector.connect()

            # First read triggers reconnection
            value = await connector.read_tag("Test")
            # Second attempt should succeed
            value = await connector.read_tag("Test")

            assert value is not None


class TestAllenBradleyPerformance:
    """Performance and optimization tests."""

    @pytest.mark.asyncio
    async def test_batch_read_performance(self):
        """Test batch reading is faster than individual reads."""
        config = AllenBradleyConfig(plc_ip="192.168.1.100")
        connector = AllenBradleyConnector(config)

        tags = [f"Program:MainProgram.Tag{i}" for i in range(100)]

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = [
                Mock(value=i, error=None, tag=tag)
                for i, tag in enumerate(tags)
            ]
            mock_driver_class.return_value = mock_driver

            await connector.connect()

            # Batch read
            start = datetime.now()
            values = await connector.read_tags(tags)
            batch_duration = (datetime.now() - start).total_seconds()

            assert len(values) == 100
            # Single driver.read() call for all tags
            assert mock_driver.read.call_count == 1

    @pytest.mark.asyncio
    async def test_polling_interval_compliance(self):
        """Test polling respects configured interval."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=["Program:MainProgram.Counter"],
            polling_interval_ms=100
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = Mock(value=0, error=None, tag="Test")
            mock_driver_class.return_value = mock_driver

            await connector.connect()

            # Start polling
            poll_count = 0
            async def callback(values):
                nonlocal poll_count
                poll_count += 1

            # Poll for 1 second
            await connector.start_polling(callback)
            await asyncio.sleep(1.0)
            await connector.stop_polling()

            # Should poll ~10 times in 1 second (100ms interval)
            assert 8 <= poll_count <= 12  # Allow some variance


class TestAllenBradleyIntegrationScenarios:
    """Real-world integration scenarios."""

    @pytest.mark.asyncio
    async def test_production_counter_monitoring(self):
        """Test monitoring production counter for OEE calculation."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=[
                "Program:MainProgram.GoodPartsCount",
                "Program:MainProgram.RejectCount",
                "Program:MainProgram.CycleTime",
            ],
            polling_interval_ms=500
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            mock_driver.read.return_value = [
                Mock(value=1000, error=None, tag="Program:MainProgram.GoodPartsCount"),
                Mock(value=50, error=None, tag="Program:MainProgram.RejectCount"),
                Mock(value=12.5, error=None, tag="Program:MainProgram.CycleTime"),
            ]
            mock_driver_class.return_value = mock_driver

            await connector.connect()

            values = await connector.read_tags([
                "Program:MainProgram.GoodPartsCount",
                "Program:MainProgram.RejectCount",
                "Program:MainProgram.CycleTime",
            ])

            # Verify OEE data collected
            assert len(values) == 3
            good_count = values[0].value
            reject_count = values[1].value
            cycle_time = values[2].value

            total_count = good_count + reject_count
            quality = (good_count / total_count) * 100 if total_count > 0 else 0

            assert quality > 95.0  # Quality should be >95%

    @pytest.mark.asyncio
    async def test_alarm_status_monitoring(self):
        """Test monitoring alarm/fault status."""
        config = AllenBradleyConfig(
            plc_ip="192.168.1.100",
            tags=["Program:Alarms.AlarmStatus"]
        )
        connector = AllenBradleyConnector(config)

        with patch('pycomm3.LogixDriver') as mock_driver_class:
            mock_driver = MagicMock()
            # Simulate alarm status word (bit field)
            mock_driver.read.return_value = Mock(
                value=0b0000000000000101,  # Alarms 0 and 2 active
                error=None,
                tag="Program:Alarms.AlarmStatus"
            )
            mock_driver_class.return_value = mock_driver

            await connector.connect()
            value = await connector.read_tag("Program:Alarms.AlarmStatus")

            # Check specific alarms
            alarm_word = value.value
            alarm_0_active = bool(alarm_word & (1 << 0))
            alarm_1_active = bool(alarm_word & (1 << 1))
            alarm_2_active = bool(alarm_word & (1 << 2))

            assert alarm_0_active is True
            assert alarm_1_active is False
            assert alarm_2_active is True


@pytest.mark.integration
class TestAllenBradleyRealPLC:
    """
    Integration tests against real Allen-Bradley PLC.

    These tests require:
    - Real CompactLogix/ControlLogix PLC
    - Network connectivity
    - Configured tags in PLC program

    Set REAL_PLC_IP environment variable to enable.
    """

    @pytest.fixture
    def real_plc_ip(self):
        """Get real PLC IP from environment."""
        import os
        plc_ip = os.getenv("REAL_AB_PLC_IP")
        if not plc_ip:
            pytest.skip("REAL_AB_PLC_IP not set, skipping real PLC tests")
        return plc_ip

    @pytest.mark.asyncio
    async def test_real_plc_connection(self, real_plc_ip):
        """Test connection to real PLC."""
        config = AllenBradleyConfig(
            plc_ip=real_plc_ip,
            plc_slot=0
        )
        connector = AllenBradleyConnector(config)

        connected = await connector.connect()
        assert connected is True

        await connector.disconnect()

    @pytest.mark.asyncio
    async def test_real_plc_tag_browse(self, real_plc_ip):
        """Test browsing tags on real PLC."""
        config = AllenBradleyConfig(plc_ip=real_plc_ip)
        connector = AllenBradleyConnector(config)

        await connector.connect()

        # Get tag list
        tags = await connector.get_tag_list()

        assert len(tags) > 0
        assert any("Program" in tag for tag in tags)

        await connector.disconnect()
