"""
ControlLogix PLC Simulator
Emulates Allen-Bradley ControlLogix PLC with realistic OEE production data
Compatible with pycomm3 LogixDriver interface
"""

import asyncio
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import math


@dataclass
class Tag:
    """PLC Tag definition"""
    name: str
    value: Any
    data_type: str
    description: str = ""

    def to_dict(self):
        return {
            'tag_name': self.name,
            'value': self.value,
            'data_type': self.data_type,
            'description': self.description
        }


@dataclass
class ReadResult:
    """Result of a tag read operation"""
    tag: str
    value: Any
    error: Optional[str] = None


class ControlLogixSimulator:
    """
    Simulates Allen-Bradley ControlLogix PLC with realistic production data

    Provides OEE metrics for multiple production lines:
    - Production counts (cyclic incrementing)
    - Machine status (running/stopped/faulted states)
    - OEE, Availability, Performance, Quality percentages
    - Downtime event tracking
    - Part counts and quality metrics
    """

    def __init__(self, plc_ip: str = "192.168.1.10", slot: int = 0):
        self.ip_address = plc_ip
        self.slot = slot
        self.connected = False

        # Production lines to simulate
        self.production_lines = ["LINE-001", "LINE-002", "LINE-003"]

        # Initialize tag database
        self.tags: Dict[str, Tag] = {}
        self._initialize_tags()

        # Simulation parameters
        self.start_time = time.time()
        self.production_rate = 60  # parts per minute at 100% performance
        self.defect_rate = 0.02  # 2% defect rate
        self.random_fault_probability = 0.001  # 0.1% chance of fault per update

        # Runtime state
        self.running_lines = {line: True for line in self.production_lines}
        self.fault_lines = {line: False for line in self.production_lines}

        # Start background simulation
        self._simulation_task = None

    def _initialize_tags(self):
        """Initialize all PLC tags with default values"""

        # System tags
        self.tags['System_Time'] = Tag('System_Time', int(time.time()), 'DINT', 'System timestamp')
        self.tags['System_Status'] = Tag('System_Status', 1, 'INT', 'System status: 1=Running, 0=Stopped')
        self.tags['CPU_Load'] = Tag('CPU_Load', 25.5, 'REAL', 'CPU load percentage')

        # Create tags for each production line
        for line_id in self.production_lines:
            prefix = f"Line_{line_id.replace('-', '_')}"

            # Production counters
            self.tags[f'{prefix}_ProductionCount'] = Tag(
                f'{prefix}_ProductionCount', 0, 'DINT',
                f'{line_id} total production count'
            )
            self.tags[f'{prefix}_TargetCount'] = Tag(
                f'{prefix}_TargetCount', 1500, 'DINT',
                f'{line_id} shift target count'
            )
            self.tags[f'{prefix}_GoodCount'] = Tag(
                f'{prefix}_GoodCount', 0, 'DINT',
                f'{line_id} good parts count'
            )
            self.tags[f'{prefix}_RejectCount'] = Tag(
                f'{prefix}_RejectCount', 0, 'DINT',
                f'{line_id} rejected parts count'
            )

            # Machine status
            self.tags[f'{prefix}_Running'] = Tag(
                f'{prefix}_Running', True, 'BOOL',
                f'{line_id} machine running status'
            )
            self.tags[f'{prefix}_Faulted'] = Tag(
                f'{prefix}_Faulted', False, 'BOOL',
                f'{line_id} machine fault status'
            )
            self.tags[f'{prefix}_Stopped'] = Tag(
                f'{prefix}_Stopped', False, 'BOOL',
                f'{line_id} machine stopped status'
            )

            # OEE metrics (0-100%)
            self.tags[f'{prefix}_OEE'] = Tag(
                f'{prefix}_OEE', 85.0, 'REAL',
                f'{line_id} Overall Equipment Effectiveness'
            )
            self.tags[f'{prefix}_Availability'] = Tag(
                f'{prefix}_Availability', 92.0, 'REAL',
                f'{line_id} Availability percentage'
            )
            self.tags[f'{prefix}_Performance'] = Tag(
                f'{prefix}_Performance', 95.0, 'REAL',
                f'{line_id} Performance percentage'
            )
            self.tags[f'{prefix}_Quality'] = Tag(
                f'{prefix}_Quality', 97.5, 'REAL',
                f'{line_id} Quality percentage'
            )

            # Cycle time
            self.tags[f'{prefix}_CycleTime'] = Tag(
                f'{prefix}_CycleTime', 1.0, 'REAL',
                f'{line_id} current cycle time (seconds)'
            )
            self.tags[f'{prefix}_IdealCycleTime'] = Tag(
                f'{prefix}_IdealCycleTime', 1.0, 'REAL',
                f'{line_id} ideal cycle time (seconds)'
            )

            # Downtime
            self.tags[f'{prefix}_DowntimeMinutes'] = Tag(
                f'{prefix}_DowntimeMinutes', 0.0, 'REAL',
                f'{line_id} downtime in minutes'
            )
            self.tags[f'{prefix}_LastFaultCode'] = Tag(
                f'{prefix}_LastFaultCode', 0, 'INT',
                f'{line_id} last fault code'
            )

    async def connect(self):
        """Simulate PLC connection"""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.connected = True

        # Start simulation task
        if self._simulation_task is None:
            self._simulation_task = asyncio.create_task(self._simulate_production())

        return True

    async def disconnect(self):
        """Disconnect from simulated PLC"""
        self.connected = False

        # Stop simulation task
        if self._simulation_task:
            self._simulation_task.cancel()
            try:
                await self._simulation_task
            except asyncio.CancelledError:
                pass
            self._simulation_task = None

    def read(self, *tag_names: str) -> List[ReadResult]:
        """
        Read one or more tags from the PLC
        Compatible with pycomm3 interface: driver.read(*tags)
        """
        if not self.connected:
            return [ReadResult(tag, None, "Not connected") for tag in tag_names]

        results = []
        for tag_name in tag_names:
            if tag_name in self.tags:
                tag = self.tags[tag_name]
                results.append(ReadResult(tag_name, tag.value, None))
            else:
                results.append(ReadResult(tag_name, None, f"Tag '{tag_name}' not found"))

        # If single tag, return single result; otherwise return list
        if len(results) == 1:
            return results[0]
        return results

    def write(self, tag_name: str, value: Any) -> ReadResult:
        """Write a value to a tag"""
        if not self.connected:
            return ReadResult(tag_name, None, "Not connected")

        if tag_name in self.tags:
            tag = self.tags[tag_name]
            # Convert value to appropriate type
            try:
                if tag.data_type == 'BOOL':
                    tag.value = bool(value)
                elif tag.data_type in ['INT', 'DINT', 'LINT']:
                    tag.value = int(value)
                elif tag.data_type in ['REAL', 'LREAL']:
                    tag.value = float(value)
                elif tag.data_type == 'STRING':
                    tag.value = str(value)
                else:
                    tag.value = value

                return ReadResult(tag_name, tag.value, None)
            except (ValueError, TypeError) as e:
                return ReadResult(tag_name, None, f"Type conversion error: {e}")
        else:
            return ReadResult(tag_name, None, f"Tag '{tag_name}' not found")

    def get_tag_list(self) -> List[Dict]:
        """Get list of all available tags"""
        return [tag.to_dict() for tag in self.tags.values()]

    @property
    def info(self) -> Dict[str, Any]:
        """Get PLC info (compatible with pycomm3)"""
        return {
            'vendor': 'Rockwell Automation',
            'product_type': 'Programmable Logic Controller',
            'product_code': 14,
            'version': '33.11',
            'revision': '33.11',
            'serial': 'SIMULATOR123',
            'product_name': 'ControlLogix Simulator',
            'state': 'Run' if self.connected else 'Disconnected',
            'ip_address': self.ip_address,
            'slot': self.slot
        }

    async def _simulate_production(self):
        """Background task to simulate production data changes"""
        print(f"[ControlLogix Simulator] Production simulation started for {len(self.production_lines)} lines")

        last_update = time.time()

        try:
            while True:
                await asyncio.sleep(1.0)  # Update every second

                current_time = time.time()
                elapsed = current_time - last_update
                last_update = current_time

                # Update system tags
                self.tags['System_Time'].value = int(current_time)
                self.tags['CPU_Load'].value = 20.0 + random.uniform(-5, 5)

                # Update each production line
                for line_id in self.production_lines:
                    self._update_line_production(line_id, elapsed)

        except asyncio.CancelledError:
            print("[ControlLogix Simulator] Production simulation stopped")
            raise

    def _update_line_production(self, line_id: str, elapsed_seconds: float):
        """Update production metrics for a single line"""
        prefix = f"Line_{line_id.replace('-', '_')}"

        # Check for random faults
        if random.random() < self.random_fault_probability:
            if not self.fault_lines[line_id]:
                self._trigger_fault(line_id)

        # Get current state
        is_running = self.running_lines[line_id]
        is_faulted = self.fault_lines[line_id]

        # Update status tags
        self.tags[f'{prefix}_Running'].value = is_running and not is_faulted
        self.tags[f'{prefix}_Faulted'].value = is_faulted
        self.tags[f'{prefix}_Stopped'].value = not is_running

        # If running and not faulted, increment production
        if is_running and not is_faulted:
            # Calculate parts produced this interval
            parts_per_second = self.production_rate / 60.0
            performance_factor = random.uniform(0.90, 1.05)  # 90-105% of ideal
            parts_produced = int(parts_per_second * elapsed_seconds * performance_factor)

            if parts_produced > 0:
                # Update production count
                production_count_tag = self.tags[f'{prefix}_ProductionCount']
                production_count_tag.value += parts_produced

                # Simulate quality (some parts are defects)
                good_parts = sum(1 for _ in range(parts_produced) if random.random() > self.defect_rate)
                reject_parts = parts_produced - good_parts

                self.tags[f'{prefix}_GoodCount'].value += good_parts
                self.tags[f'{prefix}_RejectCount'].value += reject_parts

                # Update cycle time
                actual_cycle_time = 1.0 / (parts_per_second * performance_factor)
                self.tags[f'{prefix}_CycleTime'].value = round(actual_cycle_time, 2)

                # Calculate and update OEE metrics
                self._update_oee_metrics(line_id)

        elif is_faulted:
            # Increment downtime
            downtime_tag = self.tags[f'{prefix}_DowntimeMinutes']
            downtime_tag.value += elapsed_seconds / 60.0

            # Randomly clear fault after some time
            if downtime_tag.value > random.uniform(2.0, 10.0):  # 2-10 minutes
                self._clear_fault(line_id)

    def _update_oee_metrics(self, line_id: str):
        """Calculate and update OEE metrics for a line"""
        prefix = f"Line_{line_id.replace('-', '_')}"

        # Get current values
        production_count = self.tags[f'{prefix}_ProductionCount'].value
        target_count = self.tags[f'{prefix}_TargetCount'].value
        good_count = self.tags[f'{prefix}_GoodCount'].value
        reject_count = self.tags[f'{prefix}_RejectCount'].value
        downtime_minutes = self.tags[f'{prefix}_DowntimeMinutes'].value

        # Calculate availability (uptime / planned production time)
        runtime_minutes = (time.time() - self.start_time) / 60.0
        planned_time = max(runtime_minutes, 1.0)
        uptime = planned_time - downtime_minutes
        availability = (uptime / planned_time) * 100.0
        availability = max(0, min(100, availability))

        # Calculate performance (actual production / target production)
        if target_count > 0:
            performance = (production_count / target_count) * 100.0
            performance = max(0, min(100, performance))
        else:
            performance = 100.0

        # Calculate quality (good parts / total parts)
        total_parts = good_count + reject_count
        if total_parts > 0:
            quality = (good_count / total_parts) * 100.0
        else:
            quality = 100.0

        # Calculate OEE (Availability × Performance × Quality)
        oee = (availability / 100.0) * (performance / 100.0) * (quality / 100.0) * 100.0

        # Update tags
        self.tags[f'{prefix}_Availability'].value = round(availability, 1)
        self.tags[f'{prefix}_Performance'].value = round(performance, 1)
        self.tags[f'{prefix}_Quality'].value = round(quality, 1)
        self.tags[f'{prefix}_OEE'].value = round(oee, 1)

    def _trigger_fault(self, line_id: str):
        """Trigger a fault on a production line"""
        prefix = f"Line_{line_id.replace('-', '_')}"

        self.fault_lines[line_id] = True

        # Set fault code (random fault type)
        fault_codes = [101, 102, 103, 201, 202, 301]  # Various fault types
        fault_code = random.choice(fault_codes)
        self.tags[f'{prefix}_LastFaultCode'].value = fault_code

        print(f"[ControlLogix Simulator] FAULT triggered on {line_id}: Code {fault_code}")

    def _clear_fault(self, line_id: str):
        """Clear a fault and resume production"""
        prefix = f"Line_{line_id.replace('-', '_')}"

        self.fault_lines[line_id] = False
        self.tags[f'{prefix}_LastFaultCode'].value = 0

        print(f"[ControlLogix Simulator] FAULT cleared on {line_id}, resuming production")


