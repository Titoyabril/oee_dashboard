"""
Sparkplug B Decoder Service
Decodes Sparkplug B payloads and manages alias cache from DBIRTH messages
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import time

import eclipse.tahu.client.SparkplugBPayload_pb2 as sparkplug
from prometheus_client import Counter, Histogram, Gauge


@dataclass
class AliasMapping:
    """Alias to metric name mapping from DBIRTH"""
    alias: int
    name: str
    datatype: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecodedMetric:
    """Decoded Sparkplug metric with enrichment"""
    name: str
    value: Any
    timestamp: int  # Unix timestamp in milliseconds
    datatype: str
    quality: Optional[int] = None
    is_historical: bool = False
    is_transient: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class SparkplugDecoder:
    """
    Stateless Sparkplug B decoder service with alias cache management.

    Consumes MQTT messages, decodes Sparkplug payloads, resolves aliases,
    and emits normalized metric streams.
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 3600,
        logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.cache_ttl_seconds = cache_ttl_seconds

        # Alias cache: {(group_id, node_id, device_id): {alias: AliasMapping}}
        self.alias_cache: Dict[Tuple[str, str, str], Dict[int, AliasMapping]] = defaultdict(dict)

        # Cache metadata for TTL management
        self.cache_timestamps: Dict[Tuple[str, str, str], float] = {}

        # Prometheus metrics
        self.metrics_decoded = Counter(
            'sparkplug_decoder_metrics_decoded_total',
            'Total metrics decoded',
            ['message_type', 'group_id', 'node_id']
        )

        self.decode_errors = Counter(
            'sparkplug_decoder_errors_total',
            'Decoding errors',
            ['error_type', 'message_type']
        )

        self.alias_cache_size = Gauge(
            'sparkplug_decoder_alias_cache_size',
            'Number of entries in alias cache'
        )

        self.decode_duration = Histogram(
            'sparkplug_decoder_duration_seconds',
            'Time spent decoding messages',
            ['message_type']
        )

    async def decode_message(
        self,
        topic: str,
        payload: bytes,
        received_timestamp: Optional[datetime] = None
    ) -> Tuple[str, List[DecodedMetric]]:
        """
        Decode a Sparkplug B message.

        Args:
            topic: MQTT topic (spBv1.0/<group>/<type>/<node>[/<device>])
            payload: Sparkplug protobuf payload
            received_timestamp: When message was received (for latency tracking)

        Returns:
            Tuple of (message_type, list of decoded metrics)
        """
        start_time = time.time()

        try:
            # Parse topic
            parsed_topic = self._parse_topic(topic)
            if not parsed_topic:
                self.decode_errors.labels(error_type='invalid_topic', message_type='unknown').inc()
                return ('UNKNOWN', [])

            group_id, message_type, node_id, device_id = parsed_topic

            # Decode protobuf
            sparkplug_payload = sparkplug.Payload()
            sparkplug_payload.ParseFromString(payload)

            # Handle based on message type
            if message_type in ['NBIRTH', 'DBIRTH']:
                decoded_metrics = await self._decode_birth_message(
                    sparkplug_payload,
                    group_id,
                    node_id,
                    device_id,
                    message_type
                )
            elif message_type in ['NDATA', 'DDATA']:
                decoded_metrics = await self._decode_data_message(
                    sparkplug_payload,
                    group_id,
                    node_id,
                    device_id
                )
            elif message_type in ['NDEATH', 'DDEATH']:
                decoded_metrics = await self._decode_death_message(
                    sparkplug_payload,
                    group_id,
                    node_id,
                    device_id,
                    message_type
                )
            else:
                self.logger.warning(f"Unsupported message type: {message_type}")
                decoded_metrics = []

            # Record metrics
            self.metrics_decoded.labels(
                message_type=message_type,
                group_id=group_id,
                node_id=node_id
            ).inc(len(decoded_metrics))

            duration = time.time() - start_time
            self.decode_duration.labels(message_type=message_type).observe(duration)

            # Calculate ingestion lag if received_timestamp provided
            if received_timestamp and decoded_metrics:
                for metric in decoded_metrics:
                    metric.metadata['ingestion_lag_ms'] = (
                        received_timestamp.timestamp() * 1000 - metric.timestamp
                    )

            return (message_type, decoded_metrics)

        except Exception as e:
            self.logger.error(f"Decode error: {e}", exc_info=True)
            self.decode_errors.labels(
                error_type='decode_exception',
                message_type='unknown'
            ).inc()
            return ('ERROR', [])

    async def _decode_birth_message(
        self,
        payload: sparkplug.Payload,
        group_id: str,
        node_id: str,
        device_id: Optional[str],
        message_type: str
    ) -> List[DecodedMetric]:
        """Decode NBIRTH or DBIRTH and populate alias cache"""
        cache_key = (group_id, node_id, device_id or '')

        # Clear existing cache for this device/node
        self.alias_cache[cache_key] = {}

        decoded_metrics = []

        for metric in payload.metrics:
            # Store alias mapping if present
            if metric.HasField('alias'):
                self.alias_cache[cache_key][metric.alias] = AliasMapping(
                    alias=metric.alias,
                    name=metric.name,
                    datatype=metric.datatype,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        'is_historical': metric.is_historical,
                        'is_transient': metric.is_transient,
                    }
                )

            # Decode metric value
            decoded_metric = self._decode_metric(metric)
            if decoded_metric:
                decoded_metrics.append(decoded_metric)

        # Update cache timestamp
        self.cache_timestamps[cache_key] = time.time()
        self.alias_cache_size.set(sum(len(aliases) for aliases in self.alias_cache.values()))

        self.logger.info(
            f"Processed {message_type}: {len(decoded_metrics)} metrics, "
            f"{len(self.alias_cache[cache_key])} aliases cached"
        )

        return decoded_metrics

    async def _decode_data_message(
        self,
        payload: sparkplug.Payload,
        group_id: str,
        node_id: str,
        device_id: Optional[str]
    ) -> List[DecodedMetric]:
        """Decode NDATA or DDATA using alias cache"""
        cache_key = (group_id, node_id, device_id or '')
        alias_map = self.alias_cache.get(cache_key, {})

        decoded_metrics = []

        for metric in payload.metrics:
            # Resolve alias if present
            if metric.HasField('alias'):
                alias_mapping = alias_map.get(metric.alias)
                if alias_mapping:
                    # Use alias to get metric name
                    metric_name = alias_mapping.name

                    # Decode value
                    decoded_metric = self._decode_metric(metric)
                    if decoded_metric:
                        # Override name from alias
                        decoded_metric.name = metric_name
                        decoded_metric.metadata.update(alias_mapping.metadata)
                        decoded_metrics.append(decoded_metric)
                else:
                    self.logger.warning(
                        f"Unknown alias {metric.alias} for {group_id}/{node_id}/{device_id}"
                    )
                    self.decode_errors.labels(
                        error_type='unknown_alias',
                        message_type='DATA'
                    ).inc()
            else:
                # Metric has explicit name
                decoded_metric = self._decode_metric(metric)
                if decoded_metric:
                    decoded_metrics.append(decoded_metric)

        return decoded_metrics

    async def _decode_death_message(
        self,
        payload: sparkplug.Payload,
        group_id: str,
        node_id: str,
        device_id: Optional[str],
        message_type: str
    ) -> List[DecodedMetric]:
        """Decode NDEATH or DDEATH"""
        cache_key = (group_id, node_id, device_id or '')

        # Clear alias cache on death
        if cache_key in self.alias_cache:
            del self.alias_cache[cache_key]
            del self.cache_timestamps[cache_key]
            self.alias_cache_size.set(sum(len(aliases) for aliases in self.alias_cache.values()))

        self.logger.info(f"{message_type} received for {group_id}/{node_id}/{device_id or 'NODE'}")

        # Return status metric
        return [
            DecodedMetric(
                name='node.online' if device_id else 'device.online',
                value=False,
                timestamp=int(time.time() * 1000),
                datatype='Boolean',
                metadata={
                    'group_id': group_id,
                    'node_id': node_id,
                    'device_id': device_id,
                    'message_type': message_type
                }
            )
        ]

    def _decode_metric(self, metric: sparkplug.Payload.Metric) -> Optional[DecodedMetric]:
        """Decode a single Sparkplug metric"""
        try:
            # Extract value based on datatype
            value = self._extract_value(metric)
            datatype = self._datatype_to_string(metric.datatype)

            return DecodedMetric(
                name=metric.name,
                value=value,
                timestamp=metric.timestamp if metric.HasField('timestamp') else int(time.time() * 1000),
                datatype=datatype,
                quality=metric.properties.quality if metric.HasField('properties') and metric.properties.HasField('quality') else None,
                is_historical=metric.is_historical if metric.HasField('is_historical') else False,
                is_transient=metric.is_transient if metric.HasField('is_transient') else False,
            )

        except Exception as e:
            self.logger.error(f"Failed to decode metric {metric.name}: {e}")
            self.decode_errors.labels(error_type='value_extraction', message_type='METRIC').inc()
            return None

    def _extract_value(self, metric: sparkplug.Payload.Metric) -> Any:
        """Extract value from metric based on datatype"""
        datatype = metric.datatype

        # Map Sparkplug datatypes to value fields
        if datatype == 1:  # Int8
            return metric.int_value
        elif datatype == 2:  # Int16
            return metric.int_value
        elif datatype == 3:  # Int32
            return metric.int_value
        elif datatype == 4:  # Int64
            return metric.long_value
        elif datatype == 5:  # UInt8
            return metric.int_value
        elif datatype == 6:  # UInt16
            return metric.int_value
        elif datatype == 7:  # UInt32
            return metric.int_value
        elif datatype == 8:  # UInt64
            return metric.long_value
        elif datatype == 9:  # Float
            return metric.float_value
        elif datatype == 10:  # Double
            return metric.double_value
        elif datatype == 11:  # Boolean
            return metric.boolean_value
        elif datatype == 12:  # String
            return metric.string_value
        elif datatype == 13:  # DateTime
            return metric.long_value
        elif datatype == 14:  # Text
            return metric.string_value
        else:
            self.logger.warning(f"Unsupported datatype: {datatype}")
            return None

    def _datatype_to_string(self, datatype: int) -> str:
        """Convert Sparkplug datatype enum to string"""
        datatype_map = {
            1: 'Int8', 2: 'Int16', 3: 'Int32', 4: 'Int64',
            5: 'UInt8', 6: 'UInt16', 7: 'UInt32', 8: 'UInt64',
            9: 'Float', 10: 'Double', 11: 'Boolean',
            12: 'String', 13: 'DateTime', 14: 'Text'
        }
        return datatype_map.get(datatype, f'Unknown({datatype})')

    def _parse_topic(self, topic: str) -> Optional[Tuple[str, str, str, Optional[str]]]:
        """
        Parse Sparkplug topic.

        Returns: (group_id, message_type, node_id, device_id)
        """
        try:
            parts = topic.split('/')

            if len(parts) < 4 or parts[0] != 'spBv1.0':
                return None

            group_id = parts[1]
            message_type = parts[2]
            node_id = parts[3]
            device_id = parts[4] if len(parts) > 4 else None

            return (group_id, message_type, node_id, device_id)

        except Exception as e:
            self.logger.error(f"Topic parse error: {e}")
            return None

    async def cleanup_stale_cache(self):
        """Remove stale alias cache entries"""
        current_time = time.time()
        stale_keys = []

        for cache_key, timestamp in self.cache_timestamps.items():
            if current_time - timestamp > self.cache_ttl_seconds:
                stale_keys.append(cache_key)

        for key in stale_keys:
            del self.alias_cache[key]
            del self.cache_timestamps[key]

        if stale_keys:
            self.logger.info(f"Cleaned up {len(stale_keys)} stale cache entries")
            self.alias_cache_size.set(sum(len(aliases) for aliases in self.alias_cache.values()))

    def get_statistics(self) -> Dict[str, Any]:
        """Get decoder statistics"""
        return {
            'alias_cache_entries': sum(len(aliases) for aliases in self.alias_cache.values()),
            'cached_nodes': len(self.alias_cache),
            'cache_memory_estimate_kb': sum(
                len(aliases) * 100 for aliases in self.alias_cache.values()
            ) // 1024,
        }
