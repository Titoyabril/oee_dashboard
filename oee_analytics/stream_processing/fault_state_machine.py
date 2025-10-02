"""
Fault State Machine Service
Manages fault lifecycle (start/stop/merge) with deduplication
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from prometheus_client import Counter, Gauge, Histogram

from .normalizer import NormalizedMetric


class FaultState(Enum):
    """Fault lifecycle states"""
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    MERGED = "MERGED"


class FaultSeverity(Enum):
    """Fault severity levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    INFO = 5


@dataclass
class Fault:
    """Active fault instance"""
    fault_id: str  # Unique ID for this fault instance
    machine_id: str
    line_id: str
    site_id: str

    fault_code: str
    fault_description: str
    severity: FaultSeverity

    start_time: datetime
    end_time: Optional[datetime] = None

    state: FaultState = FaultState.ACTIVE

    # Acknowledgement
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    # Deduplication
    occurrence_count: int = 1
    last_occurrence: datetime = field(default_factory=lambda: datetime.now())

    # Metadata
    source_node: Optional[str] = None
    source_device: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class FaultStateMachine:
    """
    Stateless fault management service.

    Tracks fault lifecycle, deduplicates repeated faults,
    merges related faults, and maintains fault history.
    """

    def __init__(
        self,
        dedup_window_seconds: int = 300,  # 5 minutes
        merge_window_seconds: int = 60,    # 1 minute
        logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.dedup_window_seconds = dedup_window_seconds
        self.merge_window_seconds = merge_window_seconds

        # Active faults: {fault_signature: Fault}
        self.active_faults: Dict[str, Fault] = {}

        # Recent fault signatures for deduplication
        self.recent_signatures: Dict[str, datetime] = {}

        # Prometheus metrics
        self.faults_active = Gauge(
            'fault_state_machine_active_faults',
            'Number of active faults',
            ['machine_id', 'severity']
        )

        self.faults_created = Counter(
            'fault_state_machine_faults_created_total',
            'Total faults created',
            ['machine_id', 'severity']
        )

        self.faults_resolved = Counter(
            'fault_state_machine_faults_resolved_total',
            'Total faults resolved',
            ['machine_id', 'severity']
        )

        self.faults_deduplicated = Counter(
            'fault_state_machine_faults_deduplicated_total',
            'Total faults deduplicated',
            ['machine_id']
        )

        self.fault_duration = Histogram(
            'fault_state_machine_fault_duration_seconds',
            'Fault duration',
            ['machine_id', 'severity']
        )

    async def process_metric(self, metric: NormalizedMetric) -> Optional[Fault]:
        """
        Process a normalized metric for fault detection.

        Returns Fault object if fault state changed, otherwise None.
        """
        try:
            # Only process fault-related signals
            if not metric.signal_type.startswith('fault.'):
                return None

            if metric.signal_type == 'fault.code':
                return await self._handle_fault_code(metric)
            elif metric.signal_type == 'fault.active':
                return await self._handle_fault_active(metric)
            elif metric.signal_type == 'fault.severity':
                return await self._handle_fault_severity(metric)

            return None

        except Exception as e:
            self.logger.error(f"Error processing fault metric: {e}", exc_info=True)
            return None

    async def _handle_fault_code(self, metric: NormalizedMetric) -> Optional[Fault]:
        """Handle fault code signal (fault start)"""
        fault_code = str(metric.value)

        # Ignore '0' or empty fault codes (no fault)
        if not fault_code or fault_code == '0':
            return None

        # Create fault signature for deduplication
        signature = self._create_signature(
            metric.machine_id,
            fault_code,
            metric.timestamp_utc
        )

        # Check if this is a duplicate
        if self._is_duplicate(signature):
            self.logger.debug(f"Duplicate fault ignored: {fault_code} on {metric.machine_id}")
            self.faults_deduplicated.labels(machine_id=metric.machine_id).inc()
            return None

        # Check if fault is already active
        active_fault = self.active_faults.get(signature)
        if active_fault:
            # Increment occurrence count
            active_fault.occurrence_count += 1
            active_fault.last_occurrence = metric.timestamp_utc
            self.logger.debug(
                f"Fault reoccurred: {fault_code} on {metric.machine_id} "
                f"(count: {active_fault.occurrence_count})"
            )
            return active_fault

        # Create new fault
        fault = Fault(
            fault_id=self._generate_fault_id(metric.machine_id, fault_code, metric.timestamp_utc),
            machine_id=metric.machine_id,
            line_id=metric.line_id,
            site_id=metric.site_id,
            fault_code=fault_code,
            fault_description=self._get_fault_description(fault_code),
            severity=self._get_fault_severity(fault_code),
            start_time=metric.timestamp_utc,
            source_node=metric.source_node,
            source_device=metric.source_device,
            metadata=metric.metadata
        )

        # Store as active
        self.active_faults[signature] = fault
        self.recent_signatures[signature] = metric.timestamp_utc

        # Update metrics
        self.faults_created.labels(
            machine_id=metric.machine_id,
            severity=fault.severity.name
        ).inc()

        self._update_active_fault_gauges()

        self.logger.info(
            f"Fault started: {fault_code} on {metric.machine_id} "
            f"(severity: {fault.severity.name})"
        )

        return fault

    async def _handle_fault_active(self, metric: NormalizedMetric) -> Optional[Fault]:
        """Handle fault active flag (fault end)"""
        is_active = bool(metric.value)

        if is_active:
            # Fault is active - this is typically handled by fault.code
            return None
        else:
            # Fault cleared - resolve all active faults for this machine
            resolved_faults = []

            for signature, fault in list(self.active_faults.items()):
                if fault.machine_id == metric.machine_id and fault.state == FaultState.ACTIVE:
                    fault.end_time = metric.timestamp_utc
                    fault.state = FaultState.RESOLVED

                    # Calculate duration
                    duration = (fault.end_time - fault.start_time).total_seconds()

                    # Update metrics
                    self.faults_resolved.labels(
                        machine_id=fault.machine_id,
                        severity=fault.severity.name
                    ).inc()

                    self.fault_duration.labels(
                        machine_id=fault.machine_id,
                        severity=fault.severity.name
                    ).observe(duration)

                    self.logger.info(
                        f"Fault resolved: {fault.fault_code} on {fault.machine_id} "
                        f"(duration: {duration:.1f}s)"
                    )

                    # Remove from active faults
                    del self.active_faults[signature]
                    resolved_faults.append(fault)

            self._update_active_fault_gauges()

            return resolved_faults[0] if resolved_faults else None

    async def _handle_fault_severity(self, metric: NormalizedMetric) -> Optional[Fault]:
        """Handle fault severity updates"""
        # Find active fault for this machine
        for fault in self.active_faults.values():
            if fault.machine_id == metric.machine_id and fault.state == FaultState.ACTIVE:
                # Update severity
                try:
                    new_severity = FaultSeverity(int(metric.value))
                    if new_severity != fault.severity:
                        old_severity = fault.severity
                        fault.severity = new_severity
                        self.logger.info(
                            f"Fault severity updated: {fault.fault_code} on {metric.machine_id} "
                            f"{old_severity.name} -> {new_severity.name}"
                        )
                        return fault
                except ValueError:
                    self.logger.warning(f"Invalid severity value: {metric.value}")

        return None

    def acknowledge_fault(self, fault_id: str, acknowledged_by: str) -> Optional[Fault]:
        """Acknowledge a fault"""
        for fault in self.active_faults.values():
            if fault.fault_id == fault_id:
                fault.state = FaultState.ACKNOWLEDGED
                fault.acknowledged_by = acknowledged_by
                fault.acknowledged_at = datetime.now()

                self.logger.info(
                    f"Fault acknowledged: {fault.fault_code} on {fault.machine_id} "
                    f"by {acknowledged_by}"
                )

                return fault

        return None

    def _create_signature(self, machine_id: str, fault_code: str, timestamp: datetime) -> str:
        """Create a unique signature for deduplication"""
        # Include timestamp rounded to merge window for grouping
        window_timestamp = int(timestamp.timestamp() / self.merge_window_seconds)
        return f"{machine_id}:{fault_code}:{window_timestamp}"

    def _is_duplicate(self, signature: str) -> bool:
        """Check if fault signature was recently seen"""
        if signature not in self.recent_signatures:
            return False

        last_seen = self.recent_signatures[signature]
        elapsed = (datetime.now() - last_seen).total_seconds()

        return elapsed < self.dedup_window_seconds

    def _generate_fault_id(self, machine_id: str, fault_code: str, timestamp: datetime) -> str:
        """Generate unique fault ID"""
        return f"{machine_id}_{fault_code}_{int(timestamp.timestamp() * 1000)}"

    def _get_fault_description(self, fault_code: str) -> str:
        """Get human-readable fault description"""
        # This would typically lookup from a fault code database
        # For now, return fault code itself
        fault_descriptions = {
            '1001': 'Emergency Stop Activated',
            '1002': 'Safety Gate Open',
            '2001': 'Motor Overload',
            '2002': 'Sensor Fault',
            '3001': 'Material Jam',
            '3002': 'Low Air Pressure',
            '4001': 'Communication Error',
            '4002': 'PLC Fault',
        }

        return fault_descriptions.get(fault_code, f"Fault Code {fault_code}")

    def _get_fault_severity(self, fault_code: str) -> FaultSeverity:
        """Determine fault severity from fault code"""
        # This would typically lookup from configuration
        # For now, use simple rules based on code ranges

        try:
            code_int = int(fault_code)

            if code_int < 1000:
                return FaultSeverity.INFO
            elif code_int < 2000:
                return FaultSeverity.CRITICAL
            elif code_int < 3000:
                return FaultSeverity.HIGH
            elif code_int < 4000:
                return FaultSeverity.MEDIUM
            else:
                return FaultSeverity.LOW

        except ValueError:
            return FaultSeverity.MEDIUM

    def _update_active_fault_gauges(self):
        """Update Prometheus gauges for active faults"""
        # Count active faults by machine and severity
        counts: Dict[tuple, int] = {}

        for fault in self.active_faults.values():
            if fault.state == FaultState.ACTIVE:
                key = (fault.machine_id, fault.severity.name)
                counts[key] = counts.get(key, 0) + 1

        # Update gauges
        for (machine_id, severity), count in counts.items():
            self.faults_active.labels(machine_id=machine_id, severity=severity).set(count)

    async def cleanup_resolved_faults(self, retention_hours: int = 24):
        """Clean up old resolved faults from memory"""
        cutoff_time = datetime.now() - timedelta(hours=retention_hours)

        removed_count = 0
        for signature, fault in list(self.active_faults.items()):
            if (fault.state == FaultState.RESOLVED and
                fault.end_time and
                fault.end_time < cutoff_time):

                del self.active_faults[signature]
                removed_count += 1

        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} resolved faults")

    async def cleanup_recent_signatures(self):
        """Clean up expired signature cache"""
        cutoff_time = datetime.now() - timedelta(seconds=self.dedup_window_seconds)

        removed_count = 0
        for signature, timestamp in list(self.recent_signatures.items()):
            if timestamp < cutoff_time:
                del self.recent_signatures[signature]
                removed_count += 1

        if removed_count > 0:
            self.logger.debug(f"Cleaned up {removed_count} signature cache entries")

    def get_active_faults(self, machine_id: Optional[str] = None) -> List[Fault]:
        """Get list of active faults, optionally filtered by machine"""
        faults = [
            f for f in self.active_faults.values()
            if f.state == FaultState.ACTIVE
        ]

        if machine_id:
            faults = [f for f in faults if f.machine_id == machine_id]

        return sorted(faults, key=lambda f: (f.severity.value, f.start_time))

    def get_statistics(self) -> Dict[str, Any]:
        """Get fault state machine statistics"""
        active_count = sum(
            1 for f in self.active_faults.values()
            if f.state == FaultState.ACTIVE
        )

        severity_counts = {}
        for fault in self.active_faults.values():
            if fault.state == FaultState.ACTIVE:
                severity_counts[fault.severity.name] = severity_counts.get(fault.severity.name, 0) + 1

        return {
            'active_faults': active_count,
            'total_tracked_faults': len(self.active_faults),
            'severity_distribution': severity_counts,
            'recent_signatures_cached': len(self.recent_signatures),
            'machines_with_faults': len(set(f.machine_id for f in self.active_faults.values())),
        }
