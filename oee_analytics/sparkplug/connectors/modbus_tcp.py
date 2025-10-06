"""
Modbus TCP PLC Connector
Standard Modbus TCP/IP implementation for industrial devices
Supports: Schneider, Mitsubishi, Omron, ABB, and generic Modbus devices
"""

import asyncio
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime
import struct
import logging
from dataclasses import dataclass

try:
    from pymodbus.client import AsyncModbusTcpClient
    from pymodbus.constants import Endian
    from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
    PYMODBUS_AVAILABLE = True
except ImportError:
    AsyncModbusTcpClient = None
    Endian = None
    BinaryPayloadDecoder = None
    BinaryPayloadBuilder = None
    PYMODBUS_AVAILABLE = False

from .base import (
    BasePLCConnector, PLCConnectionConfig, PLCTagDefinition,
    PLCDataPoint, PLCStatus, PLCConnectionError, PLCDataError
)


@dataclass
class ModbusTCPConfig(PLCConnectionConfig):
    """Extended configuration for Modbus TCP"""
    unit_id: int = 1                    # Modbus slave/unit ID (1-247)
    byte_order: str = "BIG"             # BIG or LITTLE endian
    word_order: str = "BIG"             # For 32-bit values (BIG or LITTLE)

    # Function code preferences
    use_fc3: bool = True                # Use FC3 (Read Holding Registers)
    use_fc4: bool = False               # Use FC4 (Read Input Registers)

    # Register ranges (for address offset calculation)
    holding_register_start: int = 0
    input_register_start: int = 10000
    coil_start: int = 0
    discrete_input_start: int = 10000

    # Performance tuning
    max_count_per_read: int = 100       # Max registers per read operation
    max_count_per_write: int = 100      # Max registers per write operation

    # Retry configuration
    retry_on_error: bool = True
    max_retries: int = 3
    retry_delay: float = 0.5            # Seconds between retries


