"""
Tag Normalizer & Unit Conversion Service
Enriches metrics with asset metadata and applies unit conversions
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import json

from prometheus_client import Counter, Histogram

from .sparkplug_decoder import DecodedMetric


@dataclass
class TagMapping:
    """Configuration for tag normalization and enrichment"""
    source_tag: str
    signal_type: str  # state.run, counter.good, rate.instant, etc.
    machine_id: str
    line_id: str
    site_id: str

    # Unit conversion
    source_unit: Optional[str] = None
    target_unit: Optional[str] = None
    scale_factor: float = 1.0
    offset: float = 0.0

    # Deadband (for filtering noise)
    deadband_absolute: Optional[float] = None
    deadband_percent: Optional[float] = None

    # Quality filtering
    min_quality: int = 192  # Sparkplug GOOD quality

    # Metadata
    description: Optional[str] = None
    engineering_units: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedMetric:
    """Enriched and normalized metric ready for storage"""
    # Identity
    machine_id: str
    line_id: str
    site_id: str
    signal_type: str  # Canonical type
    name: str  # Original metric name

    # Value
    value: Any
    unit: str
    timestamp_utc: datetime

    # Quality
    quality: int
    is_valid: bool

    # Source tracking
    source_system: str = 'SPARKPLUG'
    source_node: Optional[str] = None
    source_device: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class Normalizer:
    """
    Stateless normalizer service.

    Takes decoded Sparkplug metrics, enriches with asset metadata,
    applies unit conversions and deadband filtering, and emits
    normalized metrics ready for time-series storage.
    """

    def __init__(
        self,
        tag_mappings: Optional[Dict[str, TagMapping]] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.tag_mappings = tag_mappings or {}

        # Last value cache for deadband filtering
        self.last_values: Dict[str, float] = {}

        # Prometheus metrics
        self.metrics_normalized = Counter(
            'normalizer_metrics_normalized_total',
            'Total metrics normalized',
            ['signal_type', 'machine_id']
        )

        self.metrics_filtered = Counter(
            'normalizer_metrics_filtered_total',
            'Metrics filtered out',
            ['reason']
        )

        self.normalization_errors = Counter(
            'normalizer_errors_total',
            'Normalization errors',
            ['error_type']
        )

        self.normalization_duration = Histogram(
            'normalizer_duration_seconds',
            'Time spent normalizing metrics'
        )

    def add_tag_mapping(self, mapping: TagMapping):
        """Add a tag mapping configuration"""
        self.tag_mappings[mapping.source_tag] = mapping
        self.logger.info(f"Added tag mapping: {mapping.source_tag} -> {mapping.signal_type}")

    def load_mappings_from_config(self, config: Dict[str, Any]):
        """Load tag mappings from configuration dictionary"""
        for mapping_config in config.get('tag_mappings', []):
            mapping = TagMapping(
                source_tag=mapping_config['source_tag'],
                signal_type=mapping_config['signal_type'],
                machine_id=mapping_config['machine_id'],
                line_id=mapping_config['line_id'],
                site_id=mapping_config['site_id'],
                source_unit=mapping_config.get('source_unit'),
                target_unit=mapping_config.get('target_unit'),
                scale_factor=mapping_config.get('scale_factor', 1.0),
                offset=mapping_config.get('offset', 0.0),
                deadband_absolute=mapping_config.get('deadband_absolute'),
                deadband_percent=mapping_config.get('deadband_percent'),
                min_quality=mapping_config.get('min_quality', 192),
                description=mapping_config.get('description'),
                engineering_units=mapping_config.get('engineering_units'),
                metadata=mapping_config.get('metadata', {})
            )
            self.add_tag_mapping(mapping)

    async def normalize_metric(
        self,
        decoded_metric: DecodedMetric,
        group_id: str,
        node_id: str,
        device_id: Optional[str] = None
    ) -> Optional[NormalizedMetric]:
        """
        Normalize a single decoded metric.

        Returns None if metric should be filtered out.
        """
        try:
            # Find tag mapping
            mapping = self.tag_mappings.get(decoded_metric.name)
            if not mapping:
                # No mapping found - log and skip
                self.logger.debug(f"No mapping for tag: {decoded_metric.name}")
                self.metrics_filtered.labels(reason='no_mapping').inc()
                return None

            # Check quality threshold
            if decoded_metric.quality is not None and decoded_metric.quality < mapping.min_quality:
                self.logger.debug(
                    f"Quality too low for {decoded_metric.name}: {decoded_metric.quality} < {mapping.min_quality}"
                )
                self.metrics_filtered.labels(reason='low_quality').inc()
                return None

            # Convert value
            converted_value = self._convert_value(decoded_metric.value, mapping)
            if converted_value is None:
                self.normalization_errors.labels(error_type='conversion_failed').inc()
                return None

            # Apply deadband filter
            if not self._passes_deadband(decoded_metric.name, converted_value, mapping):
                self.metrics_filtered.labels(reason='deadband').inc()
                return None

            # Convert timestamp
            timestamp_utc = datetime.fromtimestamp(
                decoded_metric.timestamp / 1000.0,
                tz=datetime.now().astimezone().tzinfo
            )

            # Create normalized metric
            normalized = NormalizedMetric(
                machine_id=mapping.machine_id,
                line_id=mapping.line_id,
                site_id=mapping.site_id,
                signal_type=mapping.signal_type,
                name=decoded_metric.name,
                value=converted_value,
                unit=mapping.target_unit or mapping.source_unit or '',
                timestamp_utc=timestamp_utc,
                quality=decoded_metric.quality or 192,
                is_valid=True,
                source_node=node_id,
                source_device=device_id,
                metadata={
                    'group_id': group_id,
                    'datatype': decoded_metric.datatype,
                    'is_historical': decoded_metric.is_historical,
                    'is_transient': decoded_metric.is_transient,
                    'description': mapping.description,
                    **decoded_metric.metadata,
                    **mapping.metadata
                }
            )

            # Record success
            self.metrics_normalized.labels(
                signal_type=mapping.signal_type,
                machine_id=mapping.machine_id
            ).inc()

            return normalized

        except Exception as e:
            self.logger.error(f"Normalization error for {decoded_metric.name}: {e}", exc_info=True)
            self.normalization_errors.labels(error_type='exception').inc()
            return None

    async def normalize_batch(
        self,
        decoded_metrics: List[DecodedMetric],
        group_id: str,
        node_id: str,
        device_id: Optional[str] = None
    ) -> List[NormalizedMetric]:
        """Normalize a batch of decoded metrics"""
        normalized = []

        for metric in decoded_metrics:
            result = await self.normalize_metric(metric, group_id, node_id, device_id)
            if result:
                normalized.append(result)

        return normalized

    def _convert_value(self, value: Any, mapping: TagMapping) -> Optional[Any]:
        """Apply unit conversion and scaling"""
        if value is None:
            return None

        try:
            # For numeric values, apply scaling
            if isinstance(value, (int, float)):
                converted = (value * mapping.scale_factor) + mapping.offset
                return converted
            else:
                # Non-numeric values pass through
                return value

        except Exception as e:
            self.logger.error(f"Value conversion failed: {e}")
            return None

    def _passes_deadband(self, tag_name: str, value: Any, mapping: TagMapping) -> bool:
        """
        Check if value passes deadband filter.

        Deadband prevents noise by only passing values that have changed
        significantly from the last reported value.
        """
        # Only apply deadband to numeric values
        if not isinstance(value, (int, float)):
            return True

        # No deadband configured
        if not mapping.deadband_absolute and not mapping.deadband_percent:
            # Update last value for future comparisons
            self.last_values[tag_name] = value
            return True

        # Get last value
        last_value = self.last_values.get(tag_name)

        # No previous value - always pass
        if last_value is None:
            self.last_values[tag_name] = value
            return True

        # Calculate change
        delta = abs(value - last_value)

        # Check absolute deadband
        if mapping.deadband_absolute:
            if delta < mapping.deadband_absolute:
                return False

        # Check percent deadband
        if mapping.deadband_percent and last_value != 0:
            percent_change = (delta / abs(last_value)) * 100
            if percent_change < mapping.deadband_percent:
                return False

        # Passes deadband - update last value
        self.last_values[tag_name] = value
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get normalizer statistics"""
        return {
            'tag_mappings_count': len(self.tag_mappings),
            'cached_values_count': len(self.last_values),
            'signal_types': list(set(m.signal_type for m in self.tag_mappings.values())),
            'machines_tracked': list(set(m.machine_id for m in self.tag_mappings.values())),
        }
