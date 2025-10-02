"""
Main Stream Processing Service
Orchestrates the complete processing pipeline: Decode → Normalize → Calculate/Detect
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import time

import paho.mqtt.client as mqtt
from prometheus_client import Counter, Histogram, Gauge, generate_latest

from .sparkplug_decoder import SparkplugDecoder, DecodedMetric
from .normalizer import Normalizer, NormalizedMetric
from .oee_calculator import OEECalculator, OEEResult
from .fault_state_machine import FaultStateMachine, Fault


@dataclass
class StreamProcessorConfig:
    """Configuration for stream processor"""
    mqtt_broker: str
    mqtt_port: int = 8883
    mqtt_client_id: str = "stream_processor"
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_ca_cert: Optional[str] = None
    mqtt_client_cert: Optional[str] = None
    mqtt_client_key: Optional[str] = None

    # Subscriptions
    sparkplug_topics: List[str] = None

    # Processing config
    oee_window_minutes: int = 60
    fault_dedup_seconds: int = 300

    # Output queues
    telemetry_output_queue: Optional[asyncio.Queue] = None
    events_output_queue: Optional[asyncio.Queue] = None


class StreamProcessor:
    """
    Main stream processing service.

    Pipeline:
    1. MQTT Consumer → Sparkplug Decoder
    2. Sparkplug Decoder → Normalizer
    3. Normalizer → {OEE Calculator, Fault State Machine}
    4. Output → {Telemetry Queue, Events Queue}
    """

    def __init__(
        self,
        config: StreamProcessorConfig,
        logger: Optional[logging.Logger] = None
    ):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Processing components
        self.decoder = SparkplugDecoder(logger=self.logger)
        self.normalizer = Normalizer(logger=self.logger)
        self.oee_calculator = OEECalculator(
            default_window_minutes=config.oee_window_minutes,
            logger=self.logger
        )
        self.fault_state_machine = FaultStateMachine(
            dedup_window_seconds=config.fault_dedup_seconds,
            logger=self.logger
        )

        # MQTT client
        self.mqtt_client = None
        self.connected = asyncio.Event()
        self.running = False

        # Output queues
        self.telemetry_queue = config.telemetry_output_queue or asyncio.Queue()
        self.events_queue = config.events_output_queue or asyncio.Queue()

        # Prometheus metrics
        self.messages_received = Counter(
            'stream_processor_messages_received_total',
            'Total MQTT messages received',
            ['message_type']
        )

        self.pipeline_duration = Histogram(
            'stream_processor_pipeline_duration_seconds',
            'End-to-end processing duration',
            ['stage']
        )

        self.pipeline_errors = Counter(
            'stream_processor_errors_total',
            'Pipeline processing errors',
            ['stage', 'error_type']
        )

        self.telemetry_emitted = Counter(
            'stream_processor_telemetry_emitted_total',
            'Telemetry records emitted',
            ['machine_id']
        )

        self.events_emitted = Counter(
            'stream_processor_events_emitted_total',
            'Events emitted',
            ['event_type']
        )

    async def start(self):
        """Start the stream processor"""
        self.logger.info("Starting stream processor...")

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client(client_id=self.config.mqtt_client_id)

        # Configure TLS
        if self.config.mqtt_ca_cert:
            self.mqtt_client.tls_set(
                ca_certs=self.config.mqtt_ca_cert,
                certfile=self.config.mqtt_client_cert,
                keyfile=self.config.mqtt_client_key
            )

        # Set authentication
        if self.config.mqtt_username:
            self.mqtt_client.username_pw_set(
                self.config.mqtt_username,
                self.config.mqtt_password
            )

        # Set callbacks
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message

        # Connect to broker
        self.logger.info(f"Connecting to MQTT broker: {self.config.mqtt_broker}:{self.config.mqtt_port}")
        self.mqtt_client.connect_async(self.config.mqtt_broker, self.config.mqtt_port)
        self.mqtt_client.loop_start()

        # Wait for connection
        await asyncio.wait_for(self.connected.wait(), timeout=30.0)

        self.running = True
        self.logger.info("Stream processor started successfully")

    async def stop(self):
        """Stop the stream processor"""
        self.logger.info("Stopping stream processor...")
        self.running = False

        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

        self.logger.info("Stream processor stopped")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")

            # Subscribe to Sparkplug topics
            topics = self.config.sparkplug_topics or [
                'spBv1.0/+/NBIRTH/+',
                'spBv1.0/+/NDEATH/+',
                'spBv1.0/+/DBIRTH/+/+',
                'spBv1.0/+/DDEATH/+/+',
                'spBv1.0/+/NDATA/+',
                'spBv1.0/+/DDATA/+/+',
            ]

            for topic in topics:
                client.subscribe(topic, qos=1)
                self.logger.info(f"Subscribed to: {topic}")

            self.connected.set()
        else:
            self.logger.error(f"MQTT connection failed: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.connected.clear()
        if rc != 0:
            self.logger.warning(f"Unexpected disconnect: {rc}")

    def _on_message(self, client, userdata, msg):
        """MQTT message callback"""
        # Process message asynchronously
        asyncio.create_task(self._process_message(msg.topic, msg.payload))

    async def _process_message(self, topic: str, payload: bytes):
        """Process a single MQTT message through the pipeline"""
        start_time = time.time()

        try:
            # Stage 1: Decode Sparkplug message
            decode_start = time.time()
            message_type, decoded_metrics = await self.decoder.decode_message(topic, payload)
            self.pipeline_duration.labels(stage='decode').observe(time.time() - decode_start)

            if not decoded_metrics:
                return

            self.messages_received.labels(message_type=message_type).inc()

            # Extract identifiers from topic
            parts = topic.split('/')
            group_id = parts[1] if len(parts) > 1 else 'unknown'
            node_id = parts[3] if len(parts) > 3 else 'unknown'
            device_id = parts[4] if len(parts) > 4 else None

            # Stage 2: Normalize metrics
            normalize_start = time.time()
            normalized_metrics = await self.normalizer.normalize_batch(
                decoded_metrics,
                group_id,
                node_id,
                device_id
            )
            self.pipeline_duration.labels(stage='normalize').observe(time.time() - normalize_start)

            if not normalized_metrics:
                return

            # Stage 3: Process through calculators
            for metric in normalized_metrics:
                await self._process_normalized_metric(metric)

            # Record total pipeline duration
            total_duration = time.time() - start_time
            self.pipeline_duration.labels(stage='total').observe(total_duration)

        except Exception as e:
            self.logger.error(f"Pipeline error: {e}", exc_info=True)
            self.pipeline_errors.labels(stage='pipeline', error_type=type(e).__name__).inc()

    async def _process_normalized_metric(self, metric: NormalizedMetric):
        """Process a normalized metric through calculators and emit outputs"""
        try:
            # Send to telemetry queue
            await self.telemetry_queue.put({
                'type': 'telemetry',
                'data': {
                    'machine_id': metric.machine_id,
                    'line_id': metric.line_id,
                    'site_id': metric.site_id,
                    'name': metric.name,
                    'signal_type': metric.signal_type,
                    'value': metric.value,
                    'unit': metric.unit,
                    'timestamp_utc': metric.timestamp_utc.isoformat(),
                    'quality': metric.quality,
                    'metadata': metric.metadata
                }
            })

            self.telemetry_emitted.labels(machine_id=metric.machine_id).inc()

            # Process through OEE calculator
            oee_result = await self.oee_calculator.process_metric(metric)
            if oee_result:
                await self._emit_oee_result(oee_result)

            # Process through fault state machine
            fault_result = await self.fault_state_machine.process_metric(metric)
            if fault_result:
                await self._emit_fault_event(fault_result)

        except Exception as e:
            self.logger.error(f"Error processing normalized metric: {e}", exc_info=True)
            self.pipeline_errors.labels(
                stage='processing',
                error_type=type(e).__name__
            ).inc()

    async def _emit_oee_result(self, result: OEEResult):
        """Emit OEE calculation result to events queue"""
        await self.events_queue.put({
            'type': 'oee_result',
            'data': {
                'machine_id': result.machine_id,
                'line_id': result.line_id,
                'site_id': result.site_id,
                'timestamp': result.timestamp.isoformat(),
                'oee': result.oee,
                'availability': result.availability,
                'performance': result.performance,
                'quality': result.quality,
                'runtime_minutes': result.runtime_minutes,
                'downtime_minutes': result.downtime_minutes,
                'good_count': result.good_count,
                'total_count': result.total_count,
                'scrap_count': result.scrap_count,
                'mttr_minutes': result.mttr_minutes,
                'mtbf_minutes': result.mtbf_minutes,
                'window_start': result.window_start.isoformat() if result.window_start else None,
                'window_end': result.window_end.isoformat() if result.window_end else None,
            }
        })

        self.events_emitted.labels(event_type='oee_calculation').inc()

        self.logger.info(
            f"OEE result emitted: {result.machine_id} OEE={result.oee:.1f}%"
        )

    async def _emit_fault_event(self, fault: Fault):
        """Emit fault event to events queue"""
        await self.events_queue.put({
            'type': 'fault_event',
            'data': {
                'fault_id': fault.fault_id,
                'machine_id': fault.machine_id,
                'line_id': fault.line_id,
                'site_id': fault.site_id,
                'fault_code': fault.fault_code,
                'fault_description': fault.fault_description,
                'severity': fault.severity.name,
                'state': fault.state.name,
                'start_time': fault.start_time.isoformat(),
                'end_time': fault.end_time.isoformat() if fault.end_time else None,
                'occurrence_count': fault.occurrence_count,
                'acknowledged_by': fault.acknowledged_by,
                'acknowledged_at': fault.acknowledged_at.isoformat() if fault.acknowledged_at else None,
                'metadata': fault.metadata
            }
        })

        self.events_emitted.labels(event_type='fault').inc()

        self.logger.info(
            f"Fault event emitted: {fault.fault_code} on {fault.machine_id} "
            f"({fault.state.name})"
        )

    def load_configuration(self, config: Dict[str, Any]):
        """Load processing configuration"""
        # Load tag mappings
        if 'tag_mappings' in config:
            self.normalizer.load_mappings_from_config(config)

        # Load ideal cycle times
        if 'ideal_cycle_times' in config:
            for machine_id, cycle_time in config['ideal_cycle_times'].items():
                self.oee_calculator.set_ideal_cycle_time(machine_id, cycle_time)

        self.logger.info("Configuration loaded successfully")

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all components"""
        return {
            'decoder': self.decoder.get_statistics(),
            'normalizer': self.normalizer.get_statistics(),
            'oee_calculator': self.oee_calculator.get_statistics(),
            'fault_state_machine': self.fault_state_machine.get_statistics(),
            'queues': {
                'telemetry_queue_size': self.telemetry_queue.qsize(),
                'events_queue_size': self.events_queue.qsize(),
            },
            'connected': self.connected.is_set(),
            'running': self.running,
        }

    def get_metrics_text(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest().decode('utf-8')


# Standalone service entry point
async def main():
    """Run stream processor as standalone service"""
    import sys
    import yaml

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger('stream_processor')

    # Load configuration
    config_file = sys.argv[1] if len(sys.argv) > 1 else 'stream_processor_config.yml'
    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)

    # Create processor
    processor_config = StreamProcessorConfig(**config_dict['processor'])
    processor = StreamProcessor(processor_config, logger=logger)

    # Load processing rules
    if 'processing' in config_dict:
        processor.load_configuration(config_dict['processing'])

    # Start processor
    await processor.start()

    try:
        # Run forever
        while True:
            await asyncio.sleep(60)

            # Log statistics
            stats = processor.get_statistics()
            logger.info(f"Statistics: {json.dumps(stats, indent=2)}")

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        await processor.stop()


if __name__ == '__main__':
    asyncio.run(main())
