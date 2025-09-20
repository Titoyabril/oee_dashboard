"""
Django Management Command: Sparkplug Agent
Production-ready command to run the Sparkplug B MQTT integration agent
Handles PLC connections, MQTT communication, and data processing
"""

import asyncio
import json
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import time

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from pydantic import BaseSettings, Field
from pydantic_settings import SettingsConfigDict

from ...sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig
from ...sparkplug.data_processor import SparkplugDataProcessor, MetricMapping, OEEMetricType
from ...sparkplug.connectors import PLCConnectorFactory, PLCConnectionConfig
from ...sparkplug.models import SparkplugMetricHistory


class SparkplugAgentSettings(BaseSettings):
    """Pydantic settings for Sparkplug Agent configuration"""
    model_config = SettingsConfigDict(env_prefix='SPARKPLUG_')
    
    # MQTT Broker Configuration
    mqtt_broker_host: str = Field(default="localhost", description="MQTT broker hostname")
    mqtt_broker_port: int = Field(default=1883, description="MQTT broker port")
    mqtt_username: Optional[str] = Field(default=None, description="MQTT username")
    mqtt_password: Optional[str] = Field(default=None, description="MQTT password")
    mqtt_use_tls: bool = Field(default=False, description="Use TLS for MQTT")
    mqtt_ca_cert: Optional[str] = Field(default=None, description="CA certificate path")
    mqtt_client_cert: Optional[str] = Field(default=None, description="Client certificate path")
    mqtt_client_key: Optional[str] = Field(default=None, description="Client key path")
    
    # Sparkplug Configuration
    group_id: str = Field(default="OEE_Group", description="Sparkplug group ID")
    node_id: str = Field(default="OEE_Node", description="Sparkplug node ID")
    subscribe_groups: str = Field(default="OEE_Group,Production", description="Comma-separated groups to subscribe to")
    
    # Agent Configuration
    config_file: Optional[str] = Field(default=None, description="Configuration file path")
    log_level: str = Field(default="INFO", description="Logging level")
    metrics_port: int = Field(default=8001, description="Prometheus metrics port")
    
    # Data Processing
    processing_enabled: bool = Field(default=True, description="Enable data processing")
    batch_size: int = Field(default=100, description="Batch size for processing")
    processing_interval: float = Field(default=1.0, description="Processing interval in seconds")
    
    # PLC Connection Settings
    plc_enabled: bool = Field(default=True, description="Enable PLC connections")
    plc_scan_rate: int = Field(default=1000, description="PLC scan rate in milliseconds")
    plc_connection_timeout: float = Field(default=5.0, description="PLC connection timeout")
    
    # Production Settings
    enable_commands: bool = Field(default=False, description="Enable Sparkplug commands")
    store_raw_messages: bool = Field(default=True, description="Store raw MQTT messages")
    data_retention_days: int = Field(default=90, description="Data retention period")


