"""
Base PLC Connector Abstract Class
Defines the interface for all PLC connector implementations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging
from enum import Enum


class PLCConnectionError(Exception):
    """Raised when PLC connection fails"""
    pass


class PLCDataError(Exception):
    """Raised when PLC data reading/writing fails"""
    pass


class PLCStatus(Enum):
    """PLC connection status enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class PLCDataPoint:
    """Represents a single data point from PLC"""
    address: str
    value: Any
    data_type: str
    quality: int = 192  # Good quality in Sparkplug
    timestamp: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class PLCConnectionConfig:
    """PLC connection configuration"""
    host: str
    port: int = 102
    rack: int = 0
    slot: int = 1
    timeout: float = 5.0
    
    # Authentication
    username: Optional[str] = None
    password: Optional[str] = None
    
    # TLS/Security
    use_tls: bool = False
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    
    # Connection pooling
    max_connections: int = 10
    connection_retry_interval: float = 5.0
    max_retries: int = 3
    
    # Data collection
    scan_rate_ms: int = 1000
    batch_size: int = 100
    enable_subscriptions: bool = True


@dataclass
class PLCTagDefinition:
    """Definition of a PLC tag/variable"""
    name: str
    address: str
    data_type: str
    description: Optional[str] = None
    units: Optional[str] = None
    scaling_factor: float = 1.0
    scaling_offset: float = 0.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sparkplug_alias: Optional[int] = None
    oee_metric_type: Optional[str] = None


