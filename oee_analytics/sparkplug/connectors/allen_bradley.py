"""
Allen-Bradley PLC Connector
Comprehensive implementation for all Allen-Bradley PLC families
Supports: ControlLogix, CompactLogix, MicroLogix, PLC-5, SLC-500, Micro800
"""

import asyncio
import os
import sys

# Import real drivers
try:
    from pycomm3 import LogixDriver as RealLogixDriver, SLCDriver
    PYCOMM3_AVAILABLE = True
except ImportError:
    RealLogixDriver = None
    SLCDriver = None
    PYCOMM3_AVAILABLE = False

# Import simulator driver
try:
    # Add simulators directory to path
    simulators_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'simulators')
    if simulators_path not in sys.path:
        sys.path.insert(0, simulators_path)

    from pycomm3_shim import SimulatorLogixDriver
    SIMULATOR_AVAILABLE = True
except ImportError:
    SimulatorLogixDriver = None
    SIMULATOR_AVAILABLE = False

from pylogix import PLC
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import struct
import logging
from dataclasses import dataclass
import re

from .base import (
    BasePLCConnector, PLCConnectionConfig, PLCTagDefinition,
    PLCDataPoint, PLCStatus, PLCConnectionError, PLCDataError
)


@dataclass
class AllenBradleyConfig(PLCConnectionConfig):
    """Extended configuration for Allen-Bradley PLCs"""
    plc_family: str = "ControlLogix"  # ControlLogix, CompactLogix, MicroLogix, PLC5, SLC500, Micro800
    processor_type: str = "AUTO"      # AUTO, 1756-L61, 1769-L32E, etc.

    # EtherNet/IP specific
    vendor_id: int = 0x001
    device_type: int = 0x0E
    product_code: int = 0x0000

    # Connection parameters
    micro800_port: int = 44818  # Micro800 uses different port
    use_connected_msg: bool = True
    simulator_mode: bool = False  # Use PLC simulator instead of real hardware

    # Legacy parameters for older PLCs
    node_address: Optional[int] = None  # For DH+ networks

    # Performance settings
    read_timeout: float = 10.0
    write_timeout: float = 10.0
    large_packet_support: bool = True


