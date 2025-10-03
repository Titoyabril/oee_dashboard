"""
Siemens S7 PLC Simulator with OPC UA Server
Emulates Siemens S7-1500 PLC with realistic production data
Exposes data via OPC UA protocol for testing OPC UA clients
"""

import asyncio
import random
import time
from datetime import datetime
from typing import Dict, Any, List
import logging

from asyncua import Server, ua
from asyncua.common.methods import uamethod

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SiemensS7Simulator:
    """
    Simulates Siemens S7-1500 PLC with OPC UA server
    Provides OEE metrics for production lines
    """

    def __init__(self, line_id: str = "SIEMENS-001", port: int = 4840):
        self.line_id = line_id
        self.port = port
        self.server: Server = None

        # Production data
        self.production_count = 0
        self.target_count = 1500
        self.good_count = 0
        self.reject_count = 0
        self.downtime_minutes = 0.0

        # Machine status
        self.running = True
        self.faulted = False
        self.stopped = False

        # OEE metrics
        self.oee = 85.0
        self.availability = 92.0
        self.performance = 95.0
        self.quality = 97.5

        # Cycle metrics
        self.cycle_time = 1.0
        self.ideal_cycle_time = 1.0
        self.last_fault_code = 0

        # Simulation parameters
        self.start_time = time.time()
        self.production_rate = 60  # parts per minute
        self.defect_rate = 0.02  # 2% defect rate
        self.fault_probability = 0.001  # 0.1% chance per update

        # OPC UA nodes (will be populated after server start)
        self.nodes: Dict[str, Any] = {}

    async def init_server(self):
        """Initialize OPC UA server"""
        logger.info(f"Initializing Siemens S7 OPC UA server for {self.line_id}")

        # Create server
        self.server = Server()
        await self.server.init()

        # Configure server
        self.server.set_endpoint(f"opc.tcp://0.0.0.0:{self.port}/freeopcua/server/")
        self.server.set_server_name(f"Siemens S7-1500 Simulator - {self.line_id}")

        # Setup namespace
        uri = f"http://siemens.com/s7-1500/{self.line_id}"
        idx = await self.server.register_namespace(uri)

        # Get Objects node
        objects = self.server.nodes.objects

        # Create main device folder
        device = await objects.add_folder(idx, f"S7-1500_{self.line_id}")

        # Create data blocks folder
        db_folder = await device.add_folder(idx, "DataBlocks")

        # Create DB1 - Production Data
        db1 = await db_folder.add_folder(idx, "DB1_Production")

        # Production counters
        self.nodes['production_count'] = await db1.add_variable(
            idx, "ProductionCount", self.production_count, ua.VariantType.Int32
        )
        await self.nodes['production_count'].set_writable()

        self.nodes['target_count'] = await db1.add_variable(
            idx, "TargetCount", self.target_count, ua.VariantType.Int32
        )
        await self.nodes['target_count'].set_writable()

        self.nodes['good_count'] = await db1.add_variable(
            idx, "GoodCount", self.good_count, ua.VariantType.Int32
        )
        await self.nodes['good_count'].set_writable()

        self.nodes['reject_count'] = await db1.add_variable(
            idx, "RejectCount", self.reject_count, ua.VariantType.Int32
        )
        await self.nodes['reject_count'].set_writable()

        # Machine status
        self.nodes['running'] = await db1.add_variable(
            idx, "Running", self.running, ua.VariantType.Boolean
        )
        await self.nodes['running'].set_writable()

        self.nodes['faulted'] = await db1.add_variable(
            idx, "Faulted", self.faulted, ua.VariantType.Boolean
        )
        await self.nodes['faulted'].set_writable()

        self.nodes['stopped'] = await db1.add_variable(
            idx, "Stopped", self.stopped, ua.VariantType.Boolean
        )
        await self.nodes['stopped'].set_writable()

        # OEE metrics
        self.nodes['oee'] = await db1.add_variable(
            idx, "OEE", self.oee, ua.VariantType.Float
        )
        await self.nodes['oee'].set_writable()

        self.nodes['availability'] = await db1.add_variable(
            idx, "Availability", self.availability, ua.VariantType.Float
        )
        await self.nodes['availability'].set_writable()

        self.nodes['performance'] = await db1.add_variable(
            idx, "Performance", self.performance, ua.VariantType.Float
        )
        await self.nodes['performance'].set_writable()

        self.nodes['quality'] = await db1.add_variable(
            idx, "Quality", self.quality, ua.VariantType.Float
        )
        await self.nodes['quality'].set_writable()

        # Cycle metrics
        self.nodes['cycle_time'] = await db1.add_variable(
            idx, "CycleTime", self.cycle_time, ua.VariantType.Float
        )
        await self.nodes['cycle_time'].set_writable()

        self.nodes['ideal_cycle_time'] = await db1.add_variable(
            idx, "IdealCycleTime", self.ideal_cycle_time, ua.VariantType.Float
        )
        await self.nodes['ideal_cycle_time'].set_writable()

        self.nodes['downtime_minutes'] = await db1.add_variable(
            idx, "DowntimeMinutes", self.downtime_minutes, ua.VariantType.Float
        )
        await self.nodes['downtime_minutes'].set_writable()

        self.nodes['last_fault_code'] = await db1.add_variable(
            idx, "LastFaultCode", self.last_fault_code, ua.VariantType.Int16
        )
        await self.nodes['last_fault_code'].set_writable()

        # System information
        info_folder = await device.add_folder(idx, "DeviceInfo")

        await info_folder.add_variable(
            idx, "PLCType", "S7-1500", ua.VariantType.String
        )
        await info_folder.add_variable(
            idx, "LineID", self.line_id, ua.VariantType.String
        )
        await info_folder.add_variable(
            idx, "Manufacturer", "Siemens AG", ua.VariantType.String
        )
        await info_folder.add_variable(
            idx, "FirmwareVersion", "V2.9.4", ua.VariantType.String
        )

        logger.info(f"OPC UA server initialized with {len(self.nodes)} variables")

    async def start(self):
        """Start OPC UA server and production simulation"""
        await self.init_server()

        async with self.server:
            logger.info(f"Siemens S7 OPC UA server running on port {self.port}")
            logger.info(f"Endpoint: opc.tcp://0.0.0.0:{self.port}/freeopcua/server/")
            logger.info(f"Simulating production line: {self.line_id}")

            # Start production simulation
            await self._simulate_production()

    async def _simulate_production(self):
        """Background task to simulate production data changes"""
        last_update = time.time()

        while True:
            await asyncio.sleep(1.0)  # Update every second

            current_time = time.time()
            elapsed = current_time - last_update
            last_update = current_time

            # Update production based on status
            if self.running and not self.faulted:
                # Calculate parts produced this interval
                parts_per_second = self.production_rate / 60.0
                performance_factor = random.uniform(0.90, 1.05)
                parts_produced = int(parts_per_second * elapsed * performance_factor)

                if parts_produced > 0:
                    # Update production count
                    self.production_count += parts_produced

                    # Simulate quality (some parts are defects)
                    good_parts = sum(1 for _ in range(parts_produced)
                                   if random.random() > self.defect_rate)
                    reject_parts = parts_produced - good_parts

                    self.good_count += good_parts
                    self.reject_count += reject_parts

                    # Update cycle time
                    actual_cycle_time = 1.0 / (parts_per_second * performance_factor)
                    self.cycle_time = round(actual_cycle_time, 2)

                    # Calculate OEE metrics
                    self._update_oee_metrics()

            elif self.faulted:
                # Increment downtime
                self.downtime_minutes += elapsed / 60.0

                # Randomly clear fault after some time
                if self.downtime_minutes > random.uniform(2.0, 10.0):
                    self._clear_fault()

            # Random fault triggering
            if random.random() < self.fault_probability and not self.faulted:
                self._trigger_fault()

            # Update OPC UA nodes
            await self._update_opcua_nodes()

    def _update_oee_metrics(self):
        """Calculate and update OEE metrics"""
        # Calculate availability (uptime / planned production time)
        runtime_minutes = (time.time() - self.start_time) / 60.0
        planned_time = max(runtime_minutes, 1.0)
        uptime = planned_time - self.downtime_minutes
        self.availability = (uptime / planned_time) * 100.0
        self.availability = max(0, min(100, self.availability))

        # Calculate performance (actual production / target production)
        if self.target_count > 0:
            self.performance = (self.production_count / self.target_count) * 100.0
            self.performance = max(0, min(100, self.performance))
        else:
            self.performance = 100.0

        # Calculate quality (good parts / total parts)
        total_parts = self.good_count + self.reject_count
        if total_parts > 0:
            self.quality = (self.good_count / total_parts) * 100.0
        else:
            self.quality = 100.0

        # Calculate OEE (Availability × Performance × Quality)
        self.oee = (self.availability / 100.0) * (self.performance / 100.0) * (self.quality / 100.0) * 100.0

        # Round values
        self.oee = round(self.oee, 1)
        self.availability = round(self.availability, 1)
        self.performance = round(self.performance, 1)
        self.quality = round(self.quality, 1)

    def _trigger_fault(self):
        """Trigger a fault on the production line"""
        self.faulted = True
        self.running = False

        # Set fault code (random fault type)
        fault_codes = [1001, 1002, 1003, 2001, 2002, 3001]
        self.last_fault_code = random.choice(fault_codes)

        logger.info(f"[{self.line_id}] FAULT triggered: Code {self.last_fault_code}")

    def _clear_fault(self):
        """Clear a fault and resume production"""
        self.faulted = False
        self.running = True
        self.last_fault_code = 0

        logger.info(f"[{self.line_id}] FAULT cleared, resuming production")

    async def _update_opcua_nodes(self):
        """Update OPC UA node values"""
        try:
            # Use explicit data types to match node definitions
            await self.nodes['production_count'].write_value(
                ua.DataValue(ua.Variant(int(self.production_count), ua.VariantType.Int32))
            )
            await self.nodes['target_count'].write_value(
                ua.DataValue(ua.Variant(int(self.target_count), ua.VariantType.Int32))
            )
            await self.nodes['good_count'].write_value(
                ua.DataValue(ua.Variant(int(self.good_count), ua.VariantType.Int32))
            )
            await self.nodes['reject_count'].write_value(
                ua.DataValue(ua.Variant(int(self.reject_count), ua.VariantType.Int32))
            )

            await self.nodes['running'].write_value(
                ua.DataValue(ua.Variant(bool(self.running), ua.VariantType.Boolean))
            )
            await self.nodes['faulted'].write_value(
                ua.DataValue(ua.Variant(bool(self.faulted), ua.VariantType.Boolean))
            )
            await self.nodes['stopped'].write_value(
                ua.DataValue(ua.Variant(bool(self.stopped), ua.VariantType.Boolean))
            )

            await self.nodes['oee'].write_value(
                ua.DataValue(ua.Variant(float(self.oee), ua.VariantType.Float))
            )
            await self.nodes['availability'].write_value(
                ua.DataValue(ua.Variant(float(self.availability), ua.VariantType.Float))
            )
            await self.nodes['performance'].write_value(
                ua.DataValue(ua.Variant(float(self.performance), ua.VariantType.Float))
            )
            await self.nodes['quality'].write_value(
                ua.DataValue(ua.Variant(float(self.quality), ua.VariantType.Float))
            )

            await self.nodes['cycle_time'].write_value(
                ua.DataValue(ua.Variant(float(self.cycle_time), ua.VariantType.Float))
            )
            await self.nodes['ideal_cycle_time'].write_value(
                ua.DataValue(ua.Variant(float(self.ideal_cycle_time), ua.VariantType.Float))
            )
            await self.nodes['downtime_minutes'].write_value(
                ua.DataValue(ua.Variant(float(round(self.downtime_minutes, 2)), ua.VariantType.Float))
            )
            await self.nodes['last_fault_code'].write_value(
                ua.DataValue(ua.Variant(int(self.last_fault_code), ua.VariantType.Int16))
            )

        except Exception as e:
            logger.error(f"Error updating OPC UA nodes: {e}")


async def main():
    """Run the Siemens S7 OPC UA simulator"""
    import os
    import sys

    # Get configuration from environment variables
    line_id = os.getenv('LINE_ID', 'SIEMENS-001')
    port = int(os.getenv('OPCUA_PORT', '4840'))

    logger.info(f"Starting Siemens S7-1500 OPC UA Simulator")
    logger.info(f"Line ID: {line_id}")
    logger.info(f"OPC UA Port: {port}")

    # Create and start simulator
    simulator = SiemensS7Simulator(line_id=line_id, port=port)

    try:
        await simulator.start()
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
    except Exception as e:
        logger.error(f"Simulator error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
