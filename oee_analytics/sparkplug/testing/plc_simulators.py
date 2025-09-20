"""
PLC Simulators for Testing
Simulates Siemens S7 and Allen-Bradley PLCs for testing Sparkplug B integration
"""

import asyncio
import random
import time
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import socket
import struct
from abc import ABC, abstractmethod

import numpy as np
from faker import Faker


class SimulatorState(Enum):
    """Simulator state enumeration"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class SimulatedTag:
    """Configuration for a simulated PLC tag"""
    name: str
    address: str
    data_type: str
    initial_value: Any = 0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    # Simulation behavior
    behavior: str = "static"  # static, random, sine, step, ramp, cycle
    update_rate: float = 1.0  # seconds
    noise_level: float = 0.0  # percentage
    
    # Behavior-specific parameters
    sine_amplitude: float = 1.0
    sine_frequency: float = 0.1  # Hz
    sine_phase: float = 0.0
    step_values: List[Any] = field(default_factory=list)
    step_duration: float = 10.0  # seconds per step
    ramp_rate: float = 1.0  # units per second
    
    # Current state
    current_value: Any = field(init=False)
    last_update: float = field(init=False, default=0.0)
    simulation_time: float = field(init=False, default=0.0)
    step_index: int = field(init=False, default=0)
    
    def __post_init__(self):
        self.current_value = self.initial_value


class BasePLCSimulator(ABC):
    """Base class for PLC simulators"""
    
    def __init__(self, host: str = "localhost", port: int = 102, logger: Optional[logging.Logger] = None):
        self.host = host
        self.port = port
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # State
        self.state = SimulatorState.STOPPED
        self.tags: Dict[str, SimulatedTag] = {}
        self.clients: List[socket.socket] = []
        
        # Simulation
        self.simulation_thread: Optional[threading.Thread] = None
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.start_time = 0.0
        
        # Statistics
        self.stats = {
            'requests_received': 0,
            'responses_sent': 0,
            'errors': 0,
            'connections': 0,
            'uptime_seconds': 0
        }
        
        # Faker for realistic data
        self.faker = Faker()
    
    def add_tag(self, tag: SimulatedTag):
        """Add a simulated tag"""
        self.tags[tag.name] = tag
        self.logger.debug(f"Added simulated tag: {tag.name} ({tag.address})")
    
    def remove_tag(self, tag_name: str):
        """Remove a simulated tag"""
        if tag_name in self.tags:
            del self.tags[tag_name]
            self.logger.debug(f"Removed simulated tag: {tag_name}")
    
    def get_tag_value(self, address: str) -> Any:
        """Get current value of a tag by address"""
        for tag in self.tags.values():
            if tag.address == address:
                return tag.current_value
        return None
    
    def set_tag_value(self, address: str, value: Any):
        """Set value of a tag by address"""
        for tag in self.tags.values():
            if tag.address == address:
                tag.current_value = value
                break
    
    async def start(self):
        """Start the PLC simulator"""
        try:
            self.logger.info(f"Starting {self.__class__.__name__} on {self.host}:{self.port}")
            
            # Start simulation thread
            self.running = True
            self.start_time = time.time()
            self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self.simulation_thread.start()
            
            # Start server
            await self._start_server()
            
            self.state = SimulatorState.RUNNING
            self.logger.info(f"PLC simulator started with {len(self.tags)} tags")
            
        except Exception as e:
            self.state = SimulatorState.ERROR
            self.logger.error(f"Failed to start PLC simulator: {e}")
            raise
    
    async def stop(self):
        """Stop the PLC simulator"""
        try:
            self.running = False
            self.state = SimulatorState.STOPPED
            
            # Stop server
            if self.server_socket:
                self.server_socket.close()
            
            # Close client connections
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
            
            # Wait for simulation thread
            if self.simulation_thread and self.simulation_thread.is_alive():
                self.simulation_thread.join(timeout=5.0)
            
            self.logger.info("PLC simulator stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping PLC simulator: {e}")
    
    def _simulation_loop(self):
        """Main simulation loop (runs in thread)"""
        while self.running:
            try:
                current_time = time.time()
                simulation_time = current_time - self.start_time
                
                # Update all tags
                for tag in self.tags.values():
                    if current_time - tag.last_update >= tag.update_rate:
                        self._update_tag(tag, simulation_time)
                        tag.last_update = current_time
                
                # Update statistics
                self.stats['uptime_seconds'] = int(simulation_time)
                
                time.sleep(0.1)  # 100ms update cycle
                
            except Exception as e:
                self.logger.error(f"Simulation loop error: {e}")
                time.sleep(1.0)
    
    def _update_tag(self, tag: SimulatedTag, simulation_time: float):
        """Update a single tag value based on its behavior"""
        try:
            if tag.behavior == "static":
                # No change
                pass
            
            elif tag.behavior == "random":
                # Random value within range
                if tag.data_type.upper() in ['BOOL', 'BOOLEAN']:
                    tag.current_value = random.choice([True, False])
                elif tag.data_type.upper() in ['INT', 'DINT', 'SINT']:
                    min_val = int(tag.min_value or 0)
                    max_val = int(tag.max_value or 100)
                    tag.current_value = random.randint(min_val, max_val)
                elif tag.data_type.upper() in ['REAL', 'FLOAT', 'DOUBLE']:
                    min_val = float(tag.min_value or 0.0)
                    max_val = float(tag.max_value or 100.0)
                    tag.current_value = random.uniform(min_val, max_val)
                elif tag.data_type.upper() == 'STRING':
                    tag.current_value = self.faker.word()
            
            elif tag.behavior == "sine":
                # Sine wave
                amplitude = tag.sine_amplitude
                frequency = tag.sine_frequency
                phase = tag.sine_phase
                offset = float(tag.initial_value)
                
                value = offset + amplitude * np.sin(2 * np.pi * frequency * simulation_time + phase)
                
                # Apply limits
                if tag.min_value is not None:
                    value = max(value, tag.min_value)
                if tag.max_value is not None:
                    value = min(value, tag.max_value)
                
                tag.current_value = value
            
            elif tag.behavior == "step":
                # Step through predefined values
                if tag.step_values:
                    step_time = simulation_time / tag.step_duration
                    step_index = int(step_time) % len(tag.step_values)
                    tag.current_value = tag.step_values[step_index]
            
            elif tag.behavior == "ramp":
                # Linear ramp
                value = float(tag.initial_value) + tag.ramp_rate * simulation_time
                
                # Apply limits and wrap if needed
                if tag.min_value is not None and tag.max_value is not None:
                    range_size = tag.max_value - tag.min_value
                    value = tag.min_value + ((value - tag.min_value) % range_size)
                
                tag.current_value = value
            
            elif tag.behavior == "cycle":
                # Production cycle simulation
                cycle_time = 30.0  # 30 second cycles
                phase = (simulation_time % cycle_time) / cycle_time
                
                if tag.name.lower().find('cycle_start') >= 0:
                    tag.current_value = phase < 0.1  # 10% of cycle
                elif tag.name.lower().find('cycle_end') >= 0:
                    tag.current_value = 0.9 < phase < 1.0  # Last 10% of cycle
                elif tag.name.lower().find('running') >= 0:
                    tag.current_value = 0.1 <= phase <= 0.9
                elif tag.name.lower().find('count') >= 0:
                    tag.current_value = int(simulation_time / cycle_time)
                elif tag.name.lower().find('speed') >= 0:
                    # Simulate speed variation during cycle
                    if 0.1 <= phase <= 0.9:
                        base_speed = float(tag.initial_value)
                        variation = 0.1 * np.sin(4 * np.pi * phase)
                        tag.current_value = base_speed * (1 + variation)
                    else:
                        tag.current_value = 0.0
            
            # Add noise if configured
            if tag.noise_level > 0 and isinstance(tag.current_value, (int, float)):
                noise = tag.current_value * tag.noise_level / 100.0
                noise_value = random.uniform(-noise, noise)
                tag.current_value += noise_value
            
            # Apply data type constraints
            tag.current_value = self._apply_data_type_constraints(tag.current_value, tag.data_type)
            
        except Exception as e:
            self.logger.error(f"Error updating tag {tag.name}: {e}")
    
    def _apply_data_type_constraints(self, value: Any, data_type: str) -> Any:
        """Apply data type constraints to a value"""
        try:
            data_type = data_type.upper()
            
            if data_type in ['BOOL', 'BOOLEAN']:
                return bool(value)
            elif data_type == 'SINT':
                return max(-128, min(127, int(value)))
            elif data_type == 'INT':
                return max(-32768, min(32767, int(value)))
            elif data_type == 'DINT':
                return max(-2147483648, min(2147483647, int(value)))
            elif data_type == 'USINT':
                return max(0, min(255, int(value)))
            elif data_type == 'UINT':
                return max(0, min(65535, int(value)))
            elif data_type == 'UDINT':
                return max(0, min(4294967295, int(value)))
            elif data_type in ['REAL', 'FLOAT']:
                return float(value)
            elif data_type == 'STRING':
                return str(value)[:255]  # Limit string length
            else:
                return value
                
        except (ValueError, TypeError):
            return value
    
    @abstractmethod
    async def _start_server(self):
        """Start the protocol-specific server"""
        pass
    
    @abstractmethod
    def _handle_client(self, client_socket: socket.socket):
        """Handle client connection (protocol-specific)"""
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get simulator statistics"""
        return {
            **self.stats,
            'state': self.state.value,
            'tag_count': len(self.tags),
            'client_count': len(self.clients)
        }


