"""
Sparkplug B Data Processor
Maps Sparkplug B telemetry data to OEE SQL Server models
Handles real-time ingestion and transformation for production analytics
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from django.db import transaction, connections
from django.utils import timezone as django_timezone
from django.core.exceptions import ObjectDoesNotExist

from ..sql_server_models import (
    Machine, ProductionLine, Area, Plant,
    MachineEvent, ProductionCycle, DowntimeEvent, QualityEvent,
    OEERollupHourly, OEERollupShift, OEERollupDaily
)
from .models import (
    SparkplugNode, SparkplugDevice, SparkplugMetric, 
    SparkplugMetricHistory, SparkplugEventRaw
)


class OEEMetricType(Enum):
    """OEE-specific metric types for mapping Sparkplug data"""
    CYCLE_START = "CYCLE_START"
    CYCLE_END = "CYCLE_END"
    CYCLE_TIME = "CYCLE_TIME"
    PART_COUNT_GOOD = "PART_COUNT_GOOD"
    PART_COUNT_SCRAP = "PART_COUNT_SCRAP"
    PART_COUNT_REWORK = "PART_COUNT_REWORK"
    QUALITY_FLAG = "QUALITY_FLAG"
    DOWNTIME_START = "DOWNTIME_START"
    DOWNTIME_END = "DOWNTIME_END"
    DOWNTIME_REASON = "DOWNTIME_REASON"
    MACHINE_STATUS = "MACHINE_STATUS"
    PRODUCTION_RATE = "PRODUCTION_RATE"
    TEMPERATURE = "TEMPERATURE"
    PRESSURE = "PRESSURE"
    VIBRATION = "VIBRATION"
    SPEED = "SPEED"
    ALARM_ACTIVE = "ALARM_ACTIVE"
    OPERATOR_ID = "OPERATOR_ID"
    RECIPE_ID = "RECIPE_ID"
    SHIFT_ID = "SHIFT_ID"


@dataclass
class MetricMapping:
    """Configuration for mapping Sparkplug metrics to OEE data"""
    sparkplug_metric_name: str
    oee_metric_type: OEEMetricType
    machine_id: str
    data_transformation: Optional[str] = None  # Python expression for data transformation
    threshold_value: Optional[float] = None    # For trigger-based events
    scaling_factor: float = 1.0
    scaling_offset: float = 0.0
    quality_threshold: int = 192  # Minimum Sparkplug quality


@dataclass
class CycleState:
    """Tracks production cycle state for a machine"""
    machine_id: str
    cycle_start_time: Optional[datetime] = None
    current_cycle_id: Optional[int] = None
    good_parts: int = 0
    scrap_parts: int = 0
    rework_parts: int = 0
    last_cycle_time: Optional[float] = None
    target_cycle_time: Optional[float] = None
    current_recipe_id: Optional[str] = None
    current_operator_id: Optional[str] = None
    current_shift_id: Optional[str] = None


class SparkplugDataProcessor:
    """
    Processes Sparkplug B telemetry data and maps it to OEE models
    Handles real-time data transformation and persistence
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.metric_mappings: Dict[str, List[MetricMapping]] = {}
        self.cycle_states: Dict[str, CycleState] = {}
        self.last_values: Dict[str, Any] = {}  # For edge detection
        
        # Performance tracking
        self.processed_metrics = 0
        self.created_events = 0
        self.created_cycles = 0
        self.processing_errors = 0
        
    def add_metric_mapping(self, mapping: MetricMapping):
        """Add a metric mapping configuration"""
        key = f"{mapping.machine_id}:{mapping.sparkplug_metric_name}"
        if key not in self.metric_mappings:
            self.metric_mappings[key] = []
        self.metric_mappings[key].append(mapping)
        
        self.logger.info(f"Added metric mapping: {mapping.sparkplug_metric_name} -> {mapping.oee_metric_type.value}")
    
    def load_mappings_from_config(self, config: Dict[str, Any]):
        """Load metric mappings from configuration"""
        for machine_config in config.get('machines', []):
            machine_id = machine_config['machine_id']
            
            for metric_config in machine_config.get('metrics', []):
                mapping = MetricMapping(
                    sparkplug_metric_name=metric_config['sparkplug_name'],
                    oee_metric_type=OEEMetricType(metric_config['oee_type']),
                    machine_id=machine_id,
                    data_transformation=metric_config.get('transformation'),
                    threshold_value=metric_config.get('threshold'),
                    scaling_factor=metric_config.get('scaling_factor', 1.0),
                    scaling_offset=metric_config.get('scaling_offset', 0.0),
                    quality_threshold=metric_config.get('quality_threshold', 192)
                )
                self.add_metric_mapping(mapping)
    
    async def process_metric_history(self, metric_history: SparkplugMetricHistory):
        """Process a single metric history entry"""
        try:
            # Get metric definition
            metric = metric_history.metric
            
            # Check if this metric has mappings
            device_machine_id = self._get_machine_id_for_metric(metric)
            if not device_machine_id:
                return  # No mapping found
            
            mapping_key = f"{device_machine_id}:{metric.name}"
            mappings = self.metric_mappings.get(mapping_key, [])
            
            if not mappings:
                return  # No mappings for this metric
            
            # Parse metric value
            try:
                raw_value = json.loads(metric_history.value_json)
                transformed_value = self._transform_value(raw_value, mappings[0])
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.error(f"Invalid metric value for {metric.name}: {e}")
                return
            
            # Check quality threshold
            if metric_history.quality < mappings[0].quality_threshold:
                self.logger.warning(f"Low quality metric ignored: {metric.name} (quality: {metric_history.quality})")
                return
            
            # Process each mapping for this metric
            for mapping in mappings:
                await self._process_metric_mapping(
                    mapping, 
                    transformed_value, 
                    metric_history.timestamp_utc,
                    metric_history
                )
            
            self.processed_metrics += 1
            
        except Exception as e:
            self.processing_errors += 1
            self.logger.error(f"Error processing metric history {metric_history.history_id}: {e}")
    
    async def _process_metric_mapping(self, mapping: MetricMapping, value: Any, 
                                    timestamp: datetime, metric_history: SparkplugMetricHistory):
        """Process a specific metric mapping"""
        try:
            machine_id = mapping.machine_id
            metric_type = mapping.oee_metric_type
            
            # Get or create cycle state for machine
            if machine_id not in self.cycle_states:
                self.cycle_states[machine_id] = CycleState(machine_id=machine_id)
            
            cycle_state = self.cycle_states[machine_id]
            
            # Process based on metric type
            if metric_type == OEEMetricType.CYCLE_START:
                await self._handle_cycle_start(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.CYCLE_END:
                await self._handle_cycle_end(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.CYCLE_TIME:
                await self._handle_cycle_time(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.PART_COUNT_GOOD:
                await self._handle_part_count_good(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.PART_COUNT_SCRAP:
                await self._handle_part_count_scrap(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.PART_COUNT_REWORK:
                await self._handle_part_count_rework(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.QUALITY_FLAG:
                await self._handle_quality_flag(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.DOWNTIME_START:
                await self._handle_downtime_start(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.DOWNTIME_END:
                await self._handle_downtime_end(cycle_state, value, timestamp, mapping)
            elif metric_type == OEEMetricType.MACHINE_STATUS:
                await self._handle_machine_status(cycle_state, value, timestamp, mapping)
            else:
                # Handle as generic machine event
                await self._handle_generic_metric(cycle_state, value, timestamp, mapping)
            
            # Always create a machine event for traceability
            await self._create_machine_event(machine_id, metric_type.value, value, timestamp, metric_history)
            
        except Exception as e:
            self.logger.error(f"Error processing mapping for {mapping.oee_metric_type.value}: {e}")
    
    async def _handle_cycle_start(self, cycle_state: CycleState, value: Any, 
                                timestamp: datetime, mapping: MetricMapping):
        """Handle cycle start event"""
        # Check for edge trigger (false -> true or 0 -> 1)
        last_key = f"{cycle_state.machine_id}:cycle_start"
        last_value = self.last_values.get(last_key, False)
        
        current_value = bool(value)
        self.last_values[last_key] = current_value
        
        if not last_value and current_value:  # Rising edge
            # Start new production cycle
            try:
                with transaction.atomic():
                    # Get machine
                    machine = await self._get_machine(cycle_state.machine_id)
                    
                    # Create new production cycle
                    cycle = ProductionCycle.objects.create(
                        machine=machine,
                        line=machine.line,
                        start_timestamp_utc=timestamp,
                        target_cycle_time_seconds=cycle_state.target_cycle_time,
                        cycle_status='RUNNING',
                        operator_id=cycle_state.current_operator_id,
                        shift_id=cycle_state.current_shift_id,
                    )
                    
                    # Update cycle state
                    cycle_state.cycle_start_time = timestamp
                    cycle_state.current_cycle_id = cycle.cycle_id
                    cycle_state.good_parts = 0
                    cycle_state.scrap_parts = 0
                    cycle_state.rework_parts = 0
                    
                    self.created_cycles += 1
                    self.logger.debug(f"Started cycle {cycle.cycle_id} for machine {cycle_state.machine_id}")
                    
            except Exception as e:
                self.logger.error(f"Failed to create production cycle: {e}")
    
    async def _handle_cycle_end(self, cycle_state: CycleState, value: Any, 
                              timestamp: datetime, mapping: MetricMapping):
        """Handle cycle end event"""
        last_key = f"{cycle_state.machine_id}:cycle_end"
        last_value = self.last_values.get(last_key, False)
        
        current_value = bool(value)
        self.last_values[last_key] = current_value
        
        if not last_value and current_value:  # Rising edge
            # Complete current production cycle
            if cycle_state.current_cycle_id:
                try:
                    with transaction.atomic():
                        cycle = ProductionCycle.objects.get(cycle_id=cycle_state.current_cycle_id)
                        
                        # Calculate cycle time
                        if cycle_state.cycle_start_time:
                            cycle_time = (timestamp - cycle_state.cycle_start_time).total_seconds()
                        else:
                            cycle_time = cycle_state.last_cycle_time
                        
                        # Update cycle
                        cycle.end_timestamp_utc = timestamp
                        cycle.cycle_time_seconds = Decimal(str(cycle_time)) if cycle_time else None
                        cycle.good_parts_count = cycle_state.good_parts
                        cycle.scrap_parts_count = cycle_state.scrap_parts
                        cycle.rework_parts_count = cycle_state.rework_parts
                        cycle.cycle_status = 'COMPLETED'
                        cycle.save()
                        
                        # Reset cycle state
                        cycle_state.current_cycle_id = None
                        cycle_state.cycle_start_time = None
                        
                        self.logger.debug(f"Completed cycle {cycle.cycle_id} for machine {cycle_state.machine_id}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to complete production cycle: {e}")
    
    async def _handle_cycle_time(self, cycle_state: CycleState, value: Any, 
                               timestamp: datetime, mapping: MetricMapping):
        """Handle cycle time measurement"""
        try:
            cycle_time = float(value)
            cycle_state.last_cycle_time = cycle_time
            
            # If we have an active cycle, update it
            if cycle_state.current_cycle_id:
                cycle = ProductionCycle.objects.get(cycle_id=cycle_state.current_cycle_id)
                cycle.cycle_time_seconds = Decimal(str(cycle_time))
                cycle.save()
                
        except (ValueError, ObjectDoesNotExist):
            pass
    
    async def _handle_part_count_good(self, cycle_state: CycleState, value: Any, 
                                    timestamp: datetime, mapping: MetricMapping):
        """Handle good parts count"""
        try:
            count = int(value)
            cycle_state.good_parts = count
            
            # Update current cycle if active
            if cycle_state.current_cycle_id:
                cycle = ProductionCycle.objects.get(cycle_id=cycle_state.current_cycle_id)
                cycle.good_parts_count = count
                cycle.save()
                
        except (ValueError, ObjectDoesNotExist):
            pass
    
    async def _handle_part_count_scrap(self, cycle_state: CycleState, value: Any, 
                                     timestamp: datetime, mapping: MetricMapping):
        """Handle scrap parts count"""
        try:
            count = int(value)
            cycle_state.scrap_parts = count
            
            # Update current cycle if active
            if cycle_state.current_cycle_id:
                cycle = ProductionCycle.objects.get(cycle_id=cycle_state.current_cycle_id)
                cycle.scrap_parts_count = count
                cycle.save()
                
            # Create quality event for scrap
            if count > 0:
                await self._create_quality_event(cycle_state.machine_id, count, 0, timestamp)
                
        except (ValueError, ObjectDoesNotExist):
            pass
    
    async def _handle_part_count_rework(self, cycle_state: CycleState, value: Any, 
                                      timestamp: datetime, mapping: MetricMapping):
        """Handle rework parts count"""
        try:
            count = int(value)
            cycle_state.rework_parts = count
            
            # Update current cycle if active
            if cycle_state.current_cycle_id:
                cycle = ProductionCycle.objects.get(cycle_id=cycle_state.current_cycle_id)
                cycle.rework_parts_count = count
                cycle.save()
                
        except (ValueError, ObjectDoesNotExist):
            pass
    
    async def _handle_quality_flag(self, cycle_state: CycleState, value: Any, 
                                 timestamp: datetime, mapping: MetricMapping):
        """Handle quality flag (good/bad part indication)"""
        try:
            is_good = bool(value)
            
            if is_good:
                cycle_state.good_parts += 1
            else:
                cycle_state.scrap_parts += 1
                # Create quality event
                await self._create_quality_event(cycle_state.machine_id, 1, 0, timestamp)
            
            # Update current cycle if active
            if cycle_state.current_cycle_id:
                cycle = ProductionCycle.objects.get(cycle_id=cycle_state.current_cycle_id)
                cycle.good_parts_count = cycle_state.good_parts
                cycle.scrap_parts_count = cycle_state.scrap_parts
                cycle.save()
                
        except ObjectDoesNotExist:
            pass
    
    async def _handle_downtime_start(self, cycle_state: CycleState, value: Any, 
                                   timestamp: datetime, mapping: MetricMapping):
        """Handle downtime start event"""
        last_key = f"{cycle_state.machine_id}:downtime"
        last_value = self.last_values.get(last_key, False)
        
        current_value = bool(value)
        self.last_values[last_key] = current_value
        
        if not last_value and current_value:  # Rising edge - downtime started
            try:
                machine = await self._get_machine(cycle_state.machine_id)
                
                # Create downtime event
                DowntimeEvent.objects.create(
                    machine=machine,
                    line=machine.line,
                    start_timestamp_utc=timestamp,
                    reason_code_id='UNKNOWN',  # Default reason, should be updated
                    is_planned=False,
                    shift_id=cycle_state.current_shift_id,
                )
                
                self.logger.debug(f"Started downtime for machine {cycle_state.machine_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to create downtime event: {e}")
    
    async def _handle_downtime_end(self, cycle_state: CycleState, value: Any, 
                                 timestamp: datetime, mapping: MetricMapping):
        """Handle downtime end event"""
        last_key = f"{cycle_state.machine_id}:downtime"
        last_value = self.last_values.get(last_key, True)
        
        current_value = bool(value)
        self.last_values[last_key] = current_value
        
        if last_value and not current_value:  # Falling edge - downtime ended
            try:
                # Find the most recent open downtime event
                machine = await self._get_machine(cycle_state.machine_id)
                downtime = DowntimeEvent.objects.filter(
                    machine=machine,
                    end_timestamp_utc__isnull=True
                ).order_by('-start_timestamp_utc').first()
                
                if downtime:
                    # Calculate duration
                    duration = (timestamp - downtime.start_timestamp_utc).total_seconds() / 60.0
                    
                    # Update downtime event
                    downtime.end_timestamp_utc = timestamp
                    downtime.duration_minutes = Decimal(str(duration))
                    downtime.save()
                    
                    self.logger.debug(f"Ended downtime for machine {cycle_state.machine_id}, duration: {duration:.1f} min")
                
            except Exception as e:
                self.logger.error(f"Failed to complete downtime event: {e}")
    
    async def _handle_machine_status(self, cycle_state: CycleState, value: Any, 
                                   timestamp: datetime, mapping: MetricMapping):
        """Handle machine status changes"""
        # This could trigger various actions based on status
        # For now, just log it
        self.logger.debug(f"Machine {cycle_state.machine_id} status: {value}")
    
    async def _handle_generic_metric(self, cycle_state: CycleState, value: Any, 
                                   timestamp: datetime, mapping: MetricMapping):
        """Handle generic metrics (temperature, pressure, etc.)"""
        # Create machine event for telemetry data
        # This provides a data trail for all metrics
        pass  # Machine event is created in the calling function
    
    async def _create_machine_event(self, machine_id: str, event_type: str, 
                                  value: Any, timestamp: datetime, 
                                  metric_history: SparkplugMetricHistory):
        """Create a machine event record"""
        try:
            machine = await self._get_machine(machine_id)
            
            # Convert value to appropriate format
            if isinstance(value, (int, float)):
                event_value = Decimal(str(value))
                event_text = None
            else:
                event_value = None
                event_text = str(value)[:500]  # Truncate to fit field
            
            MachineEvent.objects.create(
                machine=machine,
                timestamp_utc=timestamp,
                event_type=event_type,
                event_value=event_value,
                event_text=event_text,
                source_system='SPARKPLUG',
                quality_score=min(100, metric_history.quality * 100 // 255),  # Convert to 0-100 scale
                payload_json=json.dumps({
                    'sparkplug_metric_id': metric_history.metric.metric_id,
                    'sparkplug_sequence': metric_history.sequence_number,
                    'sparkplug_quality': metric_history.quality,
                })
            )
            
            self.created_events += 1
            
        except Exception as e:
            self.logger.error(f"Failed to create machine event: {e}")
    
    async def _create_quality_event(self, machine_id: str, parts_failed: int, 
                                  parts_passed: int, timestamp: datetime):
        """Create a quality event record"""
        try:
            machine = await self._get_machine(machine_id)
            
            QualityEvent.objects.create(
                machine=machine,
                line=machine.line,
                timestamp_utc=timestamp,
                parts_inspected=parts_failed + parts_passed,
                parts_passed=parts_passed,
                parts_failed=parts_failed,
                inspection_method='SPARKPLUG',
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create quality event: {e}")
    
    async def _get_machine(self, machine_id: str) -> Machine:
        """Get machine object, with caching"""
        # TODO: Implement caching for performance
        return Machine.objects.get(machine_id=machine_id)
    
    def _get_machine_id_for_metric(self, metric: SparkplugMetric) -> Optional[str]:
        """Extract machine ID from metric's device mapping"""
        # Check if device is mapped to a machine
        if metric.device and metric.device.machine:
            return metric.device.machine.machine_id
        
        # Check if node has device mappings
        if metric.node:
            # Look for any device on this node that has a machine mapping
            for device in metric.node.devices.filter(machine__isnull=False):
                return device.machine.machine_id
        
        return None
    
    def _transform_value(self, raw_value: Any, mapping: MetricMapping) -> Any:
        """Transform raw value according to mapping configuration"""
        if raw_value is None:
            return None
        
        try:
            # Apply scaling
            if isinstance(raw_value, (int, float)):
                value = (raw_value * mapping.scaling_factor) + mapping.scaling_offset
            else:
                value = raw_value
            
            # Apply custom transformation if specified
            if mapping.data_transformation:
                # Create safe evaluation context
                context = {
                    'value': value,
                    'raw_value': raw_value,
                    'abs': abs,
                    'min': min,
                    'max': max,
                    'round': round,
                }
                
                try:
                    value = eval(mapping.data_transformation, {"__builtins__": {}}, context)
                except Exception as e:
                    self.logger.warning(f"Transformation failed for {mapping.sparkplug_metric_name}: {e}")
            
            return value
            
        except Exception as e:
            self.logger.error(f"Value transformation failed: {e}")
            return raw_value
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            'processed_metrics': self.processed_metrics,
            'created_events': self.created_events,
            'created_cycles': self.created_cycles,
            'processing_errors': self.processing_errors,
            'active_cycles': len([cs for cs in self.cycle_states.values() if cs.current_cycle_id]),
            'tracked_machines': len(self.cycle_states),
            'metric_mappings': len(self.metric_mappings),
        }
    
    def reset_statistics(self):
        """Reset processing statistics"""
        self.processed_metrics = 0
        self.created_events = 0
        self.created_cycles = 0
        self.processing_errors = 0