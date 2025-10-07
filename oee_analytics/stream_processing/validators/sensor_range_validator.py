"""
Sensor Range Validator
Validates sensor values against database-configured ranges per machine/signal
"""

import logging
from typing import Optional, Tuple
from asgiref.sync import sync_to_async

from ..normalizer import NormalizedMetric


class SensorRangeValidator:
    """Validate sensor values are within expected range"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.range_cache = {}
        self.cache_ttl_seconds = 300  # 5 minutes

    async def validate(self, metric: NormalizedMetric) -> Tuple[bool, Optional[str]]:
        """
        Check if metric value is within expected range

        Args:
            metric: Normalized metric to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        from oee_analytics.models import SensorRangeConfig

        # Get range config from database
        range_config = await self._get_range_config(
            metric.machine_id,
            metric.signal_type
        )

        if not range_config:
            # No range configured - pass validation
            return True, None

        # Validate value against range
        try:
            value = float(metric.value)

            if value < float(range_config.min_value):
                error_msg = (
                    f"Out-of-range: {metric.machine_id}.{metric.name} = {value} "
                    f"(below minimum {range_config.min_value} {range_config.unit})"
                )
                self.logger.warning(error_msg)

                # Degrade quality score
                metric.quality = 50

                return False, error_msg

            if value > float(range_config.max_value):
                error_msg = (
                    f"Out-of-range: {metric.machine_id}.{metric.name} = {value} "
                    f"(exceeds maximum {range_config.max_value} {range_config.unit})"
                )
                self.logger.warning(error_msg)

                # Degrade quality score
                metric.quality = 50

                return False, error_msg

            return True, None

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid numeric value for {metric.machine_id}.{metric.name}: {e}"
            self.logger.error(error_msg)
            return False, error_msg

    @sync_to_async
    def _get_range_config(self, machine_id: str, signal_type: str):
        """Get range configuration from database with caching"""
        from oee_analytics.models import SensorRangeConfig
        from datetime import datetime

        # Check cache first
        cache_key = f"{machine_id}:{signal_type}"

        if cache_key in self.range_cache:
            cached_time, config = self.range_cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl_seconds:
                return config

        # Query database
        try:
            config = SensorRangeConfig.objects.filter(
                machine_id=machine_id,
                signal_type=signal_type,
                is_active=True
            ).first()

            # Update cache
            self.range_cache[cache_key] = (datetime.now(), config)

            return config

        except Exception as e:
            self.logger.error(f"Error querying SensorRangeConfig: {e}")
            return None

    def clear_cache(self):
        """Clear the range configuration cache"""
        self.range_cache = {}
        self.logger.info("Range configuration cache cleared")