class SiemensS7Simulator(BasePLCSimulator):
    """Siemens S7 PLC Simulator"""
    
    def __init__(self, host: str = "localhost", port: int = 102, **kwargs):
        super().__init__(host, port, **kwargs)
        
        # Add default S7 tags
        self._add_default_s7_tags()
    
    def _add_default_s7_tags(self):
        """Add default Siemens S7 tags for testing"""
        default_tags = [
            # Production cycle tags
            SimulatedTag(
                name="cycle_start",
                address="DB1,0.0",
                data_type="BOOL",
                behavior="cycle",
                update_rate=0.5
            ),
            SimulatedTag(
                name="cycle_end",
                address="DB1,0.1",
                data_type="BOOL",
                behavior="cycle",
                update_rate=0.5
            ),
            SimulatedTag(
                name="machine_running",
                address="DB1,0.2",
                data_type="BOOL",
                behavior="cycle",
                update_rate=1.0
            ),
            
            # Counters
            SimulatedTag(
                name="good_parts",
                address="DB1,2",
                data_type="DINT",
                initial_value=0,
                behavior="step",
                step_values=[0, 1, 2, 3, 4, 5],
                step_duration=30.0,
                update_rate=30.0
            ),
            SimulatedTag(
                name="scrap_parts",
                address="DB1,6",
                data_type="DINT",
                initial_value=0,
                behavior="random",
                min_value=0,
                max_value=1,
                update_rate=60.0
            ),
            
            # Process values
            SimulatedTag(
                name="temperature",
                address="DB1,10",
                data_type="REAL",
                initial_value=75.0,
                behavior="sine",
                sine_amplitude=5.0,
                sine_frequency=0.01,
                noise_level=2.0,
                update_rate=2.0
            ),
            SimulatedTag(
                name="pressure",
                address="DB1,14",
                data_type="REAL",
                initial_value=5.2,
                behavior="sine",
                sine_amplitude=0.3,
                sine_frequency=0.02,
                noise_level=1.0,
                update_rate=1.0
            ),
            SimulatedTag(
                name="speed",
                address="DB1,18",
                data_type="REAL",
                initial_value=1500.0,
                behavior="cycle",
                update_rate=1.0
            ),
            
            # Status and alarms
            SimulatedTag(
                name="alarm_active",
                address="DB1,0.3",
                data_type="BOOL",
                behavior="random",
                update_rate=30.0
            ),
            SimulatedTag(
                name="operator_id",
                address="DB1,22",
                data_type="STRING",
                initial_value="OP001",
                behavior="step",
                step_values=["OP001", "OP002", "OP003"],
                step_duration=3600.0,  # Change every hour
                update_rate=3600.0
            ),
        ]
        
        for tag in default_tags:
            self.add_tag(tag)
    
    async def _start_server(self):
        """Start S7 protocol server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        # Accept connections in a separate thread
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()
    
    def _accept_connections(self):
        """Accept client connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                self.clients.append(client_socket)
                self.stats['connections'] += 1
                
                self.logger.info(f"S7 client connected from {address}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error accepting S7 connection: {e}")
                break
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle S7 client connection"""
        try:
            while self.running:
                # Receive request
                data = client_socket.recv(1024)
                if not data:
                    break
                
                self.stats['requests_received'] += 1
                
                # Parse S7 request (simplified)
                response = self._process_s7_request(data)
                
                # Send response
                if response:
                    client_socket.send(response)
                    self.stats['responses_sent'] += 1
                
        except Exception as e:
            self.logger.error(f"Error handling S7 client: {e}")
            self.stats['errors'] += 1
        finally:
            try:
                client_socket.close()
                self.clients.remove(client_socket)
            except:
                pass
    
    def _process_s7_request(self, request_data: bytes) -> Optional[bytes]:
        """Process S7 protocol request (simplified implementation)"""
        try:
            # This is a very simplified S7 protocol implementation
            # In a real implementation, you would parse the actual S7 PDU
            
            # For testing purposes, we'll simulate read responses
            if len(request_data) >= 4:
                # Assume it's a read request
                # Return a dummy response with some tag values
                response_data = bytearray(32)
                
                # Simulate temperature value (4 bytes, IEEE 754 float)
                temp_tag = self.tags.get('temperature')
                if temp_tag:
                    temp_bytes = struct.pack('>f', float(temp_tag.current_value))
                    response_data[0:4] = temp_bytes
                
                # Simulate good parts count (4 bytes, big-endian int)
                parts_tag = self.tags.get('good_parts')
                if parts_tag:
                    parts_bytes = struct.pack('>I', int(parts_tag.current_value))
                    response_data[4:8] = parts_bytes
                
                # Simulate boolean values (1 byte each)
                running_tag = self.tags.get('machine_running')
                if running_tag:
                    response_data[8] = 1 if running_tag.current_value else 0
                
                cycle_start_tag = self.tags.get('cycle_start')
                if cycle_start_tag:
                    response_data[9] = 1 if cycle_start_tag.current_value else 0
                
                return bytes(response_data)
            
        except Exception as e:
            self.logger.error(f"Error processing S7 request: {e}")
            
        return None


class AllenBradleySimulator(BasePLCSimulator):
    """Allen-Bradley PLC Simulator"""
    
    def __init__(self, host: str = "localhost", port: int = 44818, **kwargs):
        super().__init__(host, port, **kwargs)
        
        # Add default AB tags
        self._add_default_ab_tags()
    
    def _add_default_ab_tags(self):
        """Add default Allen-Bradley tags for testing"""
        default_tags = [
            # ControlLogix-style tags
            SimulatedTag(
                name="ProductionLine.CycleStart",
                address="ProductionLine.CycleStart",
                data_type="BOOL",
                behavior="cycle",
                update_rate=0.5
            ),
            SimulatedTag(
                name="ProductionLine.CycleComplete",
                address="ProductionLine.CycleComplete",
                data_type="BOOL",
                behavior="cycle",
                update_rate=0.5
            ),
            SimulatedTag(
                name="ProductionLine.Running",
                address="ProductionLine.Running",
                data_type="BOOL",
                behavior="cycle",
                update_rate=1.0
            ),
            
            # Counters
            SimulatedTag(
                name="Counters.GoodParts",
                address="Counters.GoodParts",
                data_type="DINT",
                initial_value=0,
                behavior="step",
                step_values=[0, 1, 2, 3, 4, 5],
                step_duration=30.0,
                update_rate=30.0
            ),
            SimulatedTag(
                name="Counters.ScrapParts",
                address="Counters.ScrapParts",
                data_type="DINT",
                initial_value=0,
                behavior="random",
                min_value=0,
                max_value=1,
                update_rate=60.0
            ),
            
            # Process values
            SimulatedTag(
                name="Process.Temperature",
                address="Process.Temperature",
                data_type="REAL",
                initial_value=80.0,
                behavior="sine",
                sine_amplitude=4.0,
                sine_frequency=0.01,
                noise_level=1.5,
                update_rate=2.0
            ),
            SimulatedTag(
                name="Process.Pressure",
                address="Process.Pressure",
                data_type="REAL",
                initial_value=4.8,
                behavior="sine",
                sine_amplitude=0.2,
                sine_frequency=0.02,
                noise_level=0.5,
                update_rate=1.0
            ),
            SimulatedTag(
                name="Process.FlowRate",
                address="Process.FlowRate",
                data_type="REAL",
                initial_value=125.0,
                behavior="sine",
                sine_amplitude=10.0,
                sine_frequency=0.005,
                noise_level=2.0,
                update_rate=1.0
            ),
            
            # HMI tags
            SimulatedTag(
                name="HMI.OperatorID",
                address="HMI.OperatorID",
                data_type="STRING",
                initial_value="OP001",
                behavior="step",
                step_values=["OP001", "OP002", "OP003"],
                step_duration=3600.0,
                update_rate=3600.0
            ),
            SimulatedTag(
                name="HMI.RecipeNumber",
                address="HMI.RecipeNumber",
                data_type="DINT",
                initial_value=1,
                behavior="step",
                step_values=[1, 2, 3, 1],
                step_duration=1800.0,  # 30 minutes
                update_rate=1800.0
            ),
        ]
        
        for tag in default_tags:
            self.add_tag(tag)
    
    async def _start_server(self):
        """Start EtherNet/IP server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        # Accept connections in a separate thread
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()
    
    def _accept_connections(self):
        """Accept client connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                self.clients.append(client_socket)
                self.stats['connections'] += 1
                
                self.logger.info(f"EtherNet/IP client connected from {address}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error accepting EtherNet/IP connection: {e}")
                break
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle EtherNet/IP client connection"""
        try:
            while self.running:
                # Receive request
                data = client_socket.recv(1024)
                if not data:
                    break
                
                self.stats['requests_received'] += 1
                
                # Parse EtherNet/IP request (simplified)
                response = self._process_ethernet_ip_request(data)
                
                # Send response
                if response:
                    client_socket.send(response)
                    self.stats['responses_sent'] += 1
                
        except Exception as e:
            self.logger.error(f"Error handling EtherNet/IP client: {e}")
            self.stats['errors'] += 1
        finally:
            try:
                client_socket.close()
                self.clients.remove(client_socket)
            except:
                pass
    
    def _process_ethernet_ip_request(self, request_data: bytes) -> Optional[bytes]:
        """Process EtherNet/IP protocol request (simplified implementation)"""
        try:
            # This is a very simplified EtherNet/IP implementation
            # In a real implementation, you would parse the actual CIP messages
            
            # For testing purposes, we'll simulate tag read responses
            if len(request_data) >= 8:
                # Create a JSON response with current tag values
                tag_values = {}
                for name, tag in self.tags.items():
                    tag_values[name] = {
                        'value': tag.current_value,
                        'type': tag.data_type,
                        'address': tag.address,
                        'timestamp': time.time()
                    }
                
                response_json = json.dumps(tag_values)
                response_bytes = response_json.encode('utf-8')
                
                # Simple framing: 4-byte length + data
                length_bytes = struct.pack('>I', len(response_bytes))
                return length_bytes + response_bytes
            
        except Exception as e:
            self.logger.error(f"Error processing EtherNet/IP request: {e}")
            
        return None


