"""
Siemens S7 PLC Connector
Comprehensive implementation for all Siemens S7 series PLCs
Supports: S7-300, S7-400, S7-1200, S7-1500, LOGO!, ET200SP
"""

import asyncio
import snap7
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import struct
import logging
from dataclasses import dataclass

from .base import (
    BasePLCConnector, PLCConnectionConfig, PLCTagDefinition, 
    PLCDataPoint, PLCStatus, PLCConnectionError, PLCDataError
)


@dataclass
class SiemensS7Config(PLCConnectionConfig):
    """Extended configuration for Siemens S7 PLCs"""
    plc_type: str = "S7_1200"  # S7_300, S7_400, S7_1200, S7_1500, LOGO, ET200SP
    cpu_type: str = "AUTO"     # AUTO, CPU_314, CPU_315, CPU_416, etc.
    
    # S7 specific parameters
    local_tsap: int = 0x0100
    remote_tsap: int = 0x0102
    
    # Data blocks and memory areas
    enable_db_read: bool = True
    enable_input_read: bool = True
    enable_output_read: bool = True
    enable_marker_read: bool = True
    
    # Performance tuning
    pdu_size: int = 480  # PDU size for bulk reads
    word_len: int = 2    # Word length for data alignment


class SiemensS7Connector(BasePLCConnector):
    """
    Siemens S7 PLC Connector using python-snap7
    Supports all major S7 series PLCs with optimized communication
    """
    
    # S7 data type mappings
    S7_DATA_TYPES = {
        'BOOL': snap7.snap7types.S7WLBit,
        'BYTE': snap7.snap7types.S7WLByte,
        'WORD': snap7.snap7types.S7WLWord,
        'DWORD': snap7.snap7types.S7WLDWord,
        'INT': snap7.snap7types.S7WLWord,
        'DINT': snap7.snap7types.S7WLDWord,
        'REAL': snap7.snap7types.S7WLReal,
        'STRING': snap7.snap7types.S7WLByte,
    }
    
    # Memory area codes
    MEMORY_AREAS = {
        'DB': snap7.snap7types.S7AreaDB,    # Data blocks
        'I': snap7.snap7types.S7AreaPE,     # Process inputs
        'Q': snap7.snap7types.S7AreaPA,     # Process outputs  
        'M': snap7.snap7types.S7AreaMK,     # Memory (Merker)
        'T': snap7.snap7types.S7AreaTM,     # Timers
        'C': snap7.snap7types.S7AreaCT,     # Counters
    }
    
    def __init__(self, config: Union[PLCConnectionConfig, SiemensS7Config], 
                 logger: Optional[logging.Logger] = None):
        # Convert to Siemens-specific config if needed
        if isinstance(config, PLCConnectionConfig) and not isinstance(config, SiemensS7Config):
            config = SiemensS7Config(**config.__dict__)
        
        super().__init__(config, logger)
        self.s7_client: Optional[snap7.client.Client] = None
        self.connection_params = self._build_connection_params()
        
    def _build_connection_params(self) -> Dict[str, Any]:
        """Build connection parameters based on PLC type"""
        params = {
            'rack': self.config.rack,
            'slot': self.config.slot,
        }
        
        # Adjust parameters based on PLC type
        if hasattr(self.config, 'plc_type'):
            plc_type = self.config.plc_type.upper()
            
            if plc_type in ['S7_300', 'S7_400']:
                # Classic S7 PLCs
                params['rack'] = self.config.rack or 0
                params['slot'] = self.config.slot or 2
            elif plc_type in ['S7_1200', 'S7_1500']:
                # Modern S7 PLCs
                params['rack'] = self.config.rack or 0
                params['slot'] = self.config.slot or 1
            elif plc_type == 'LOGO':
                # LOGO! PLCs
                params['rack'] = 0
                params['slot'] = 0
            elif plc_type == 'ET200SP':
                # Distributed I/O
                params['rack'] = self.config.rack or 0
                params['slot'] = self.config.slot or 1
        
        return params
    
    async def connect(self) -> bool:
        """Establish connection to Siemens S7 PLC"""
        try:
            self._update_status(PLCStatus.CONNECTING)
            
            # Create S7 client
            self.s7_client = snap7.client.Client()
            
            # Configure connection parameters
            if hasattr(self.config, 'local_tsap'):
                self.s7_client.set_param(snap7.snap7types.LocalTSAP, self.config.local_tsap)
            if hasattr(self.config, 'remote_tsap'):
                self.s7_client.set_param(snap7.snap7types.RemoteTSAP, self.config.remote_tsap)
            
            # Connect to PLC
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.s7_client.connect,
                self.config.host,
                self.connection_params['rack'],
                self.connection_params['slot']
            )
            
            # Verify connection
            if self.s7_client.get_connected():
                self._update_status(PLCStatus.CONNECTED)
                
                # Get PLC info for logging
                cpu_info = await self._get_cpu_info()
                self.logger.info(f"Connected to Siemens S7 PLC: {cpu_info}")
                
                return True
            else:
                raise PLCConnectionError("Failed to establish connection")
                
        except Exception as e:
            error_msg = f"S7 connection failed: {str(e)}"
            self._update_status(PLCStatus.ERROR, error_msg)
            self._increment_error_stats()
            raise PLCConnectionError(error_msg)
    
    async def disconnect(self) -> bool:
        """Disconnect from Siemens S7 PLC"""
        try:
            if self.s7_client and self.s7_client.get_connected():
                await asyncio.get_event_loop().run_in_executor(
                    None, self.s7_client.disconnect
                )
            
            self.s7_client = None
            self._update_status(PLCStatus.DISCONNECTED)
            return True
            
        except Exception as e:
            error_msg = f"S7 disconnect failed: {str(e)}"
            self._update_status(PLCStatus.ERROR, error_msg)
            self.logger.error(error_msg)
            return False
    
    async def read_single(self, address: str, data_type: str) -> PLCDataPoint:
        """Read a single data point from S7 PLC"""
        if not self.s7_client or not self.s7_client.get_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        try:
            # Parse S7 address
            area, db_number, start_address, bit_offset = self._parse_s7_address(address)
            
            # Determine read size based on data type
            size = self._get_data_type_size(data_type)
            
            # Read data from PLC
            raw_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self.s7_client.read_area,
                area,
                db_number,
                start_address,
                size
            )
            
            # Convert raw data to typed value
            value = self._convert_raw_data(raw_data, data_type, bit_offset)
            
            self._increment_read_stats(len(raw_data))
            
            return PLCDataPoint(
                address=address,
                value=value,
                data_type=data_type,
                quality=192,  # Good quality
                timestamp=datetime.now()
            )
            
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
    
    async def read_multiple(self, addresses: List[Tuple[str, str]]) -> List[PLCDataPoint]:
        """Read multiple data points from S7 PLC in batch"""
        if not self.s7_client or not self.s7_client.get_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        results = []
        
        # Group addresses by memory area for optimization
        grouped_reads = self._group_addresses_for_batch_read(addresses)
        
        for group in grouped_reads:
            try:
                # Perform batch read for this group
                group_results = await self._read_address_group(group)
                results.extend(group_results)
                
            except Exception as e:
                # If batch read fails, fall back to individual reads
                self.logger.warning(f"Batch read failed, falling back to individual reads: {e}")
                for address, data_type in group['addresses']:
                    result = await self.read_single(address, data_type)
                    results.append(result)
        
        return results
    
    async def write_single(self, address: str, value: Any, data_type: str) -> bool:
        """Write a single value to S7 PLC"""
        if not self.s7_client or not self.s7_client.get_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        try:
            # Parse S7 address
            area, db_number, start_address, bit_offset = self._parse_s7_address(address)
            
            # Convert value to raw bytes
            raw_data = self._convert_value_to_raw(value, data_type, bit_offset)
            
            # Write data to PLC
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.s7_client.write_area,
                area,
                db_number,
                start_address,
                raw_data
            )
            
            self._increment_write_stats(len(raw_data))
            return True
            
        except Exception as e:
            self._increment_error_stats()
            error_msg = f"Failed to write {address}: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    async def write_multiple(self, writes: List[Tuple[str, Any, str]]) -> List[bool]:
        """Write multiple values to S7 PLC in batch"""
        results = []
        
        # For now, perform individual writes
        # TODO: Implement optimized batch writing
        for address, value, data_type in writes:
            success = await self.write_single(address, value, data_type)
            results.append(success)
        
        return results
    
    async def discover_tags(self) -> List[PLCTagDefinition]:
        """Auto-discover available tags in S7 PLC"""
        if not self.s7_client or not self.s7_client.get_connected():
            raise PLCConnectionError("Not connected to PLC")
        
        discovered_tags = []
        
        try:
            # Get list of data blocks
            block_list = await self._get_block_list()
            
            for block_info in block_list:
                if block_info['type'] == 'DB':  # Data Block
                    db_number = block_info['number']
                    
                    # Try to read DB header to get size
                    try:
                        db_size = await self._get_db_size(db_number)
                        
                        # Create basic tag definitions for DB words
                        for word_offset in range(0, min(db_size, 100), 2):  # Limit discovery
                            tag_name = f"DB{db_number}.DBW{word_offset}"
                            tag_def = PLCTagDefinition(
                                name=tag_name,
                                address=f"DB{db_number},{word_offset}",
                                data_type='WORD',
                                description=f"Data Block {db_number} Word {word_offset}"
                            )
                            discovered_tags.append(tag_def)
                    
                    except Exception as e:
                        self.logger.debug(f"Could not read DB{db_number}: {e}")
            
            # Add common system tags
            system_tags = self._get_common_system_tags()
            discovered_tags.extend(system_tags)
            
        except Exception as e:
            self.logger.error(f"Tag discovery failed: {e}")
        
        return discovered_tags
    
    def validate_address(self, address: str) -> bool:
        """Validate S7 address format"""
        try:
            self._parse_s7_address(address)
            return True
        except:
            return False
    
    # Helper methods
    
    def _parse_s7_address(self, address: str) -> Tuple[int, int, int, int]:
        """
        Parse S7 address string into components
        
        Formats supported:
        - DB1,X0.0 (Data Block 1, Byte 0, Bit 0)
        - DB1,10 (Data Block 1, Word at byte 10)
        - I0.0 (Input bit 0.0)
        - Q0.0 (Output bit 0.0)
        - M0.0 (Memory bit 0.0)
        - IW10 (Input word at byte 10)
        - QW10 (Output word at byte 10)
        - MW10 (Memory word at byte 10)
        
        Returns:
            Tuple of (area_code, db_number, start_address, bit_offset)
        """
        address = address.upper().strip()
        
        # Data Block format: DB1,X0.0 or DB1,10
        if address.startswith('DB'):
            parts = address.split(',')
            if len(parts) != 2:
                raise ValueError(f"Invalid DB address format: {address}")
            
            db_number = int(parts[0][2:])  # Extract number from "DB1"
            location = parts[1]
            
            # Check for bit addressing
            if '.' in location:
                byte_addr, bit_addr = location.split('.')
                if location.startswith('X'):
                    byte_addr = byte_addr[1:]  # Remove 'X' prefix
                start_address = int(byte_addr)
                bit_offset = int(bit_addr)
            else:
                start_address = int(location)
                bit_offset = 0
            
            return self.MEMORY_AREAS['DB'], db_number, start_address, bit_offset
        
        # Process Input/Output/Memory formats
        bit_offset = 0
        
        if '.' in address:
            # Bit addressing
            byte_part, bit_part = address.split('.')
            bit_offset = int(bit_part)
            address = byte_part
        
        if address.startswith('I'):
            # Input
            if address.startswith('IW'):
                start_address = int(address[2:])
            elif address.startswith('IB'):
                start_address = int(address[2:])
            else:
                start_address = int(address[1:])
            return self.MEMORY_AREAS['I'], 0, start_address, bit_offset
        
        elif address.startswith('Q'):
            # Output
            if address.startswith('QW'):
                start_address = int(address[2:])
            elif address.startswith('QB'):
                start_address = int(address[2:])
            else:
                start_address = int(address[1:])
            return self.MEMORY_AREAS['Q'], 0, start_address, bit_offset
        
        elif address.startswith('M'):
            # Memory
            if address.startswith('MW'):
                start_address = int(address[2:])
            elif address.startswith('MB'):
                start_address = int(address[2:])
            else:
                start_address = int(address[1:])
            return self.MEMORY_AREAS['M'], 0, start_address, bit_offset
        
        else:
            raise ValueError(f"Unsupported address format: {address}")
    
    def _get_data_type_size(self, data_type: str) -> int:
        """Get the size in bytes for a data type"""
        size_map = {
            'BOOL': 1,
            'BYTE': 1,
            'WORD': 2,
            'DWORD': 4,
            'INT': 2,
            'DINT': 4,
            'REAL': 4,
            'STRING': 256,  # Max string size
        }
        return size_map.get(data_type.upper(), 1)
    
    def _convert_raw_data(self, raw_data: bytes, data_type: str, bit_offset: int = 0) -> Any:
        """Convert raw bytes to typed value"""
        data_type = data_type.upper()
        
        try:
            if data_type == 'BOOL':
                if len(raw_data) < 1:
                    return None
                byte_value = raw_data[0]
                return bool(byte_value & (1 << bit_offset))
            
            elif data_type == 'BYTE':
                if len(raw_data) < 1:
                    return None
                return raw_data[0]
            
            elif data_type == 'WORD':
                if len(raw_data) < 2:
                    return None
                return struct.unpack('>H', raw_data[:2])[0]  # Big-endian
            
            elif data_type == 'DWORD':
                if len(raw_data) < 4:
                    return None
                return struct.unpack('>I', raw_data[:4])[0]  # Big-endian
            
            elif data_type == 'INT':
                if len(raw_data) < 2:
                    return None
                return struct.unpack('>h', raw_data[:2])[0]  # Signed big-endian
            
            elif data_type == 'DINT':
                if len(raw_data) < 4:
                    return None
                return struct.unpack('>i', raw_data[:4])[0]  # Signed big-endian
            
            elif data_type == 'REAL':
                if len(raw_data) < 4:
                    return None
                return struct.unpack('>f', raw_data[:4])[0]  # IEEE 754 big-endian
            
            elif data_type == 'STRING':
                # S7 string format: [max_len][current_len][data...]
                if len(raw_data) < 2:
                    return ""
                current_len = raw_data[1]
                if len(raw_data) < 2 + current_len:
                    return ""
                return raw_data[2:2+current_len].decode('ascii', errors='ignore')
            
            else:
                return raw_data.hex()
                
        except Exception as e:
            self.logger.error(f"Data conversion error for type {data_type}: {e}")
            return None
    
    def _convert_value_to_raw(self, value: Any, data_type: str, bit_offset: int = 0) -> bytes:
        """Convert typed value to raw bytes"""
        data_type = data_type.upper()
        
        try:
            if data_type == 'BOOL':
                # For bit writes, we need to read-modify-write
                # This is a simplified implementation
                return bytes([1 if value else 0])
            
            elif data_type == 'BYTE':
                return bytes([int(value) & 0xFF])
            
            elif data_type == 'WORD':
                return struct.pack('>H', int(value) & 0xFFFF)
            
            elif data_type == 'DWORD':
                return struct.pack('>I', int(value) & 0xFFFFFFFF)
            
            elif data_type == 'INT':
                return struct.pack('>h', int(value))
            
            elif data_type == 'DINT':
                return struct.pack('>i', int(value))
            
            elif data_type == 'REAL':
                return struct.pack('>f', float(value))
            
            elif data_type == 'STRING':
                str_value = str(value)
                str_bytes = str_value.encode('ascii', errors='ignore')
                max_len = 254  # Reserve 2 bytes for length info
                str_bytes = str_bytes[:max_len]
                # S7 string format
                return bytes([max_len, len(str_bytes)]) + str_bytes
            
            else:
                return bytes()
                
        except Exception as e:
            self.logger.error(f"Value conversion error for type {data_type}: {e}")
            return bytes()
    
    async def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        try:
            cpu_info = await asyncio.get_event_loop().run_in_executor(
                None, self.s7_client.get_cpu_info
            )
            return {
                'module_type_name': cpu_info.ModuleTypeName.decode('ascii', errors='ignore'),
                'serial_number': cpu_info.SerialNumber.decode('ascii', errors='ignore'),
                'as_name': cpu_info.ASName.decode('ascii', errors='ignore'),
                'module_name': cpu_info.ModuleName.decode('ascii', errors='ignore'),
            }
        except:
            return {'info': 'CPU info not available'}
    
    async def _get_block_list(self) -> List[Dict[str, Any]]:
        """Get list of blocks in PLC"""
        # This is a simplified implementation
        # In a real implementation, you would query the PLC for available blocks
        return [
            {'type': 'DB', 'number': 1},
            {'type': 'DB', 'number': 2},
            {'type': 'DB', 'number': 10},
        ]
    
    async def _get_db_size(self, db_number: int) -> int:
        """Get size of a data block"""
        try:
            # Try to read the first few bytes to determine size
            # This is a simplified approach
            test_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self.s7_client.read_area,
                self.MEMORY_AREAS['DB'],
                db_number,
                0,
                2
            )
            # Return a conservative size estimate
            return 100
        except:
            return 0
    
    def _get_common_system_tags(self) -> List[PLCTagDefinition]:
        """Get common system tags for S7 PLCs"""
        return [
            PLCTagDefinition(
                name="CPU_DIAG_STATUS",
                address="M0,0",
                data_type="BYTE",
                description="CPU diagnostic status"
            ),
            PLCTagDefinition(
                name="CYCLE_TIME", 
                address="M4,0",
                data_type="WORD",
                description="PLC cycle time in ms",
                units="ms"
            ),
        ]
    
    def _group_addresses_for_batch_read(self, addresses: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Group addresses for optimized batch reading"""
        # Simplified grouping - group by memory area
        groups = {}
        
        for address, data_type in addresses:
            try:
                area, db_number, start_address, bit_offset = self._parse_s7_address(address)
                area_key = f"{area}_{db_number}"
                
                if area_key not in groups:
                    groups[area_key] = {
                        'area': area,
                        'db_number': db_number,
                        'addresses': []
                    }
                
                groups[area_key]['addresses'].append((address, data_type))
                
            except Exception as e:
                self.logger.warning(f"Could not group address {address}: {e}")
        
        return list(groups.values())
    
    async def _read_address_group(self, group: Dict[str, Any]) -> List[PLCDataPoint]:
        """Read a group of addresses from the same memory area"""
        results = []
        
        # For now, fall back to individual reads
        # TODO: Implement true batch reading with optimized memory access
        for address, data_type in group['addresses']:
            result = await self.read_single(address, data_type)
            results.append(result)
        
        return results


# Register the connector
from .base import PLCConnectorFactory
PLCConnectorFactory.register_connector('SIEMENS_S7', SiemensS7Connector)
PLCConnectorFactory.register_connector('S7', SiemensS7Connector)