"""
Integration tests for Siemens S7 PLC connector.

Tests the python-snap7 based connector against simulated and real S7 PLCs.
"""

import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import struct

from oee_analytics.sparkplug.connectors.siemens import (
    SiemensS7Connector,
    SiemensS7Config,
)
from oee_analytics.sparkplug.connectors.base import PLCDataPoint, PLCTagDefinition


class TestSiemensS7ConnectorBasics:
    """Basic Siemens S7 connector functionality tests."""

    @pytest.fixture
    def s7_config(self):
        """Create test configuration."""
        return SiemensS7Config(
            host="192.168.0.1",
            rack=0,
            slot=1,
            port=102,
            timeout=5.0,
            plc_type="S7_1200",
        )

    @pytest.fixture
    async def connector(self, s7_config):
        """Create connector instance."""
        connector = SiemensS7Connector(s7_config)
        yield connector
        await connector.disconnect()

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, connector, s7_config):
        """Test connection establishment and disconnection."""
        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_connected.return_value = True
            mock_client_class.return_value = mock_client

            # Test connection
            connected = await connector.connect()
            assert connected is True
            assert connector.is_connected is True

            # Verify correct connection parameters
            mock_client.connect.assert_called_once_with(
                s7_config.plc_ip,
                s7_config.plc_rack,
                s7_config.plc_slot
            )

            # Test disconnection
            await connector.disconnect()
            mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_db_int(self, connector, s7_config):
        """Test reading INT from data block."""
        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            # Simulate reading 2 bytes for INT (big-endian)
            mock_client.db_read.return_value = struct.pack('>h', 1500)
            mock_client_class.return_value = mock_client

            await connector.connect()

            # Read INT tag
            value = await connector.read_tag("Production.GoodCount")

            assert value is not None
            assert value.value == 1500
            assert value.tag_name == "Production.GoodCount"
            assert value.data_type == "INT"
            mock_client.db_read.assert_called_with(1, 0, 2)

    @pytest.mark.asyncio
    async def test_read_db_real(self, connector, s7_config):
        """Test reading REAL (float) from data block."""
        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            # Simulate reading 4 bytes for REAL (big-endian float)
            mock_client.db_read.return_value = struct.pack('>f', 75.5)
            mock_client_class.return_value = mock_client

            await connector.connect()

            # Read REAL tag
            value = await connector.read_tag("Production.Speed")

            assert value is not None
            assert abs(value.value - 75.5) < 0.01
            assert value.data_type == "REAL"
            mock_client.db_read.assert_called_with(1, 4, 4)

    @pytest.mark.asyncio
    async def test_read_db_bool(self, connector, s7_config):
        """Test reading BOOL from data block."""
        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            # Simulate reading 1 byte with bit 0 set
            mock_client.db_read.return_value = bytes([0b00000001])
            mock_client_class.return_value = mock_client

            await connector.connect()

            # Read BOOL tag
            value = await connector.read_tag("Production.Running")

            assert value is not None
            assert value.value is True
            assert value.data_type == "BOOL"
            mock_client.db_read.assert_called_with(1, 8, 1)

    @pytest.mark.asyncio
    async def test_write_db_int(self, connector, s7_config):
        """Test writing INT to data block."""
        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.db_write.return_value = 0  # Success
            mock_client_class.return_value = mock_client

            await connector.connect()

            # Write INT tag
            success = await connector.write_tag("Production.GoodCount", 2000)

            assert success is True
            # Verify correct data written
            expected_data = struct.pack('>h', 2000)
            mock_client.db_write.assert_called_once()
            call_args = mock_client.db_write.call_args[0]
            assert call_args[0] == 1  # DB number
            assert call_args[1] == 0  # Offset
            assert call_args[2] == expected_data