class BasePLCConnector(ABC):
    """
    Abstract base class for all PLC connectors
    Provides common interface and functionality for PLC communication
    """
    
    def __init__(self, config: PLCConnectionConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.status = PLCStatus.DISCONNECTED
        self.connection = None
        self.last_error: Optional[str] = None
        self.tags: Dict[str, PLCTagDefinition] = {}
        self.connection_start_time: Optional[datetime] = None
        
        # Statistics
        self.read_count = 0
        self.write_count = 0
        self.error_count = 0
        self.total_bytes_read = 0
        self.total_bytes_written = 0
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to PLC
        Returns True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from PLC
        Returns True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def read_single(self, address: str, data_type: str) -> PLCDataPoint:
        """
        Read a single data point from PLC
        
        Args:
            address: PLC address/tag name
            data_type: Expected data type
            
        Returns:
            PLCDataPoint with value and metadata
        """
        pass
    
    @abstractmethod
    async def read_multiple(self, addresses: List[Tuple[str, str]]) -> List[PLCDataPoint]:
        """
        Read multiple data points from PLC in batch
        
        Args:
            addresses: List of (address, data_type) tuples
            
        Returns:
            List of PLCDataPoint objects
        """
        pass
    
    @abstractmethod
    async def write_single(self, address: str, value: Any, data_type: str) -> bool:
        """
        Write a single value to PLC
        
        Args:
            address: PLC address/tag name
            value: Value to write
            data_type: Data type
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def write_multiple(self, writes: List[Tuple[str, Any, str]]) -> List[bool]:
        """
        Write multiple values to PLC in batch
        
        Args:
            writes: List of (address, value, data_type) tuples
            
        Returns:
            List of success flags
        """
        pass
    
    @abstractmethod
    async def discover_tags(self) -> List[PLCTagDefinition]:
        """
        Auto-discover available tags/variables in PLC
        
        Returns:
            List of discovered tag definitions
        """
        pass
    
    @abstractmethod
    def validate_address(self, address: str) -> bool:
        """
        Validate if address format is correct for this PLC type
        
        Args:
            address: Address to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    # Common utility methods
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on PLC connection
        
        Returns:
            Dictionary with health status information
        """
        health_info = {
            'status': self.status.value,
            'connected': self.is_connected(),
            'last_error': self.last_error,
            'uptime_seconds': self.get_uptime_seconds(),
            'statistics': {
                'read_count': self.read_count,
                'write_count': self.write_count,
                'error_count': self.error_count,
                'total_bytes_read': self.total_bytes_read,
                'total_bytes_written': self.total_bytes_written,
                'error_rate': self.get_error_rate(),
            }
        }
        
        # Try a simple read operation if connected
        if self.is_connected() and self.tags:
            try:
                # Read the first available tag as health check
                first_tag = next(iter(self.tags.values()))
                await self.read_single(first_tag.address, first_tag.data_type)
                health_info['last_read_success'] = True
            except Exception as e:
                health_info['last_read_success'] = False
                health_info['last_read_error'] = str(e)
        
        return health_info
    
    def is_connected(self) -> bool:
        """Check if PLC is currently connected"""
        return self.status == PLCStatus.CONNECTED
    
    def get_uptime_seconds(self) -> Optional[float]:
        """Get connection uptime in seconds"""
        if self.connection_start_time and self.is_connected():
            return (datetime.now() - self.connection_start_time).total_seconds()
        return None
    
    def get_error_rate(self) -> float:
        """Calculate error rate as percentage"""
        total_operations = self.read_count + self.write_count
        if total_operations == 0:
            return 0.0
        return (self.error_count / total_operations) * 100.0
    
    def add_tag(self, tag_def: PLCTagDefinition):
        """Add a tag definition"""
        self.tags[tag_def.name] = tag_def
        self.logger.debug(f"Added tag: {tag_def.name} -> {tag_def.address}")
    
    def remove_tag(self, tag_name: str):
        """Remove a tag definition"""
        if tag_name in self.tags:
            del self.tags[tag_name]
            self.logger.debug(f"Removed tag: {tag_name}")
    
    def get_tag(self, tag_name: str) -> Optional[PLCTagDefinition]:
        """Get tag definition by name"""
        return self.tags.get(tag_name)
    
    async def read_tag(self, tag_name: str) -> PLCDataPoint:
        """
        Read a tag by name (using tag definition)
        
        Args:
            tag_name: Name of the tag to read
            
        Returns:
            PLCDataPoint with value and metadata
        """
        tag_def = self.get_tag(tag_name)
        if not tag_def:
            raise PLCDataError(f"Tag not found: {tag_name}")
        
        data_point = await self.read_single(tag_def.address, tag_def.data_type)
        
        # Apply scaling if configured
        if isinstance(data_point.value, (int, float)) and data_point.value is not None:
            if tag_def.scaling_factor != 1.0 or tag_def.scaling_offset != 0.0:
                scaled_value = (data_point.value * tag_def.scaling_factor) + tag_def.scaling_offset
                data_point.value = scaled_value
        
        return data_point
    
    async def write_tag(self, tag_name: str, value: Any) -> bool:
        """
        Write a value to a tag by name
        
        Args:
            tag_name: Name of the tag to write
            value: Value to write
            
        Returns:
            True if successful, False otherwise
        """
        tag_def = self.get_tag(tag_name)
        if not tag_def:
            raise PLCDataError(f"Tag not found: {tag_name}")
        
        # Apply reverse scaling if configured
        write_value = value
        if isinstance(value, (int, float)) and value is not None:
            if tag_def.scaling_factor != 1.0 or tag_def.scaling_offset != 0.0:
                write_value = (value - tag_def.scaling_offset) / tag_def.scaling_factor
        
        return await self.write_single(tag_def.address, write_value, tag_def.data_type)
    
    async def read_all_tags(self) -> List[PLCDataPoint]:
        """
        Read all configured tags
        
        Returns:
            List of PLCDataPoint objects for all tags
        """
        if not self.tags:
            return []
        
        addresses = [(tag.address, tag.data_type) for tag in self.tags.values()]
        data_points = await self.read_multiple(addresses)
        
        # Apply scaling and tag names
        result = []
        for i, (tag_name, tag_def) in enumerate(self.tags.items()):
            if i < len(data_points):
                data_point = data_points[i]
                data_point.address = tag_name  # Use tag name instead of raw address
                
                # Apply scaling
                if isinstance(data_point.value, (int, float)) and data_point.value is not None:
                    if tag_def.scaling_factor != 1.0 or tag_def.scaling_offset != 0.0:
                        scaled_value = (data_point.value * tag_def.scaling_factor) + tag_def.scaling_offset
                        data_point.value = scaled_value
                
                result.append(data_point)
        
        return result
    
    def _increment_read_stats(self, byte_count: int = 0):
        """Increment read statistics"""
        self.read_count += 1
        self.total_bytes_read += byte_count
    
    def _increment_write_stats(self, byte_count: int = 0):
        """Increment write statistics"""
        self.write_count += 1
        self.total_bytes_written += byte_count
    
    def _increment_error_stats(self):
        """Increment error statistics"""
        self.error_count += 1
    
    def _update_status(self, status: PLCStatus, error: Optional[str] = None):
        """Update connection status"""
        old_status = self.status
        self.status = status
        self.last_error = error
        
        if status == PLCStatus.CONNECTED and old_status != PLCStatus.CONNECTED:
            self.connection_start_time = datetime.now()
            self.logger.info(f"PLC connected: {self.config.host}")
        elif status != PLCStatus.CONNECTED and old_status == PLCStatus.CONNECTED:
            self.connection_start_time = None
            self.logger.warning(f"PLC disconnected: {self.config.host}")
        
        if error:
            self.logger.error(f"PLC error: {error}")


class PLCConnectorFactory:
    """Factory for creating PLC connector instances"""
    
    _connector_types = {}
    
    @classmethod
    def register_connector(cls, plc_type: str, connector_class):
        """Register a connector class for a PLC type"""
        cls._connector_types[plc_type.upper()] = connector_class
    
    @classmethod
    def create_connector(cls, plc_type: str, config: PLCConnectionConfig, 
                        logger: Optional[logging.Logger] = None) -> BasePLCConnector:
        """
        Create a connector instance for the specified PLC type
        
        Args:
            plc_type: Type of PLC (e.g., 'SIEMENS_S7', 'ALLEN_BRADLEY')
            config: Connection configuration
            logger: Optional logger instance
            
        Returns:
            PLC connector instance
        """
        plc_type_upper = plc_type.upper()
        if plc_type_upper not in cls._connector_types:
            raise ValueError(f"Unknown PLC type: {plc_type}")
        
        connector_class = cls._connector_types[plc_type_upper]
        return connector_class(config, logger)