class AllenBradleyConnector(BasePLCConnector):
    """
    Allen-Bradley PLC Connector using pycomm3 and pylogix
    Supports all major AB PLC families with optimized communication
    """
    
    # Data type mappings for different PLC families
    LOGIX_DATA_TYPES = {
        'BOOL': 'BOOL',
        'SINT': 'SINT',
        'INT': 'INT', 
        'DINT': 'DINT',
        'LINT': 'LINT',
        'USINT': 'USINT',
        'UINT': 'UINT',
        'UDINT': 'UDINT',
        'ULINT': 'ULINT',
        'REAL': 'REAL',
        'LREAL': 'LREAL',
        'STRING': 'STRING',
    }
    
    # Legacy data types for older PLCs
    LEGACY_DATA_TYPES = {
        'B': 'BOOL',    # Bit
        'N': 'INT',     # Integer
        'F': 'REAL',    # Float
        'S': 'STRING',  # String
        'T': 'TIMER',   # Timer
        'C': 'COUNTER', # Counter
        'R': 'CONTROL', # Control
    }
    
    def __init__(self, config: Union[PLCConnectionConfig, AllenBradleyConfig],
                 logger: Optional[logging.Logger] = None):
        # Convert to AB-specific config if needed
        if isinstance(config, PLCConnectionConfig) and not isinstance(config, AllenBradleyConfig):
            config = AllenBradleyConfig(**config.__dict__)

        super().__init__(config, logger)
        self.driver = None
        self.legacy_driver = None
        self.plc_family = config.plc_family.upper()
        self.simulator_mode = getattr(config, 'simulator_mode', False)

        if self.simulator_mode:
            self.logger.info(f"Allen-Bradley connector initialized in SIMULATOR MODE for {self.config.host}")
            if not SIMULATOR_AVAILABLE:
                raise PLCConnectionError("Simulator mode requested but simulator not available")
        
    async def connect(self) -> bool:
        """Establish connection to Allen-Bradley PLC"""
        try:
            self._update_status(PLCStatus.CONNECTING)
            
            # Select appropriate driver based on PLC family
            if self.plc_family in ['CONTROLLOGIX', 'COMPACTLOGIX', 'MICRO800']:
                await self._connect_logix()
            elif self.plc_family in ['MICROLOGIX', 'SLC500', 'PLC5']:
                await self._connect_legacy()
            else:
                raise PLCConnectionError(f"Unsupported PLC family: {self.plc_family}")
            
            # Test connection with a simple read
            await self._test_connection()
            
            self._update_status(PLCStatus.CONNECTED)
            self.logger.info(f"Connected to Allen-Bradley {self.plc_family} PLC at {self.config.host}")
            
            return True
            
        except Exception as e:
            error_msg = f"AB connection failed: {str(e)}"
            self._update_status(PLCStatus.ERROR, error_msg)
            self._increment_error_stats()
            raise PLCConnectionError(error_msg)
    
    async def _connect_logix(self):
        """Connect to Logix-based PLCs (ControlLogix, CompactLogix, Micro800)"""
        # Choose driver based on simulator mode
        if self.simulator_mode:
            self.driver = SimulatorLogixDriver(self.config.host, port=self.config.port)
        else:
            if not PYCOMM3_AVAILABLE:
                raise PLCConnectionError("pycomm3 not installed - cannot connect to real PLC")
            self.driver = RealLogixDriver(self.config.host, self.config.port)

        # Configure driver settings
        if hasattr(self.config, 'read_timeout') and hasattr(self.driver, 'socket_timeout'):
            self.driver.socket_timeout = self.config.read_timeout

        # Open connection
        await asyncio.get_event_loop().run_in_executor(
            None, self.driver.open
        )

        if not self.driver.connected:
            raise PLCConnectionError("Failed to connect to Logix PLC")
    
    async def _connect_legacy(self):
        """Connect to legacy PLCs (MicroLogix, SLC-500, PLC-5)"""
        if self.plc_family in ['MICROLOGIX']:
            # Use pycomm3 for MicroLogix
            self.driver = LogixDriver(self.config.host, self.config.port)
            await asyncio.get_event_loop().run_in_executor(
                None, self.driver.open
            )
        else:
            # Use pylogix for SLC-500 and PLC-5
            self.legacy_driver = PLC()
            self.legacy_driver.IPAddress = self.config.host
            if hasattr(self.config, 'node_address') and self.config.node_address:
                self.legacy_driver.Route = f"1,{self.config.node_address}"
    
    async def disconnect(self) -> bool:
        """Disconnect from Allen-Bradley PLC"""
        try:
            if self.driver:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.driver.close
                )
                self.driver = None
            
            if self.legacy_driver:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.legacy_driver.Close
                )
                self.legacy_driver = None
            
            self._update_status(PLCStatus.DISCONNECTED)
            return True
            
        except Exception as e:
            error_msg = f"AB disconnect failed: {str(e)}"
            self._update_status(PLCStatus.ERROR, error_msg)
            self.logger.error(error_msg)
            return False
    
    async def read_single(self, address: str, data_type: str) -> PLCDataPoint:
        """Read a single data point from AB PLC"""
        if not self._is_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        try:
            if self.driver:
                # Use pycomm3 for Logix PLCs
                result = await self._read_logix_tag(address, data_type)
            elif self.legacy_driver:
                # Use pylogix for legacy PLCs
                result = await self._read_legacy_tag(address, data_type)
            else:
                raise PLCConnectionError("No active driver")
            
            self._increment_read_stats()
            return result
            
        except Exception as e:
            self._increment_error_stats()
            error_msg = f"Failed to read {address}: {str(e)}"
            self.logger.error(error_msg)
            
            return PLCDataPoint(
                address=address,
                value=None,
                data_type=data_type,
                quality=0,  # Bad quality
                timestamp=datetime.now(),
                error=error_msg
            )
    
    async def _read_logix_tag(self, address: str, data_type: str) -> PLCDataPoint:
        """Read tag from Logix PLC using pycomm3"""
        # Parse complex tag addresses (e.g., "MyArray[5].Value")
        tag_name = self._parse_logix_address(address)
        
        # Read from PLC
        result = await asyncio.get_event_loop().run_in_executor(
            None, self.driver.read, tag_name
        )
        
        if result.error:
            raise PLCDataError(f"Read error: {result.error}")
        
        # Convert value based on data type
        value = self._convert_logix_value(result.value, data_type)
        
        return PLCDataPoint(
            address=address,
            value=value,
            data_type=data_type,
            quality=192,  # Good quality
            timestamp=datetime.now()
        )
    
    async def _read_legacy_tag(self, address: str, data_type: str) -> PLCDataPoint:
        """Read tag from legacy PLC using pylogix"""
        # Parse legacy address format (e.g., "N7:0", "B3:0/5")
        parsed_address = self._parse_legacy_address(address)
        
        # Read from PLC
        result = await asyncio.get_event_loop().run_in_executor(
            None, self.legacy_driver.Read, parsed_address
        )
        
        if result.Status != 'Success':
            raise PLCDataError(f"Read error: {result.Status}")
        
        # Convert value based on data type
        value = self._convert_legacy_value(result.Value, data_type)
        
        return PLCDataPoint(
            address=address,
            value=value,
            data_type=data_type,
            quality=192,  # Good quality
            timestamp=datetime.now()
        )
    
    async def read_multiple(self, addresses: List[Tuple[str, str]]) -> List[PLCDataPoint]:
        """Read multiple data points from AB PLC in batch"""
        if not self._is_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        results = []
        
        if self.driver:
            # Use batch read for Logix PLCs
            results = await self._read_logix_batch(addresses)
        elif self.legacy_driver:
            # Legacy PLCs - use individual reads
            for address, data_type in addresses:
                result = await self.read_single(address, data_type)
                results.append(result)
        
        return results
    
    async def _read_logix_batch(self, addresses: List[Tuple[str, str]]) -> List[PLCDataPoint]:
        """Batch read from Logix PLC"""
        tag_names = [self._parse_logix_address(addr) for addr, _ in addresses]
        
        # Perform batch read
        results = await asyncio.get_event_loop().run_in_executor(
            None, self.driver.read, *tag_names
        )
        
        # Process results
        data_points = []
        for i, (address, data_type) in enumerate(addresses):
            if i < len(results):
                result = results[i]
                if result.error:
                    data_point = PLCDataPoint(
                        address=address,
                        value=None,
                        data_type=data_type,
                        quality=0,
                        timestamp=datetime.now(),
                        error=result.error
                    )
                else:
                    value = self._convert_logix_value(result.value, data_type)
                    data_point = PLCDataPoint(
                        address=address,
                        value=value,
                        data_type=data_type,
                        quality=192,
                        timestamp=datetime.now()
                    )
                data_points.append(data_point)
        
        return data_points
    
    async def write_single(self, address: str, value: Any, data_type: str) -> bool:
        """Write a single value to AB PLC"""
        if not self._is_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        try:
            if self.driver:
                success = await self._write_logix_tag(address, value, data_type)
            elif self.legacy_driver:
                success = await self._write_legacy_tag(address, value, data_type)
            else:
                raise PLCConnectionError("No active driver")
            
            if success:
                self._increment_write_stats()
            else:
                self._increment_error_stats()
            
            return success
            
        except Exception as e:
            self._increment_error_stats()
            error_msg = f"Failed to write {address}: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    async def _write_logix_tag(self, address: str, value: Any, data_type: str) -> bool:
        """Write tag to Logix PLC using pycomm3"""
        tag_name = self._parse_logix_address(address)
        converted_value = self._prepare_logix_write_value(value, data_type)
        
        result = await asyncio.get_event_loop().run_in_executor(
            None, self.driver.write, tag_name, converted_value
        )
        
        if result.error:
            self.logger.error(f"Write error for {address}: {result.error}")
            return False
        
        return True
    
    async def _write_legacy_tag(self, address: str, value: Any, data_type: str) -> bool:
        """Write tag to legacy PLC using pylogix"""
        parsed_address = self._parse_legacy_address(address)
        converted_value = self._prepare_legacy_write_value(value, data_type)
        
        result = await asyncio.get_event_loop().run_in_executor(
            None, self.legacy_driver.Write, parsed_address, converted_value
        )
        
        if result.Status != 'Success':
            self.logger.error(f"Write error for {address}: {result.Status}")
            return False
        
        return True
    
    async def write_multiple(self, writes: List[Tuple[str, Any, str]]) -> List[bool]:
        """Write multiple values to AB PLC"""
        results = []
        
        # For now, use individual writes
        # TODO: Implement batch writing for Logix PLCs
        for address, value, data_type in writes:
            success = await self.write_single(address, value, data_type)
            results.append(success)
        
        return results
    
    async def discover_tags(self) -> List[PLCTagDefinition]:
        """Auto-discover available tags in AB PLC"""
        if not self._is_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        discovered_tags = []
        
        try:
            if self.driver and hasattr(self.driver, 'get_tag_list'):
                # Get tag list from Logix PLC
                tag_list = await asyncio.get_event_loop().run_in_executor(
                    None, self.driver.get_tag_list
                )
                
                for tag_info in tag_list:
                    tag_def = PLCTagDefinition(
                        name=tag_info['tag_name'],
                        address=tag_info['tag_name'],
                        data_type=tag_info['data_type'],
                        description=f"Auto-discovered {tag_info['data_type']} tag"
                    )
                    discovered_tags.append(tag_def)
            
            elif self.legacy_driver:
                # For legacy PLCs, create common address patterns
                discovered_tags = self._get_common_legacy_tags()
            
        except Exception as e:
            self.logger.error(f"Tag discovery failed: {e}")
        
        return discovered_tags
    
    def validate_address(self, address: str) -> bool:
        """Validate AB address format"""
        try:
            if self.plc_family in ['CONTROLLOGIX', 'COMPACTLOGIX', 'MICRO800']:
                return self._validate_logix_address(address)
            else:
                return self._validate_legacy_address(address)
        except:
            return False
    
    # Helper methods
    
    def _is_connected(self) -> bool:
        """Check if PLC is connected"""
        if self.driver:
            return getattr(self.driver, 'connected', False)
        elif self.legacy_driver:
            return True  # pylogix doesn't have a connection state
        return False
    
    async def _test_connection(self):
        """Test connection with a simple operation"""
        if self.driver:
            # Try to get PLC info
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, getattr, self.driver, 'info'
                )
            except:
                pass  # Info not available on all drivers
        elif self.legacy_driver:
            # Try a simple read
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.legacy_driver.Read, "S:1/15"  # CPU scan time bit
                )
            except:
                pass  # May not be available on all PLCs
    
    def _parse_logix_address(self, address: str) -> str:
        """Parse and validate Logix tag address"""
        # Logix tags support complex addressing:
        # - SimpleTag
        # - ArrayTag[5]
        # - UDTTag.Member
        # - ComplexTag[2].Member[3].SubMember
        
        # For now, return as-is since pycomm3 handles complex addressing
        return address.strip()
    
    def _parse_legacy_address(self, address: str) -> str:
        """Parse legacy PLC address format"""
        # Legacy format examples:
        # N7:0 (Integer file 7, element 0)
        # B3:0/5 (Binary file 3, element 0, bit 5)
        # T4:0.PRE (Timer file 4, element 0, preset value)
        # C5:0.ACC (Counter file 5, element 0, accumulator value)
        
        return address.strip().upper()
    
    def _validate_logix_address(self, address: str) -> bool:
        """Validate Logix tag address format"""
        # Basic validation for Logix tag names
        # Must start with letter or underscore, contain only alphanumeric, underscore, brackets, dots
        pattern = r'^[A-Za-z_][A-Za-z0-9_\[\]\.]*$'
        return bool(re.match(pattern, address))
    
    def _validate_legacy_address(self, address: str) -> bool:
        """Validate legacy PLC address format"""
        # Pattern for legacy addresses like N7:0, B3:0/5, T4:0.PRE
        patterns = [
            r'^[NBFTCSR]\d+:\d+$',           # Basic file:element
            r'^[NBFTCSR]\d+:\d+/\d+$',       # With bit
            r'^[NBFTCSR]\d+:\d+\.[A-Z]+$',   # With member
        ]
        
        address_upper = address.upper()
        return any(re.match(pattern, address_upper) for pattern in patterns)
    
    def _convert_logix_value(self, value: Any, data_type: str) -> Any:
        """Convert Logix value to proper Python type"""
        if value is None:
            return None
        
        data_type = data_type.upper()
        
        try:
            if data_type == 'BOOL':
                return bool(value)
            elif data_type in ['SINT', 'INT', 'DINT', 'LINT']:
                return int(value)
            elif data_type in ['USINT', 'UINT', 'UDINT', 'ULINT']:
                return int(value)
            elif data_type in ['REAL', 'LREAL']:
                return float(value)
            elif data_type == 'STRING':
                return str(value)
            else:
                return value
        except (ValueError, TypeError):
            return value
    
    def _convert_legacy_value(self, value: Any, data_type: str) -> Any:
        """Convert legacy PLC value to proper Python type"""
        if value is None:
            return None
        
        data_type = data_type.upper()
        
        try:
            if data_type in ['B', 'BOOL']:
                return bool(value)
            elif data_type in ['N', 'INT']:
                return int(value)
            elif data_type in ['F', 'REAL']:
                return float(value)
            elif data_type in ['S', 'STRING']:
                return str(value)
            else:
                return value
        except (ValueError, TypeError):
            return value
    
    def _prepare_logix_write_value(self, value: Any, data_type: str) -> Any:
        """Prepare value for writing to Logix PLC"""
        return self._convert_logix_value(value, data_type)
    
    def _prepare_legacy_write_value(self, value: Any, data_type: str) -> Any:
        """Prepare value for writing to legacy PLC"""
        return self._convert_legacy_value(value, data_type)
    
    def _get_common_legacy_tags(self) -> List[PLCTagDefinition]:
        """Get common tags for legacy PLCs"""
        return [
            PLCTagDefinition(
                name="CPU_SCAN_TIME",
                address="S:3",
                data_type="INT",
                description="CPU scan time in 0.01ms units",
                units="0.01ms"
            ),
            PLCTagDefinition(
                name="FREE_RUNNING_CLOCK",
                address="S:4",
                data_type="INT", 
                description="Free running clock"
            ),
            PLCTagDefinition(
                name="MAJOR_FAULT_BIT",
                address="S:1/13",
                data_type="BOOL",
                description="Major fault bit"
            ),
            PLCTagDefinition(
                name="MINOR_FAULT_BIT", 
                address="S:1/14",
                data_type="BOOL",
                description="Minor fault bit"
            ),
        ]


# Register the connector
from .base import PLCConnectorFactory
PLCConnectorFactory.register_connector('ALLEN_BRADLEY', AllenBradleyConnector)
PLCConnectorFactory.register_connector('AB', AllenBradleyConnector)
PLCConnectorFactory.register_connector('CONTROLLOGIX', AllenBradleyConnector)
PLCConnectorFactory.register_connector('COMPACTLOGIX', AllenBradleyConnector)
PLCConnectorFactory.register_connector('MICROLOGIX', AllenBradleyConnector)