class ModbusTCPConnector(BasePLCConnector):
    """
    Modbus TCP Connector using pymodbus
    Supports standard Modbus addressing and data types
    """

    # Data type size mappings (in 16-bit registers)
    MODBUS_DATA_TYPES = {
        'BOOL': 1,      # 1 bit (uses 1 register)
        'INT16': 1,     # 16-bit signed integer
        'UINT16': 1,    # 16-bit unsigned integer
        'INT32': 2,     # 32-bit signed integer
        'UINT32': 2,    # 32-bit unsigned integer
        'FLOAT32': 2,   # 32-bit IEEE 754 float
        'INT64': 4,     # 64-bit signed integer
        'UINT64': 4,    # 64-bit unsigned integer
        'FLOAT64': 4,   # 64-bit IEEE 754 float
        'STRING': None, # Variable length
    }

    def __init__(self, config: Union[PLCConnectionConfig, ModbusTCPConfig],
                 logger: Optional[logging.Logger] = None):
        """Initialize Modbus TCP connector"""
        if not PYMODBUS_AVAILABLE:
            raise ImportError("pymodbus library not available. Install with: pip install pymodbus")

        # Convert to Modbus-specific config if needed
        if isinstance(config, PLCConnectionConfig) and not isinstance(config, ModbusTCPConfig):
            config = ModbusTCPConfig(**config.__dict__)

        super().__init__(config, logger)
        self.client: Optional[AsyncModbusTcpClient] = None
        self.unit_id = config.unit_id

        # Set endianness for payload encoding/decoding
        self.byte_order = Endian.BIG if config.byte_order == "BIG" else Endian.LITTLE
        self.word_order = Endian.BIG if config.word_order == "BIG" else Endian.LITTLE

        # Set default port if not specified
        if self.config.port == 102:  # Default S7 port
            self.config.port = 502   # Modbus TCP default port

    async def connect(self) -> bool:
        """Establish connection to Modbus TCP device"""
        try:
            self._update_status(PLCStatus.CONNECTING)

            # Create async Modbus client
            self.client = AsyncModbusTcpClient(
                host=self.config.host,
                port=self.config.port,
                timeout=self.config.timeout
            )

            # Connect to device
            await self.client.connect()

            if self.client.connected:
                self._update_status(PLCStatus.CONNECTED)
                self.logger.info(
                    f"Connected to Modbus TCP at {self.config.host}:{self.config.port}, "
                    f"Unit ID: {self.unit_id}"
                )
                return True
            else:
                raise PLCConnectionError("Failed to establish Modbus TCP connection")

        except Exception as e:
            error_msg = f"Modbus TCP connection failed: {str(e)}"
            self._update_status(PLCStatus.ERROR, error_msg)
            self._increment_error_stats()
            raise PLCConnectionError(error_msg)

    async def disconnect(self) -> bool:
        """Disconnect from Modbus TCP device"""
        try:
            if self.client:
                self.client.close()
                self._update_status(PLCStatus.DISCONNECTED)
                self.logger.info("Disconnected from Modbus TCP device")
            return True
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            return False

    async def read_single(self, address: str, data_type: str) -> PLCDataPoint:
        """Read single value from Modbus device"""
        try:
            # Parse address
            addr_info = self._parse_address(address)
            register_address = addr_info['address']
            function_code = addr_info['function_code']

            # Read based on function code and data type
            if function_code == 'coil':
                result = await self.client.read_coils(
                    register_address, 1, slave=self.unit_id
                )
                if result.isError():
                    raise PLCDataError(f"Modbus read error: {result}")
                value = result.bits[0]

            elif function_code == 'discrete':
                result = await self.client.read_discrete_inputs(
                    register_address, 1, slave=self.unit_id
                )
                if result.isError():
                    raise PLCDataError(f"Modbus read error: {result}")
                value = result.bits[0]

            else:
                # Read holding or input registers
                count = self.MODBUS_DATA_TYPES.get(data_type.upper(), 1)

                if function_code == 'input':
                    result = await self.client.read_input_registers(
                        register_address, count, slave=self.unit_id
                    )
                else:  # holding
                    result = await self.client.read_holding_registers(
                        register_address, count, slave=self.unit_id
                    )

                if result.isError():
                    raise PLCDataError(f"Modbus read error: {result}")

                # Decode value based on data type
                decoder = BinaryPayloadDecoder.fromRegisters(
                    result.registers,
                    byteorder=self.byte_order,
                    wordorder=self.word_order
                )
                value = self._decode_value(decoder, data_type.upper())

            # Update statistics
            self._increment_read_stats(count if 'count' in locals() else 1)

            return PLCDataPoint(
                address=address,
                value=value,
                data_type=data_type,
                quality=192,  # Good quality
                timestamp=datetime.now()
            )

        except Exception as e:
            self._increment_error_stats()
            self.logger.error(f"Modbus read failed for {address}: {e}")
            raise PLCDataError(str(e))

    async def write_single(self, address: str, value: Any, data_type: str) -> bool:
        """Write single value to Modbus device"""
        try:
            # Parse address
            addr_info = self._parse_address(address)
            register_address = addr_info['address']
            function_code = addr_info['function_code']

            # Write based on function code and data type
            if function_code == 'coil':
                result = await self.client.write_coil(
                    register_address, bool(value), slave=self.unit_id
                )
            else:
                # Build payload for register write
                builder = BinaryPayloadBuilder(
                    byteorder=self.byte_order,
                    wordorder=self.word_order
                )

                # Add value to payload based on data type
                self._encode_value(builder, value, data_type.upper())

                # Get registers from payload
                registers = builder.to_registers()

                # Write to holding registers
                if len(registers) == 1:
                    result = await self.client.write_register(
                        register_address, registers[0], slave=self.unit_id
                    )
                else:
                    result = await self.client.write_registers(
                        register_address, registers, slave=self.unit_id
                    )

            if result.isError():
                raise PLCDataError(f"Modbus write error: {result}")

            # Update statistics
            self._increment_write_stats(len(registers) if 'registers' in locals() else 1)

            self.logger.debug(f"Modbus write successful: {address} = {value}")
            return True

        except Exception as e:
            self._increment_error_stats()
            self.logger.error(f"Modbus write failed for {address}: {e}")
            raise PLCDataError(str(e))

    async def read_batch(self, addresses: List[str], data_types: List[str]) -> List[PLCDataPoint]:
        """Read multiple values (optimized batch read where possible)"""
        results = []

        # Simple implementation: read each individually
        # TODO: Optimize by grouping consecutive addresses
        for addr, dtype in zip(addresses, data_types):
            try:
                result = await self.read_single(addr, dtype)
                results.append(result)
            except Exception as e:
                # Return error data point
                results.append(PLCDataPoint(
                    address=addr,
                    value=None,
                    data_type=dtype,
                    quality=0,  # Bad quality
                    timestamp=datetime.now(),
                    error=str(e)
                ))

        return results

    async def write_batch(self, addresses: List[str], values: List[Any],
                         data_types: List[str]) -> List[bool]:
        """Write multiple values"""
        results = []

        for addr, val, dtype in zip(addresses, values, data_types):
            try:
                success = await self.write_single(addr, val, dtype)
                results.append(success)
            except Exception as e:
                self.logger.error(f"Batch write failed for {addr}: {e}")
                results.append(False)

        return results

    async def subscribe(self, tags: List[PLCTagDefinition],
                       callback: Callable[[PLCDataPoint], None]) -> bool:
        """
        Subscribe to tag changes (polling-based for Modbus)
        Modbus doesn't support native subscriptions, so we poll
        """
        self.logger.warning("Modbus TCP doesn't support native subscriptions, using polling")

        # Store tags and callback
        for tag in tags:
            self.add_tag(tag)

        # Start polling loop
        asyncio.create_task(self._polling_loop(tags, callback))

        return True

    async def _polling_loop(self, tags: List[PLCTagDefinition],
                           callback: Callable[[PLCDataPoint], None]):
        """Polling loop for subscription emulation"""
        while self.is_connected():
            for tag in tags:
                try:
                    data_point = await self.read_single(tag.address, tag.data_type)
                    callback(data_point)
                except Exception as e:
                    self.logger.error(f"Polling error for {tag.name}: {e}")

            # Wait for scan rate interval
            await asyncio.sleep(self.config.scan_rate_ms / 1000.0)

    def validate_address(self, address: str) -> bool:
        """Validate Modbus address format"""
        try:
            self._parse_address(address)
            return True
        except Exception as e:
            self.logger.debug(f"Invalid address {address}: {e}")
            return False

    def _parse_address(self, address: str) -> Dict[str, Any]:
        """
        Parse Modbus address format

        Supports:
        - Standard Modbus: 40001 (holding), 30001 (input), 00001 (coil), 10001 (discrete)
        - Explicit format: HR:0, IR:100, C:0, DI:50
        - Direct addressing: 0, 100, 1000 (assumes holding registers)
        """
        if ':' in address:
            # Explicit format: HR:0, IR:100, C:0, DI:50
            area, addr = address.split(':')
            register_address = int(addr)

            area_upper = area.upper()
            if area_upper == 'HR':
                function_code = 'holding'
            elif area_upper == 'IR':
                function_code = 'input'
            elif area_upper == 'C':
                function_code = 'coil'
            elif area_upper == 'DI':
                function_code = 'discrete'
            else:
                raise ValueError(f"Unknown area code: {area}")

        else:
            # Standard Modbus addressing or direct addressing
            addr_int = int(address)

            if 1 <= addr_int <= 9999:  # Coils (00001-09999)
                register_address = addr_int - 1
                function_code = 'coil'
            elif 10001 <= addr_int <= 19999:  # Discrete inputs (10001-19999)
                register_address = addr_int - 10001
                function_code = 'discrete'
            elif 30001 <= addr_int <= 39999:  # Input registers (30001-39999)
                register_address = addr_int - 30001
                function_code = 'input'
            elif 40001 <= addr_int <= 49999:  # Holding registers (40001-49999)
                register_address = addr_int - 40001
                function_code = 'holding'
            else:
                # Direct 0-based addressing (assume holding registers)
                register_address = addr_int
                function_code = 'holding'

        return {
            'address': register_address,
            'function_code': function_code
        }

    def _decode_value(self, decoder: BinaryPayloadDecoder, data_type: str) -> Any:
        """Decode value from Modbus registers based on data type"""
        if data_type == 'BOOL':
            return bool(decoder.decode_16bit_uint())
        elif data_type == 'INT16':
            return decoder.decode_16bit_int()
        elif data_type == 'UINT16':
            return decoder.decode_16bit_uint()
        elif data_type == 'INT32':
            return decoder.decode_32bit_int()
        elif data_type == 'UINT32':
            return decoder.decode_32bit_uint()
        elif data_type == 'FLOAT32':
            return decoder.decode_32bit_float()
        elif data_type == 'INT64':
            return decoder.decode_64bit_int()
        elif data_type == 'UINT64':
            return decoder.decode_64bit_uint()
        elif data_type == 'FLOAT64':
            return decoder.decode_64bit_float()
        else:
            raise ValueError(f"Unsupported data type for decoding: {data_type}")

    def _encode_value(self, builder: BinaryPayloadBuilder, value: Any, data_type: str):
        """Encode value to Modbus registers based on data type"""
        if data_type == 'BOOL':
            builder.add_16bit_uint(1 if value else 0)
        elif data_type == 'INT16':
            builder.add_16bit_int(int(value))
        elif data_type == 'UINT16':
            builder.add_16bit_uint(int(value))
        elif data_type == 'INT32':
            builder.add_32bit_int(int(value))
        elif data_type == 'UINT32':
            builder.add_32bit_uint(int(value))
        elif data_type == 'FLOAT32':
            builder.add_32bit_float(float(value))
        elif data_type == 'INT64':
            builder.add_64bit_int(int(value))
        elif data_type == 'UINT64':
            builder.add_64bit_uint(int(value))
        elif data_type == 'FLOAT64':
            builder.add_64bit_float(float(value))
        else:
            raise ValueError(f"Unsupported data type for encoding: {data_type}")

    async def read_multiple(self, addresses: List[Tuple[str, str]]) -> List[PLCDataPoint]:
        """
        Read multiple values (required by BasePLCConnector)
        Wrapper for read_batch with different signature
        """
        addrs = [addr for addr, _ in addresses]
        types = [dtype for _, dtype in addresses]
        return await self.read_batch(addrs, types)

    async def write_multiple(self, writes: List[Tuple[str, Any, str]]) -> List[bool]:
        """
        Write multiple values (required by BasePLCConnector)
        Wrapper for write_batch with different signature
        """
        addrs = [addr for addr, _, _ in writes]
        values = [val for _, val, _ in writes]
        types = [dtype for _, _, dtype in writes]
        return await self.write_batch(addrs, values, types)

    async def discover_tags(self) -> List[PLCTagDefinition]:
        """
        Discover available tags (not supported by Modbus)
        Modbus doesn't provide tag discovery - tags must be configured manually
        """
        self.logger.warning("Tag discovery not supported for Modbus TCP - tags must be manually configured")
        return []