class PLCSimulatorManager:
    """Manager for multiple PLC simulators"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.simulators: Dict[str, BasePLCSimulator] = {}
        self.running = False
    
    def add_simulator(self, name: str, simulator: BasePLCSimulator):
        """Add a PLC simulator"""
        self.simulators[name] = simulator
        self.logger.info(f"Added PLC simulator: {name}")
    
    def remove_simulator(self, name: str):
        """Remove a PLC simulator"""
        if name in self.simulators:
            del self.simulators[name]
            self.logger.info(f"Removed PLC simulator: {name}")
    
    async def start_all(self):
        """Start all simulators"""
        self.logger.info("Starting all PLC simulators")
        
        for name, simulator in self.simulators.items():
            try:
                await simulator.start()
                self.logger.info(f"Started simulator: {name}")
            except Exception as e:
                self.logger.error(f"Failed to start simulator {name}: {e}")
        
        self.running = True
    
    async def stop_all(self):
        """Stop all simulators"""
        self.logger.info("Stopping all PLC simulators")
        
        for name, simulator in self.simulators.items():
            try:
                await simulator.stop()
                self.logger.info(f"Stopped simulator: {name}")
            except Exception as e:
                self.logger.error(f"Failed to stop simulator {name}: {e}")
        
        self.running = False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all simulators"""
        stats = {}
        for name, simulator in self.simulators.items():
            stats[name] = simulator.get_statistics()
        return stats
    
    def get_tag_values(self, simulator_name: Optional[str] = None) -> Dict[str, Any]:
        """Get current tag values"""
        if simulator_name:
            simulators = {simulator_name: self.simulators[simulator_name]}
        else:
            simulators = self.simulators
        
        tag_values = {}
        for name, simulator in simulators.items():
            tag_values[name] = {}
            for tag_name, tag in simulator.tags.items():
                tag_values[name][tag_name] = {
                    'address': tag.address,
                    'value': tag.current_value,
                    'type': tag.data_type,
                    'behavior': tag.behavior,
                    'last_update': tag.last_update
                }
        
        return tag_values
    
    def create_demo_setup(self) -> None:
        """Create a demo setup with both types of simulators"""
        # Siemens S7 simulator
        s7_sim = SiemensS7Simulator(host="localhost", port=10102, logger=self.logger)
        self.add_simulator("siemens_demo", s7_sim)
        
        # Allen-Bradley simulator
        ab_sim = AllenBradleySimulator(host="localhost", port=10818, logger=self.logger)
        self.add_simulator("ab_demo", ab_sim)
        
        self.logger.info("Demo PLC simulator setup created")