class TestSiemensS7DataTypes:
    """Test handling of different S7 data types."""

    @pytest.mark.asyncio
    async def test_byte_type(self):
        """Test BYTE data type (8-bit unsigned)."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Test",
                    tags=[{"name": "Status", "offset": 0, "type": "BYTE"}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.db_read.return_value = bytes([0xFF])
            mock_client_class.return_value = mock_client

            await connector.connect()
            value = await connector.read_tag("Test.Status")

            assert value.value == 255
            assert value.data_type == "BYTE"

    @pytest.mark.asyncio
    async def test_word_type(self):
        """Test WORD data type (16-bit unsigned)."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Test",
                    tags=[{"name": "Value", "offset": 0, "type": "WORD"}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.db_read.return_value = struct.pack('>H', 65535)
            mock_client_class.return_value = mock_client

            await connector.connect()
            value = await connector.read_tag("Test.Value")

            assert value.value == 65535
            assert value.data_type == "WORD"

    @pytest.mark.asyncio
    async def test_dword_type(self):
        """Test DWORD data type (32-bit unsigned)."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Test",
                    tags=[{"name": "Counter", "offset": 0, "type": "DWORD"}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.db_read.return_value = struct.pack('>I', 123456789)
            mock_client_class.return_value = mock_client

            await connector.connect()
            value = await connector.read_tag("Test.Counter")

            assert value.value == 123456789
            assert value.data_type == "DWORD"

    @pytest.mark.asyncio
    async def test_dint_type(self):
        """Test DINT data type (32-bit signed)."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Test",
                    tags=[{"name": "Position", "offset": 0, "type": "DINT"}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.db_read.return_value = struct.pack('>i', -12345)
            mock_client_class.return_value = mock_client

            await connector.connect()
            value = await connector.read_tag("Test.Position")

            assert value.value == -12345
            assert value.data_type == "DINT"

    @pytest.mark.asyncio
    async def test_string_type(self):
        """Test STRING data type."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Test",
                    tags=[{"name": "PartID", "offset": 0, "type": "STRING", "length": 20}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            # S7 STRING format: max_len (1 byte) + actual_len (1 byte) + chars
            string_data = bytes([20, 8]) + b"PART-123" + bytes(12)  # Padded to 20
            mock_client.db_read.return_value = string_data
            mock_client_class.return_value = mock_client

            await connector.connect()
            value = await connector.read_tag("Test.PartID")

            assert value.value == "PART-123"
            assert value.data_type == "STRING"


class TestSiemensS7MemoryAreas:
    """Test different S7 memory areas (DB, M, I, Q)."""

    @pytest.mark.asyncio
    async def test_merker_memory_read(self):
        """Test reading from Merker (M) memory area."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            memory_areas=[
                {"area": "M", "offset": 0, "size": 100, "name": "Merker"}
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.mb_read.return_value = bytes(100)
            mock_client_class.return_value = mock_client

            await connector.connect()
            # Read M10.0 (byte 10, bit 0)
            value = await connector.read_memory("M", 10, "BOOL", bit=0)

            assert value is not None
            mock_client.mb_read.assert_called()

    @pytest.mark.asyncio
    async def test_input_memory_read(self):
        """Test reading from Input (I) memory area."""
        config = SiemensS7Config(plc_ip="192.168.0.1")
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.eb_read.return_value = bytes([0xFF])
            mock_client_class.return_value = mock_client

            await connector.connect()
            # Read I0.0
            value = await connector.read_memory("I", 0, "BYTE")

            assert value.value == 255

    @pytest.mark.asyncio
    async def test_output_memory_write(self):
        """Test writing to Output (Q) memory area."""
        config = SiemensS7Config(plc_ip="192.168.0.1")
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.ab_write.return_value = 0
            mock_client_class.return_value = mock_client

            await connector.connect()
            # Write Q0.0 = True
            success = await connector.write_memory("Q", 0, "BOOL", True, bit=0)

            assert success is True


class TestSiemensS7ErrorHandling:
    """Test error handling and resilience."""

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """Test connection timeout handling."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            connection_timeout_s=1.0
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.connect.side_effect = Exception("Connection timeout")
            mock_client_class.return_value = mock_client

            connected = await connector.connect()
            assert connected is False

    @pytest.mark.asyncio
    async def test_read_error_recovery(self):
        """Test automatic recovery from read errors."""
        config = SiemensS7Config(plc_ip="192.168.0.1")
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            # First read fails, second succeeds
            mock_client.db_read.side_effect = [
                Exception("Read error"),
                struct.pack('>h', 100)
            ]
            mock_client_class.return_value = mock_client

            await connector.connect()

            # Should retry and succeed
            value = await connector.read_tag("Production.GoodCount")
            # Implementation should handle retry

    @pytest.mark.asyncio
    async def test_invalid_db_number(self):
        """Test handling of invalid DB number."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=9999,  # Invalid
                    name="Invalid",
                    tags=[{"name": "Test", "offset": 0, "type": "INT"}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.db_read.side_effect = Exception("DB not found")
            mock_client_class.return_value = mock_client

            await connector.connect()
            value = await connector.read_tag("Invalid.Test")

            assert value is None or value.quality == "BAD"


class TestSiemensS7Performance:
    """Performance and optimization tests."""

    @pytest.mark.asyncio
    async def test_bulk_read_optimization(self):
        """Test optimized bulk reading of contiguous tags."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Production",
                    tags=[
                        {"name": "Count1", "offset": 0, "type": "INT"},
                        {"name": "Count2", "offset": 2, "type": "INT"},
                        {"name": "Count3", "offset": 4, "type": "INT"},
                        {"name": "Count4", "offset": 6, "type": "INT"},
                    ]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            # Return 8 bytes (4 INTs)
            mock_client.db_read.return_value = struct.pack('>hhhh', 100, 200, 300, 400)
            mock_client_class.return_value = mock_client

            await connector.connect()

            # Bulk read should use single DB read
            values = await connector.read_tags([
                "Production.Count1",
                "Production.Count2",
                "Production.Count3",
                "Production.Count4",
            ])

            assert len(values) == 4
            assert values[0].value == 100
            assert values[3].value == 400
            # Should read once (offset 0, length 8)
            assert mock_client.db_read.call_count == 1

    @pytest.mark.asyncio
    async def test_polling_performance(self):
        """Test polling loop performance."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            polling_interval_ms=100,
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Test",
                    tags=[{"name": "Value", "offset": 0, "type": "INT"}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.db_read.return_value = struct.pack('>h', 100)
            mock_client_class.return_value = mock_client

            await connector.connect()

            poll_count = 0
            async def callback(values):
                nonlocal poll_count
                poll_count += 1

            await connector.start_polling(callback)
            await asyncio.sleep(1.0)
            await connector.stop_polling()

            # Should poll ~10 times in 1 second
            assert 8 <= poll_count <= 12


class TestSiemensS7IntegrationScenarios:
    """Real-world integration scenarios."""

    @pytest.mark.asyncio
    async def test_oee_data_collection(self):
        """Test collecting OEE data from S7 PLC."""
        config = SiemensS7Config(
            plc_ip="192.168.0.1",
            data_blocks=[
                S7DataBlock(
                    db_number=100,
                    name="OEE",
                    tags=[
                        {"name": "TotalCount", "offset": 0, "type": "DINT"},
                        {"name": "GoodCount", "offset": 4, "type": "DINT"},
                        {"name": "Runtime", "offset": 8, "type": "DINT"},
                        {"name": "IdealCycleTime", "offset": 12, "type": "REAL"},
                    ]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        with patch('snap7.client.Client') as mock_client_class:
            mock_client = MagicMock()
            # Pack OEE data
            data = struct.pack('>iif', 1000, 950, 28800)  # Total, good, runtime (8hrs)
            data += struct.pack('>f', 30.0)  # Ideal cycle time
            mock_client.db_read.return_value = data
            mock_client_class.return_value = mock_client

            await connector.connect()

            values = await connector.read_tags([
                "OEE.TotalCount",
                "OEE.GoodCount",
                "OEE.Runtime",
                "OEE.IdealCycleTime",
            ])

            # Calculate OEE
            total_count = values[0].value
            good_count = values[1].value
            runtime = values[2].value
            ideal_cycle = values[3].value

            quality = (good_count / total_count * 100) if total_count > 0 else 0
            performance = (total_count * ideal_cycle / runtime * 100) if runtime > 0 else 0

            assert quality == 95.0
            assert abs(performance - 104.17) < 1.0  # Performance > 100% is possible


@pytest.mark.integration
class TestSiemensS7RealPLC:
    """
    Integration tests against real Siemens S7 PLC.

    These tests require:
    - Real S7-300/400/1200/1500 PLC
    - Network connectivity
    - Configured data blocks

    Set REAL_S7_PLC_IP environment variable to enable.
    """

    @pytest.fixture
    def real_plc_ip(self):
        """Get real PLC IP from environment."""
        import os
        plc_ip = os.getenv("REAL_S7_PLC_IP")
        if not plc_ip:
            pytest.skip("REAL_S7_PLC_IP not set, skipping real PLC tests")
        return plc_ip

    @pytest.mark.asyncio
    async def test_real_plc_connection(self, real_plc_ip):
        """Test connection to real S7 PLC."""
        config = SiemensS7Config(
            plc_ip=real_plc_ip,
            plc_rack=0,
            plc_slot=1,
            plc_type="S7-1200"
        )
        connector = SiemensS7Connector(config)

        connected = await connector.connect()
        assert connected is True

        await connector.disconnect()

    @pytest.mark.asyncio
    async def test_real_plc_db_read(self, real_plc_ip):
        """Test reading from real PLC data block."""
        config = SiemensS7Config(
            plc_ip=real_plc_ip,
            data_blocks=[
                S7DataBlock(
                    db_number=1,
                    name="Test",
                    tags=[{"name": "Value", "offset": 0, "type": "INT"}]
                )
            ]
        )
        connector = SiemensS7Connector(config)

        await connector.connect()
        value = await connector.read_tag("Test.Value")

        assert value is not None
        assert value.quality == "GOOD"

        await connector.disconnect()
