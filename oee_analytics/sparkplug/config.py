"""
Sparkplug B Configuration Management
Production-grade configuration handling with validation and hot-reload
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import yaml
from pydantic import BaseModel, Field, validator
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class PLCConnectionConfig(BaseModel):
    """PLC connection configuration"""
    id: str = Field(..., description="Unique PLC identifier")
    type: str = Field(..., description="PLC type (SIEMENS_S7, ALLEN_BRADLEY, etc.)")
    host: str = Field(..., description="PLC IP address or hostname")
    port: int = Field(default=102, description="PLC port")
    rack: int = Field(default=0, description="PLC rack number")
    slot: int = Field(default=1, description="PLC slot number")
    timeout: float = Field(default=5.0, description="Connection timeout in seconds")
    enabled: bool = Field(default=True, description="Enable this PLC connection")
    
    # Authentication
    username: Optional[str] = Field(default=None, description="PLC username")
    password: Optional[str] = Field(default=None, description="PLC password")
    
    # PLC-specific settings
    plc_type: Optional[str] = Field(default=None, description="Specific PLC model")
    cpu_type: Optional[str] = Field(default="AUTO", description="CPU type")
    
    # Tags configuration
    tags: List[Dict[str, Any]] = Field(default_factory=list, description="Tag definitions")
    
    @validator('type')
    def validate_plc_type(cls, v):
        valid_types = ['SIEMENS_S7', 'ALLEN_BRADLEY', 'CONTROLLOGIX', 'COMPACTLOGIX', 'MICROLOGIX']
        if v.upper() not in valid_types:
            raise ValueError(f"Invalid PLC type. Must be one of: {valid_types}")
        return v.upper()


class TagConfig(BaseModel):
    """Tag configuration for PLC"""
    name: str = Field(..., description="Tag name")
    address: str = Field(..., description="PLC address")
    data_type: str = Field(..., description="Data type")
    description: Optional[str] = Field(default=None, description="Tag description")
    units: Optional[str] = Field(default=None, description="Engineering units")
    scaling_factor: float = Field(default=1.0, description="Scaling factor")
    scaling_offset: float = Field(default=0.0, description="Scaling offset")
    min_value: Optional[float] = Field(default=None, description="Minimum value")
    max_value: Optional[float] = Field(default=None, description="Maximum value")
    sparkplug_alias: Optional[int] = Field(default=None, description="Sparkplug alias number")
    oee_metric_type: Optional[str] = Field(default=None, description="OEE metric type mapping")


class MetricMappingConfig(BaseModel):
    """Metric mapping configuration"""
    machine_id: str = Field(..., description="Target machine ID")
    sparkplug_metric_name: str = Field(..., description="Sparkplug metric name")
    oee_metric_type: str = Field(..., description="OEE metric type")
    data_transformation: Optional[str] = Field(default=None, description="Data transformation expression")
    threshold_value: Optional[float] = Field(default=None, description="Threshold value for triggers")
    scaling_factor: float = Field(default=1.0, description="Scaling factor")
    scaling_offset: float = Field(default=0.0, description="Scaling offset")
    quality_threshold: int = Field(default=192, description="Minimum Sparkplug quality")


class MQTTConfig(BaseModel):
    """MQTT broker configuration"""
    broker_host: str = Field(..., description="MQTT broker hostname")
    broker_port: int = Field(default=1883, description="MQTT broker port")
    username: Optional[str] = Field(default=None, description="MQTT username")
    password: Optional[str] = Field(default=None, description="MQTT password")
    client_id: str = Field(default="sparkplug_oee_client", description="MQTT client ID")
    
    # TLS configuration
    use_tls: bool = Field(default=False, description="Use TLS encryption")
    ca_cert_path: Optional[str] = Field(default=None, description="CA certificate path")
    cert_path: Optional[str] = Field(default=None, description="Client certificate path")
    key_path: Optional[str] = Field(default=None, description="Client key path")
    insecure: bool = Field(default=False, description="Skip certificate verification")
    
    # Connection settings
    keep_alive: int = Field(default=60, description="Keep alive interval")
    qos: int = Field(default=1, ge=0, le=2, description="Quality of Service level")
    retain: bool = Field(default=False, description="Retain messages")
    clean_session: bool = Field(default=True, description="Clean session on connect")
    
    # Reliability settings
    reconnect_delay_min: float = Field(default=1.0, description="Minimum reconnect delay")
    reconnect_delay_max: float = Field(default=60.0, description="Maximum reconnect delay")
    connection_timeout: int = Field(default=30, description="Connection timeout")


class SparkplugConfig(BaseModel):
    """Sparkplug B protocol configuration"""
    group_id: str = Field(default="OEE_Group", description="Sparkplug group ID")
    node_id: str = Field(default="OEE_Node", description="Sparkplug node ID")
    subscribe_group_ids: List[str] = Field(default_factory=lambda: ["OEE_Group"], description="Groups to subscribe to")
    
    # Message handling
    max_queue_size: int = Field(default=10000, description="Maximum message queue size")
    batch_size: int = Field(default=100, description="Batch size for processing")
    batch_timeout: float = Field(default=1.0, description="Batch timeout in seconds")
    
    # Birth/Death settings
    birth_timeout: int = Field(default=300, description="Birth timeout in seconds")
    death_timeout: int = Field(default=60, description="Death timeout in seconds")
    
    # Command settings
    enable_commands: bool = Field(default=False, description="Enable command handling")
    command_timeout: int = Field(default=30, description="Command timeout in seconds")
    command_rate_limit: int = Field(default=10, description="Commands per minute limit")


class ProcessingConfig(BaseModel):
    """Data processing configuration"""
    enabled: bool = Field(default=True, description="Enable data processing")
    batch_size: int = Field(default=100, description="Processing batch size")
    processing_interval: float = Field(default=1.0, description="Processing interval in seconds")
    
    # Store and forward
    store_raw_messages: bool = Field(default=True, description="Store raw MQTT messages")
    enable_store_forward: bool = Field(default=True, description="Enable store and forward")
    max_stored_messages: int = Field(default=100000, description="Maximum stored messages")
    
    # Data retention
    data_retention_days: int = Field(default=90, description="Data retention period")
    cleanup_interval_hours: int = Field(default=24, description="Cleanup interval")
    
    # Quality settings
    quality_score_threshold: int = Field(default=50, description="Minimum quality score")
    duplicate_detection: bool = Field(default=True, description="Enable duplicate detection")


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration"""
    enabled: bool = Field(default=True, description="Enable monitoring")
    metrics_port: int = Field(default=8001, description="Prometheus metrics port")
    health_check_port: int = Field(default=8002, description="Health check port")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="structured", description="Log format (structured/text)")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # Alerting thresholds
    connection_timeout_threshold: int = Field(default=300, description="Connection timeout alert threshold")
    message_lag_threshold: int = Field(default=60, description="Message lag alert threshold")
    error_rate_threshold: float = Field(default=5.0, description="Error rate alert threshold")
    
    # Performance monitoring
    enable_profiling: bool = Field(default=False, description="Enable performance profiling")
    slow_query_threshold: float = Field(default=1.0, description="Slow query threshold")