class Command(BaseCommand):
    """Django management command for Sparkplug Agent"""
    
    help = 'Run the Sparkplug B MQTT integration agent for OEE data collection'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent: Optional['SparkplugAgent'] = None
        self.shutdown_requested = False
    
    def add_arguments(self, parser):
        """Add command line arguments"""
        parser.add_argument(
            '--config-file',
            type=str,
            help='Path to configuration file (JSON)',
        )
        parser.add_argument(
            '--log-level',
            type=str,
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            default='INFO',
            help='Set the logging level',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode (no database writes)',
        )
        parser.add_argument(
            '--broker-host',
            type=str,
            help='MQTT broker hostname',
        )
        parser.add_argument(
            '--broker-port',
            type=int,
            help='MQTT broker port',
        )
        parser.add_argument(
            '--group-id',
            type=str,
            help='Sparkplug group ID',
        )
        parser.add_argument(
            '--node-id',
            type=str,
            help='Sparkplug node ID',
        )
        parser.add_argument(
            '--metrics-port',
            type=int,
            help='Prometheus metrics port',
        )
        parser.add_argument(
            '--disable-plc',
            action='store_true',
            help='Disable PLC connections',
        )
        parser.add_argument(
            '--disable-processing',
            action='store_true',
            help='Disable data processing',
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        try:
            # Setup logging
            self.setup_logging(options.get('log_level', 'INFO'))
            
            # Load configuration
            settings_obj = self.load_configuration(options)
            
            # Create and run agent
            self.agent = SparkplugAgent(settings_obj, options.get('dry_run', False))
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Run the agent
            self.stdout.write(self.style.SUCCESS('Starting Sparkplug Agent...'))
            asyncio.run(self.agent.run())
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nShutdown requested by user'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Agent failed: {e}'))
            raise CommandError(f'Agent failed: {e}')
        finally:
            self.stdout.write(self.style.SUCCESS('Sparkplug Agent stopped'))
    
    def setup_logging(self, log_level: str):
        """Setup logging configuration"""
        import structlog
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Setup standard logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def load_configuration(self, options: Dict[str, Any]) -> SparkplugAgentSettings:
        """Load configuration from file and command line options"""
        # Start with default settings
        config_data = {}
        
        # Load from file if specified
        config_file = options.get('config_file')
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config_data.update(json.load(f))
            self.stdout.write(f'Loaded configuration from {config_file}')
        
        # Override with command line options
        if options.get('broker_host'):
            config_data['mqtt_broker_host'] = options['broker_host']
        if options.get('broker_port'):
            config_data['mqtt_broker_port'] = options['broker_port']
        if options.get('group_id'):
            config_data['group_id'] = options['group_id']
        if options.get('node_id'):
            config_data['node_id'] = options['node_id']
        if options.get('metrics_port'):
            config_data['metrics_port'] = options['metrics_port']
        if options.get('disable_plc'):
            config_data['plc_enabled'] = False
        if options.get('disable_processing'):
            config_data['processing_enabled'] = False
        
        # Set log level
        config_data['log_level'] = options.get('log_level', 'INFO')
        
        return SparkplugAgentSettings(**config_data)
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.stdout.write(self.style.WARNING(f'\nReceived signal {signum}, shutting down...'))
            self.shutdown_requested = True
            if self.agent:
                asyncio.create_task(self.agent.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


class SparkplugAgent:
    """Main Sparkplug Agent implementation"""
    
    def __init__(self, settings: SparkplugAgentSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.logger = structlog.get_logger("sparkplug.agent")
        
        # Components
        self.mqtt_client: Optional[SparkplugMQTTClient] = None
        self.data_processor: Optional[SparkplugDataProcessor] = None
        self.plc_connectors: Dict[str, Any] = {}
        
        # Control
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # Tasks
        self.background_tasks: List[asyncio.Task] = []
        
        # Statistics
        self.start_time = None
        self.stats = {
            'uptime_seconds': 0,
            'mqtt_messages': 0,
            'processed_metrics': 0,
            'plc_connections': 0,
            'errors': 0,
        }
    
    async def run(self):
        """Main agent run loop"""
        try:
            self.start_time = time.time()
            self.running = True
            
            # Initialize components
            await self.initialize()
            
            # Start background tasks
            await self.start_background_tasks()
            
            # Main loop
            self.logger.info("Sparkplug Agent started successfully")
            await self.main_loop()
            
        except Exception as e:
            self.logger.error("Agent failed", error=str(e))
            raise
        finally:
            await self.cleanup()
    
    async def initialize(self):
        """Initialize all agent components"""
        self.logger.info("Initializing Sparkplug Agent", settings=self.settings.dict())
        
        # Initialize MQTT client
        await self.initialize_mqtt_client()
        
        # Initialize data processor
        if self.settings.processing_enabled:
            await self.initialize_data_processor()
        
        # Initialize PLC connections
        if self.settings.plc_enabled:
            await self.initialize_plc_connections()
        
        # Start metrics server
        if self.settings.metrics_port:
            await self.start_metrics_server()
    
    async def initialize_mqtt_client(self):
        """Initialize Sparkplug MQTT client"""
        config = SparkplugConfig(
            broker_host=self.settings.mqtt_broker_host,
            broker_port=self.settings.mqtt_broker_port,
            username=self.settings.mqtt_username,
            password=self.settings.mqtt_password,
            use_tls=self.settings.mqtt_use_tls,
            ca_cert_path=self.settings.mqtt_ca_cert,
            cert_path=self.settings.mqtt_client_cert,
            key_path=self.settings.mqtt_client_key,
            group_id=self.settings.group_id,
            node_id=self.settings.node_id,
            subscribe_group_ids=self.settings.subscribe_groups.split(','),
            enable_commands=self.settings.enable_commands,
            batch_size=self.settings.batch_size,
        )
        
        self.mqtt_client = SparkplugMQTTClient(config, self.logger)
        
        if not self.dry_run:
            success = await self.mqtt_client.start()
            if not success:
                raise RuntimeError("Failed to start MQTT client")
        
        self.logger.info("MQTT client initialized")
    
    async def initialize_data_processor(self):
        """Initialize data processor"""
        self.data_processor = SparkplugDataProcessor(self.logger)
        
        # Load metric mappings from configuration
        if self.settings.config_file and os.path.exists(self.settings.config_file):
            with open(self.settings.config_file, 'r') as f:
                config = json.load(f)
                if 'metric_mappings' in config:
                    self.data_processor.load_mappings_from_config(config['metric_mappings'])
        
        self.logger.info("Data processor initialized")
    
    async def initialize_plc_connections(self):
        """Initialize PLC connections"""
        # Load PLC configurations from file
        if self.settings.config_file and os.path.exists(self.settings.config_file):
            with open(self.settings.config_file, 'r') as f:
                config = json.load(f)
                
                for plc_config in config.get('plc_connections', []):
                    await self.connect_plc(plc_config)
        
        self.logger.info("PLC connections initialized", count=len(self.plc_connectors))
    
    async def connect_plc(self, plc_config: Dict[str, Any]):
        """Connect to a single PLC"""
        try:
            # Create connection config
            conn_config = PLCConnectionConfig(
                host=plc_config['host'],
                port=plc_config.get('port', 102),
                rack=plc_config.get('rack', 0),
                slot=plc_config.get('slot', 1),
                timeout=self.settings.plc_connection_timeout,
                scan_rate_ms=self.settings.plc_scan_rate,
            )
            
            # Create connector
            plc_type = plc_config['type']
            connector = PLCConnectorFactory.create_connector(plc_type, conn_config, self.logger)
            
            # Connect
            if not self.dry_run:
                success = await connector.connect()
                if not success:
                    self.logger.error("Failed to connect to PLC", plc=plc_config)
                    return
            
            # Add tag definitions
            for tag_config in plc_config.get('tags', []):
                connector.add_tag(tag_config)
            
            # Store connector
            plc_id = plc_config.get('id', plc_config['host'])
            self.plc_connectors[plc_id] = connector
            
            self.logger.info("Connected to PLC", plc_id=plc_id, type=plc_type, host=plc_config['host'])
            
        except Exception as e:
            self.logger.error("Failed to connect to PLC", plc=plc_config, error=str(e))
    
    async def start_metrics_server(self):
        """Start Prometheus metrics server"""
        try:
            from prometheus_client import start_http_server
            start_http_server(self.settings.metrics_port)
            self.logger.info("Metrics server started", port=self.settings.metrics_port)
        except Exception as e:
            self.logger.error("Failed to start metrics server", error=str(e))
    
    async def start_background_tasks(self):
        """Start background processing tasks"""
        # Data processing task
        if self.settings.processing_enabled and self.data_processor:
            task = asyncio.create_task(self.data_processing_loop())
            self.background_tasks.append(task)
        
        # PLC scanning tasks
        for plc_id, connector in self.plc_connectors.items():
            task = asyncio.create_task(self.plc_scanning_loop(plc_id, connector))
            self.background_tasks.append(task)
        
        # Statistics task
        task = asyncio.create_task(self.statistics_loop())
        self.background_tasks.append(task)
        
        self.logger.info("Background tasks started", count=len(self.background_tasks))
    
    async def main_loop(self):
        """Main agent loop"""
        try:
            while self.running and not self.shutdown_event.is_set():
                # Update statistics
                self.update_statistics()
                
                # Health checks
                await self.perform_health_checks()
                
                # Wait for shutdown or interval
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=30.0)
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    continue  # Normal timeout, continue loop
                
        except Exception as e:
            self.logger.error("Main loop error", error=str(e))
            raise
    
    async def data_processing_loop(self):
        """Background task for processing Sparkplug data"""
        self.logger.info("Starting data processing loop")
        
        while self.running and not self.shutdown_event.is_set():
            try:
                # Get unprocessed metric history records
                if not self.dry_run:
                    unprocessed = SparkplugMetricHistory.objects.filter(
                        # Add filter for unprocessed records
                    ).order_by('timestamp_utc')[:self.settings.batch_size]
                    
                    for metric_history in unprocessed:
                        await self.data_processor.process_metric_history(metric_history)
                
                # Wait for next processing interval
                await asyncio.sleep(self.settings.processing_interval)
                
            except Exception as e:
                self.logger.error("Data processing error", error=str(e))
                self.stats['errors'] += 1
                await asyncio.sleep(5.0)  # Back off on error
    
    async def plc_scanning_loop(self, plc_id: str, connector):
        """Background task for scanning PLC data"""
        self.logger.info("Starting PLC scanning loop", plc_id=plc_id)
        
        scan_interval = self.settings.plc_scan_rate / 1000.0  # Convert to seconds
        
        while self.running and not self.shutdown_event.is_set():
            try:
                if not self.dry_run and connector.is_connected():
                    # Read all configured tags
                    data_points = await connector.read_all_tags()
                    
                    # Process each data point
                    for data_point in data_points:
                        # TODO: Convert to Sparkplug metrics and publish
                        pass
                
                await asyncio.sleep(scan_interval)
                
            except Exception as e:
                self.logger.error("PLC scanning error", plc_id=plc_id, error=str(e))
                self.stats['errors'] += 1
                await asyncio.sleep(10.0)  # Back off on error
    
    async def statistics_loop(self):
        """Background task for updating statistics"""
        while self.running and not self.shutdown_event.is_set():
            try:
                self.update_statistics()
                self.log_statistics()
                
                await asyncio.sleep(60.0)  # Update every minute
                
            except Exception as e:
                self.logger.error("Statistics error", error=str(e))
                await asyncio.sleep(60.0)
    
    def update_statistics(self):
        """Update agent statistics"""
        if self.start_time:
            self.stats['uptime_seconds'] = int(time.time() - self.start_time)
        
        if self.mqtt_client:
            mqtt_stats = self.mqtt_client.get_statistics()
            self.stats['mqtt_messages'] = mqtt_stats.get('messages_received', 0)
        
        if self.data_processor:
            proc_stats = self.data_processor.get_statistics()
            self.stats['processed_metrics'] = proc_stats.get('processed_metrics', 0)
        
        self.stats['plc_connections'] = len(self.plc_connectors)
    
    def log_statistics(self):
        """Log current statistics"""
        self.logger.info("Agent statistics", **self.stats)
        
        if self.data_processor:
            proc_stats = self.data_processor.get_statistics()
            self.logger.info("Data processor statistics", **proc_stats)
    
    async def perform_health_checks(self):
        """Perform health checks on all components"""
        try:
            # Check MQTT connection
            if self.mqtt_client and not self.mqtt_client.connected:
                self.logger.warning("MQTT client disconnected")
            
            # Check PLC connections
            for plc_id, connector in self.plc_connectors.items():
                if not connector.is_connected():
                    self.logger.warning("PLC disconnected", plc_id=plc_id)
                    # Attempt reconnection
                    try:
                        await connector.connect()
                    except Exception as e:
                        self.logger.error("PLC reconnection failed", plc_id=plc_id, error=str(e))
            
        except Exception as e:
            self.logger.error("Health check error", error=str(e))
    
    async def shutdown(self):
        """Shutdown the agent gracefully"""
        self.logger.info("Shutting down Sparkplug Agent")
        self.running = False
        self.shutdown_event.set()
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            # Stop MQTT client
            if self.mqtt_client:
                await self.mqtt_client.stop()
            
            # Disconnect PLCs
            for plc_id, connector in self.plc_connectors.items():
                try:
                    await connector.disconnect()
                    self.logger.info("Disconnected from PLC", plc_id=plc_id)
                except Exception as e:
                    self.logger.error("PLC disconnect error", plc_id=plc_id, error=str(e))
            
            self.logger.info("Agent cleanup completed")
            
        except Exception as e:
            self.logger.error("Cleanup error", error=str(e))