# Example usage and testing functions
def create_realistic_production_scenario():
    """Create a realistic production scenario for testing"""
    manager = PLCSimulatorManager()
    
    # Create production line simulator
    production_sim = SiemensS7Simulator(host="localhost", port=11102)
    
    # Add realistic production tags
    production_tags = [
        # Main production cycle
        SimulatedTag(
            name="main_cycle_start",
            address="DB10,0.0",
            data_type="BOOL",
            behavior="cycle",
            update_rate=0.1
        ),
        SimulatedTag(
            name="main_cycle_time",
            address="DB10,2",
            data_type="REAL",
            initial_value=25.5,
            behavior="sine",
            sine_amplitude=2.0,
            sine_frequency=0.02,
            noise_level=5.0,
            update_rate=1.0
        ),
        
        # Quality inspection
        SimulatedTag(
            name="quality_pass",
            address="DB10,0.1",
            data_type="BOOL",
            behavior="random",  # 95% pass rate
            update_rate=25.0
        ),
        
        # Machine health
        SimulatedTag(
            name="vibration_level",
            address="DB10,6",
            data_type="REAL",
            initial_value=2.1,
            behavior="sine",
            sine_amplitude=0.3,
            sine_frequency=0.1,
            noise_level=10.0,
            update_rate=0.5
        ),
        
        # Downtime events
        SimulatedTag(
            name="maintenance_mode",
            address="DB10,0.2",
            data_type="BOOL",
            behavior="step",
            step_values=[False] * 119 + [True],  # 5 minutes maintenance every 2 hours
            step_duration=60.0,  # 1 minute steps
            update_rate=60.0
        ),
    ]
    
    for tag in production_tags:
        production_sim.add_tag(tag)
    
    manager.add_simulator("production_line_1", production_sim)
    
    return manager