class SparkplugAgentConfig(BaseModel):
    """Complete Sparkplug Agent configuration"""
    version: str = Field(default="1.0", description="Configuration version")
    
    # Component configurations
    mqtt: MQTTConfig
    sparkplug: SparkplugConfig = Field(default_factory=SparkplugConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # PLC connections
    plc_connections: List[PLCConnectionConfig] = Field(default_factory=list, description="PLC connections")
    
    # Metric mappings
    metric_mappings: List[MetricMappingConfig] = Field(default_factory=list, description="Metric mappings")
    
    # Environment-specific settings
    environment: str = Field(default="production", description="Environment (development/staging/production)")
    debug: bool = Field(default=False, description="Debug mode")
    
    class Config:
        extra = "forbid"  # Prevent extra fields


class ConfigurationManager:
    """
    Configuration manager with validation, hot-reload, and environment support
    """
    
    def __init__(self, config_path: Optional[str] = None, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.config_path = config_path
        self.config: Optional[SparkplugAgentConfig] = None
        self.callbacks: List[Callable] = []
        self.observer: Optional[Observer] = None
        
        # Load configuration
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> SparkplugAgentConfig:
        """Load configuration from file"""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
            # Load based on file extension
            with open(config_file, 'r') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    config_data = yaml.safe_load(f)
                elif config_file.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    raise ValueError(f"Unsupported configuration file format: {config_file.suffix}")
            
            # Apply environment overrides
            config_data = self._apply_environment_overrides(config_data)
            
            # Validate and create config object
            self.config = SparkplugAgentConfig(**config_data)
            self.config_path = config_path
            
            self.logger.info(f"Configuration loaded from {config_path}")
            return self.config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _apply_environment_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides"""
        # MQTT overrides
        if os.getenv('MQTT_BROKER_HOST'):
            config_data.setdefault('mqtt', {})['broker_host'] = os.getenv('MQTT_BROKER_HOST')
        if os.getenv('MQTT_BROKER_PORT'):
            config_data.setdefault('mqtt', {})['broker_port'] = int(os.getenv('MQTT_BROKER_PORT'))
        if os.getenv('MQTT_USERNAME'):
            config_data.setdefault('mqtt', {})['username'] = os.getenv('MQTT_USERNAME')
        if os.getenv('MQTT_PASSWORD'):
            config_data.setdefault('mqtt', {})['password'] = os.getenv('MQTT_PASSWORD')
        
        # Sparkplug overrides
        if os.getenv('SPARKPLUG_GROUP_ID'):
            config_data.setdefault('sparkplug', {})['group_id'] = os.getenv('SPARKPLUG_GROUP_ID')
        if os.getenv('SPARKPLUG_NODE_ID'):
            config_data.setdefault('sparkplug', {})['node_id'] = os.getenv('SPARKPLUG_NODE_ID')
        
        # Debug mode
        if os.getenv('DEBUG'):
            config_data['debug'] = os.getenv('DEBUG').lower() in ['true', '1', 'yes']
        
        # Environment
        if os.getenv('ENVIRONMENT'):
            config_data['environment'] = os.getenv('ENVIRONMENT')
        
        return config_data
    
    def save_config(self, config_path: Optional[str] = None) -> None:
        """Save current configuration to file"""
        if not self.config:
            raise ValueError("No configuration to save")
        
        save_path = config_path or self.config_path
        if not save_path:
            raise ValueError("No save path specified")
        
        try:
            config_data = self.config.dict()
            
            save_file = Path(save_path)
            with open(save_file, 'w') as f:
                if save_file.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(config_data, f, default_flow_style=False, indent=2)
                elif save_file.suffix.lower() == '.json':
                    json.dump(config_data, f, indent=2)
                else:
                    raise ValueError(f"Unsupported save format: {save_file.suffix}")
            
            self.logger.info(f"Configuration saved to {save_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise
    
    def validate_config(self) -> List[str]:
        """Validate current configuration and return any issues"""
        issues = []
        
        if not self.config:
            issues.append("No configuration loaded")
            return issues
        
        try:
            # Test MQTT configuration
            mqtt_config = self.config.mqtt
            if not mqtt_config.broker_host:
                issues.append("MQTT broker host not specified")
            
            # Test PLC configurations
            for i, plc in enumerate(self.config.plc_connections):
                if not plc.host:
                    issues.append(f"PLC connection {i}: host not specified")
                if not plc.tags:
                    issues.append(f"PLC connection {i}: no tags configured")
            
            # Test metric mappings
            for i, mapping in enumerate(self.config.metric_mappings):
                if not mapping.machine_id:
                    issues.append(f"Metric mapping {i}: machine_id not specified")
                if not mapping.sparkplug_metric_name:
                    issues.append(f"Metric mapping {i}: sparkplug_metric_name not specified")
            
        except Exception as e:
            issues.append(f"Configuration validation error: {e}")
        
        return issues
    
    def enable_hot_reload(self, callback: Optional[Callable] = None):
        """Enable hot reload of configuration file"""
        if not self.config_path:
            raise ValueError("No configuration file path available for hot reload")
        
        if callback:
            self.callbacks.append(callback)
        
        # Setup file watcher
        event_handler = ConfigFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(
            event_handler,
            str(Path(self.config_path).parent),
            recursive=False
        )
        self.observer.start()
        
        self.logger.info("Hot reload enabled for configuration")
    
    def disable_hot_reload(self):
        """Disable hot reload"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.callbacks.clear()
        
        self.logger.info("Hot reload disabled")
    
    def add_reload_callback(self, callback: Callable):
        """Add callback for configuration reload events"""
        self.callbacks.append(callback)
    
    def _notify_reload(self):
        """Notify callbacks of configuration reload"""
        for callback in self.callbacks:
            try:
                callback(self.config)
            except Exception as e:
                self.logger.error(f"Reload callback error: {e}")
    
    def get_config(self) -> Optional[SparkplugAgentConfig]:
        """Get current configuration"""
        return self.config
    
    def create_default_config(self, config_path: str) -> SparkplugAgentConfig:
        """Create a default configuration file"""
        default_config = SparkplugAgentConfig(
            mqtt=MQTTConfig(
                broker_host="localhost",
                broker_port=1883,
            ),
            plc_connections=[
                PLCConnectionConfig(
                    id="demo_plc",
                    type="SIEMENS_S7",
                    host="192.168.1.100",
                    tags=[
                        {
                            "name": "cycle_start",
                            "address": "DB1,0.0",
                            "data_type": "BOOL",
                            "description": "Production cycle start signal",
                            "oee_metric_type": "CYCLE_START"
                        },
                        {
                            "name": "part_count",
                            "address": "DB1,2",
                            "data_type": "INT",
                            "description": "Good parts counter",
                            "oee_metric_type": "PART_COUNT_GOOD"
                        }
                    ]
                )
            ],
            metric_mappings=[
                MetricMappingConfig(
                    machine_id="MACHINE_001",
                    sparkplug_metric_name="cycle_start",
                    oee_metric_type="CYCLE_START"
                ),
                MetricMappingConfig(
                    machine_id="MACHINE_001",
                    sparkplug_metric_name="part_count",
                    oee_metric_type="PART_COUNT_GOOD"
                )
            ]
        )
        
        # Save default configuration
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            if config_file.suffix.lower() in ['.yaml', '.yml']:
                yaml.dump(default_config.dict(), f, default_flow_style=False, indent=2)
            else:
                json.dump(default_config.dict(), f, indent=2)
        
        self.config = default_config
        self.config_path = config_path
        
        self.logger.info(f"Default configuration created at {config_path}")
        return default_config


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration hot reload"""
    
    def __init__(self, config_manager: ConfigurationManager):
        self.config_manager = config_manager
        self.logger = config_manager.logger
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        if event.src_path == self.config_manager.config_path:
            self.logger.info("Configuration file modified, reloading...")
            try:
                self.config_manager.load_config(self.config_manager.config_path)
                self.config_manager._notify_reload()
            except Exception as e:
                self.logger.error(f"Failed to reload configuration: {e}")


# Configuration validation functions
def validate_plc_connection(config: PLCConnectionConfig) -> List[str]:
    """Validate PLC connection configuration"""
    issues = []
    
    # Check required fields
    if not config.host:
        issues.append("Host is required")
    
    # Validate port range
    if config.port < 1 or config.port > 65535:
        issues.append("Port must be between 1 and 65535")
    
    # Validate timeout
    if config.timeout <= 0:
        issues.append("Timeout must be positive")
    
    return issues


def validate_tag_config(config: TagConfig) -> List[str]:
    """Validate tag configuration"""
    issues = []
    
    # Check required fields
    if not config.name:
        issues.append("Tag name is required")
    if not config.address:
        issues.append("Tag address is required")
    if not config.data_type:
        issues.append("Tag data type is required")
    
    # Validate scaling
    if config.scaling_factor == 0:
        issues.append("Scaling factor cannot be zero")
    
    # Validate value range
    if config.min_value is not None and config.max_value is not None:
        if config.min_value >= config.max_value:
            issues.append("Minimum value must be less than maximum value")
    
    return issues