# Singleton instance for external access
_simulator_instance: Optional[ControlLogixSimulator] = None


def get_simulator(ip: str = "192.168.1.10", slot: int = 0) -> ControlLogixSimulator:
    """Get or create simulator instance"""
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = ControlLogixSimulator(ip, slot)
    return _simulator_instance


async def main():
    """Test the simulator"""
    sim = get_simulator()

    print("Connecting to simulated PLC...")
    await sim.connect()

    print("\nPLC Info:")
    print(sim.info)

    print("\nAvailable tags:")
    tags = sim.get_tag_list()
    print(f"Total tags: {len(tags)}")
    for tag in tags[:10]:  # Show first 10
        print(f"  {tag['tag_name']}: {tag['value']} ({tag['data_type']})")

    print("\nMonitoring production for 30 seconds...")
    for i in range(6):
        await asyncio.sleep(5)

        print(f"\n--- Update {i+1} ---")
        for line in sim.production_lines:
            prefix = f"Line_{line.replace('-', '_')}"

            # Read multiple tags
            results = sim.read(
                f'{prefix}_ProductionCount',
                f'{prefix}_OEE',
                f'{prefix}_Running',
                f'{prefix}_Faulted'
            )

            print(f"{line}:")
            print(f"  Production: {results[0].value}")
            print(f"  OEE: {results[1].value}%")
            print(f"  Running: {results[2].value}")
            print(f"  Faulted: {results[3].value}")

    print("\nDisconnecting...")
    await sim.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
