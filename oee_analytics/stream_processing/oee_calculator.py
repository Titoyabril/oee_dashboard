"""
OEE Calculator Service
Stateless microservice for real-time OEE calculations
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict

from prometheus_client import Counter, Histogram, Gauge

from .normalizer import NormalizedMetric


@dataclass
class OEEWindow:
    """Rolling window for OEE calculation"""
    machine_id: str
    window_start: datetime
    window_end: datetime

    # Time tracking (minutes)
    planned_production_time: float = 0.0
    downtime: float = 0.0
    runtime: float = 0.0

    # Performance tracking
    ideal_cycle_time: Optional[float] = None
    actual_cycle_time: Optional[float] = None
    good_count: int = 0
    total_count: int = 0

    # Quality tracking
    scrap_count: int = 0
    rework_count: int = 0

    # Metadata
    shift_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OEEResult:
    """Calculated OEE metrics"""
    machine_id: str
    line_id: str
    site_id: str
    timestamp: datetime

    # Primary OEE components (0-100%)
    availability: float
    performance: float
    quality: float
    oee: float

    # Supporting metrics
    runtime_minutes: float
    downtime_minutes: float
    planned_production_time_minutes: float
    good_count: int
    total_count: int
    scrap_count: int
    ideal_cycle_time_seconds: Optional[float]
    actual_cycle_time_seconds: Optional[float]

    # MTTR/MTBF
    mttr_minutes: Optional[float] = None
    mtbf_minutes: Optional[float] = None
    failure_count: int = 0

    # Window info
    window_start: datetime = None
    window_end: datetime = None
    shift_id: Optional[str] = None


class OEECalculator:
    """
    Stateless OEE calculator service.

    Consumes normalized metrics, maintains rolling windows,
    and publishes OEE results for storage and dashboards.
    """

    def __init__(
        self,
        default_window_minutes: int = 60,
        ideal_cycle_times: Optional[Dict[str, float]] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.default_window_minutes = default_window_minutes
        self.ideal_cycle_times = ideal_cycle_times or {}

        # Active windows by machine
        self.windows: Dict[str, OEEWindow] = {}

        # Downtime tracking
        self.active_downtimes: Dict[str, datetime] = {}  # machine_id -> downtime start
        self.downtime_history: Dict[str, List[float]] = defaultdict(list)  # for MTTR

        # Prometheus metrics
        self.oee_gauge = Gauge(
            'oee_calculator_oee_percent',
            'Current OEE percentage',
            ['machine_id', 'line_id']
        )

        self.availability_gauge = Gauge(
            'oee_calculator_availability_percent',
            'Current availability percentage',
            ['machine_id', 'line_id']
        )

        self.performance_gauge = Gauge(
            'oee_calculator_performance_percent',
            'Current performance percentage',
            ['machine_id', 'line_id']
        )

        self.quality_gauge = Gauge(
            'oee_calculator_quality_percent',
            'Current quality percentage',
            ['machine_id', 'line_id']
        )

        self.calculations_total = Counter(
            'oee_calculator_calculations_total',
            'Total OEE calculations performed',
            ['machine_id']
        )

        self.calculation_errors = Counter(
            'oee_calculator_errors_total',
            'OEE calculation errors',
            ['machine_id', 'error_type']
        )

    async def process_metric(self, metric: NormalizedMetric) -> Optional[OEEResult]:
        """
        Process a normalized metric and update OEE calculation.

        Returns OEE result if window is complete, otherwise None.
        """
        try:
            machine_id = metric.machine_id

            # Get or create window
            if machine_id not in self.windows:
                self.windows[machine_id] = self._create_window(
                    machine_id,
                    metric.timestamp_utc
                )

            window = self.windows[machine_id]

            # Check if metric is outside current window
            if metric.timestamp_utc > window.window_end:
                # Calculate OEE for completed window
                result = await self._calculate_oee(window, metric.line_id, metric.site_id)

                # Create new window
                self.windows[machine_id] = self._create_window(
                    machine_id,
                    metric.timestamp_utc
                )
                window = self.windows[machine_id]

                return result

            # Update window based on signal type
            signal_type = metric.signal_type

            if signal_type == 'counter.good':
                window.good_count = int(metric.value)
                window.total_count = max(window.total_count, window.good_count)

            elif signal_type == 'counter.total':
                window.total_count = int(metric.value)

            elif signal_type == 'counter.scrap':
                window.scrap_count = int(metric.value)

            elif signal_type == 'cycle.time_actual':
                window.actual_cycle_time = float(metric.value)

            elif signal_type == 'cycle.time_ideal':
                window.ideal_cycle_time = float(metric.value)

            elif signal_type == 'state.down':
                await self._handle_downtime_state(machine_id, bool(metric.value), metric.timestamp_utc)

            elif signal_type == 'state.run':
                await self._handle_run_state(machine_id, bool(metric.value), metric.timestamp_utc)

            elif signal_type == 'utilization.planned_time':
                window.planned_production_time = float(metric.value)

            return None  # Window not complete

        except Exception as e:
            self.logger.error(f"Error processing metric {metric.name}: {e}", exc_info=True)
            self.calculation_errors.labels(
                machine_id=metric.machine_id,
                error_type='metric_processing'
            ).inc()
            return None

    async def _calculate_oee(
        self,
        window: OEEWindow,
        line_id: str,
        site_id: str
    ) -> OEEResult:
        """Calculate OEE for a completed window"""
        try:
            machine_id = window.machine_id

            # Calculate Availability
            if window.planned_production_time > 0:
                window.runtime = window.planned_production_time - window.downtime
                availability = (window.runtime / window.planned_production_time) * 100
            else:
                # Fallback: assume window duration is planned time
                window_duration = (window.window_end - window.window_start).total_seconds() / 60.0
                window.runtime = window_duration - window.downtime
                availability = (window.runtime / window_duration) * 100 if window_duration > 0 else 0.0

            availability = max(0.0, min(100.0, availability))

            # Calculate Performance
            ideal_cycle = window.ideal_cycle_time or self.ideal_cycle_times.get(machine_id)

            if ideal_cycle and window.runtime > 0 and window.total_count > 0:
                # Performance = (Ideal Cycle Time × Total Count) / Run Time
                ideal_time_minutes = (ideal_cycle * window.total_count) / 60.0
                performance = (ideal_time_minutes / window.runtime) * 100
            else:
                # Fallback: use actual vs ideal cycle time if available
                if window.actual_cycle_time and window.ideal_cycle_time:
                    performance = (window.ideal_cycle_time / window.actual_cycle_time) * 100
                else:
                    performance = 100.0  # Assume 100% if no data

            performance = max(0.0, min(100.0, performance))

            # Calculate Quality
            if window.total_count > 0:
                quality = (window.good_count / window.total_count) * 100
            else:
                quality = 100.0  # No parts = no defects

            quality = max(0.0, min(100.0, quality))

            # Calculate OEE
            oee = (availability * performance * quality) / 10000.0

            # Calculate MTTR/MTBF
            mttr = self._calculate_mttr(machine_id)
            mtbf = self._calculate_mtbf(machine_id, window)

            # Create result
            result = OEEResult(
                machine_id=machine_id,
                line_id=line_id,
                site_id=site_id,
                timestamp=window.window_end,
                availability=round(availability, 2),
                performance=round(performance, 2),
                quality=round(quality, 2),
                oee=round(oee, 2),
                runtime_minutes=round(window.runtime, 2),
                downtime_minutes=round(window.downtime, 2),
                planned_production_time_minutes=round(window.planned_production_time, 2),
                good_count=window.good_count,
                total_count=window.total_count,
                scrap_count=window.scrap_count,
                ideal_cycle_time_seconds=window.ideal_cycle_time,
                actual_cycle_time_seconds=window.actual_cycle_time,
                mttr_minutes=mttr,
                mtbf_minutes=mtbf,
                failure_count=len(self.downtime_history.get(machine_id, [])),
                window_start=window.window_start,
                window_end=window.window_end,
                shift_id=window.shift_id
            )

            # Update Prometheus metrics
            self.oee_gauge.labels(machine_id=machine_id, line_id=line_id).set(oee)
            self.availability_gauge.labels(machine_id=machine_id, line_id=line_id).set(availability)
            self.performance_gauge.labels(machine_id=machine_id, line_id=line_id).set(performance)
            self.quality_gauge.labels(machine_id=machine_id, line_id=line_id).set(quality)
            self.calculations_total.labels(machine_id=machine_id).inc()

            self.logger.info(
                f"OEE calculated for {machine_id}: "
                f"OEE={oee:.1f}% (A={availability:.1f}%, P={performance:.1f}%, Q={quality:.1f}%)"
            )

            return result

        except Exception as e:
            self.logger.error(f"OEE calculation failed for {window.machine_id}: {e}", exc_info=True)
            self.calculation_errors.labels(
                machine_id=window.machine_id,
                error_type='calculation'
            ).inc()
            raise

    async def _handle_downtime_state(self, machine_id: str, is_down: bool, timestamp: datetime):
        """Handle downtime state changes"""
        if is_down:
            # Downtime started
            if machine_id not in self.active_downtimes:
                self.active_downtimes[machine_id] = timestamp
                self.logger.debug(f"Downtime started for {machine_id}")
        else:
            # Downtime ended
            if machine_id in self.active_downtimes:
                start_time = self.active_downtimes[machine_id]
                duration_minutes = (timestamp - start_time).total_seconds() / 60.0

                # Update window
                if machine_id in self.windows:
                    self.windows[machine_id].downtime += duration_minutes

                # Track for MTTR
                self.downtime_history[machine_id].append(duration_minutes)

                # Keep only last 100 downtimes for MTTR calculation
                if len(self.downtime_history[machine_id]) > 100:
                    self.downtime_history[machine_id] = self.downtime_history[machine_id][-100:]

                del self.active_downtimes[machine_id]
                self.logger.debug(f"Downtime ended for {machine_id}: {duration_minutes:.1f} min")

    async def _handle_run_state(self, machine_id: str, is_running: bool, timestamp: datetime):
        """Handle run state changes (inverse of downtime)"""
        await self._handle_downtime_state(machine_id, not is_running, timestamp)

    def _create_window(self, machine_id: str, start_time: datetime) -> OEEWindow:
        """Create a new OEE calculation window"""
        window_end = start_time + timedelta(minutes=self.default_window_minutes)

        return OEEWindow(
            machine_id=machine_id,
            window_start=start_time,
            window_end=window_end,
            ideal_cycle_time=self.ideal_cycle_times.get(machine_id)
        )

    def _calculate_mttr(self, machine_id: str) -> Optional[float]:
        """Calculate Mean Time To Repair"""
        downtimes = self.downtime_history.get(machine_id, [])
        if not downtimes:
            return None

        return sum(downtimes) / len(downtimes)

    def _calculate_mtbf(self, machine_id: str, window: OEEWindow) -> Optional[float]:
        """Calculate Mean Time Between Failures"""
        failure_count = len(self.downtime_history.get(machine_id, []))
        if failure_count == 0:
            return None

        # MTBF = Total Runtime / Number of Failures
        return window.runtime / failure_count

    def set_ideal_cycle_time(self, machine_id: str, cycle_time_seconds: float):
        """Set ideal cycle time for a machine"""
        self.ideal_cycle_times[machine_id] = cycle_time_seconds
        self.logger.info(f"Set ideal cycle time for {machine_id}: {cycle_time_seconds}s")

    def get_statistics(self) -> Dict[str, Any]:
        """Get calculator statistics"""
        return {
            'active_windows': len(self.windows),
            'active_downtimes': len(self.active_downtimes),
            'machines_tracked': list(self.windows.keys()),
            'ideal_cycle_times_configured': len(self.ideal_cycle_times),
        }
