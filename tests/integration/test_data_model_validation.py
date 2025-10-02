"""
Data Model and Namespace Validation Tests

Tests for Section 3: Data Model & Namespace
- Asset hierarchy integrity
- Canonical tag mappings
- Sparkplug namespace compliance
- Signal type validation
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime, timedelta

from oee_analytics.models.asset_hierarchy import (
    Site, Area, ProductionLine, Cell, Machine,
    CanonicalTag, AssetTagMapping
)
from oee_analytics.sparkplug.models import (
    SparkplugNode, SparkplugDevice, SparkplugMetric
)


class TestAssetHierarchy(TestCase):
    """Test asset hierarchy model integrity"""

    def setUp(self):
        """Create test hierarchy"""
        self.site = Site.objects.create(
            site_id="SITE01",
            name="Plant A",
            country="USA",
            timezone="America/New_York"
        )

        self.area = Area.objects.create(
            area_id="AREA01",
            site=self.site,
            name="Production Floor 1",
            area_type="PRODUCTION"
        )

        self.line = ProductionLine.objects.create(
            line_id="LINE01",
            area=self.area,
            name="Assembly Line 1",
            design_capacity_per_hour=100,
            standard_cycle_time_seconds=Decimal('36.0')
        )

        self.cell = Cell.objects.create(
            cell_id="CELL01",
            line=self.line,
            name="Station 1",
            cell_type="ASSEMBLY",
            sequence_order=1
        )

        self.machine = Machine.objects.create(
            machine_id="M001",
            cell=self.cell,
            name="Robot Arm 1",
            machine_type="ROBOT",
            manufacturer="ABB",
            model="IRB 6700"
        )

    def test_site_creation(self):
        """Test site model creation and validation"""
        assert self.site.site_id == "SITE01"
        assert self.site.name == "Plant A"
        assert self.site.active is True

    def test_area_belongs_to_site(self):
        """Test area-site relationship"""
        assert self.area.site == self.site
        assert self.area in self.site.areas.all()

    def test_line_belongs_to_area(self):
        """Test line-area relationship"""
        assert self.line.area == self.area
        assert self.line in self.area.lines.all()

    def test_cell_belongs_to_line(self):
        """Test cell-line relationship"""
        assert self.cell.line == self.line
        assert self.cell in self.line.cells.all()

    def test_machine_belongs_to_cell(self):
        """Test machine-cell relationship"""
        assert self.machine.cell == self.cell
        assert self.machine in self.cell.machines.all()

    def test_canonical_path_generation(self):
        """Test canonical namespace path generation"""
        assert self.site.get_canonical_path() == "site.SITE01"
        assert self.area.get_canonical_path() == "site.SITE01.area.AREA01"
        assert self.line.get_canonical_path() == "site.SITE01.area.AREA01.line.LINE01"
        assert self.cell.get_canonical_path() == "site.SITE01.area.AREA01.line.LINE01.cell.CELL01"
        assert self.machine.get_canonical_path() == "site.SITE01.area.AREA01.line.LINE01.cell.CELL01.machine.M001"

    def test_full_hierarchy_retrieval(self):
        """Test full hierarchy information retrieval"""
        hierarchy = self.machine.get_full_hierarchy()

        assert hierarchy['site_id'] == "SITE01"
        assert hierarchy['site_name'] == "Plant A"
        assert hierarchy['area_id'] == "AREA01"
        assert hierarchy['area_name'] == "Production Floor 1"
        assert hierarchy['line_id'] == "LINE01"
        assert hierarchy['line_name'] == "Assembly Line 1"
        assert hierarchy['cell_id'] == "CELL01"
        assert hierarchy['cell_name'] == "Station 1"
        assert hierarchy['machine_id'] == "M001"
        assert hierarchy['machine_name'] == "Robot Arm 1"

    def test_unique_constraints(self):
        """Test unique constraints in hierarchy"""
        # Duplicate site_id should fail
        with pytest.raises(Exception):
            Site.objects.create(site_id="SITE01", name="Duplicate Site")

        # Duplicate area_id within same site should fail
        with pytest.raises(Exception):
            Area.objects.create(
                area_id="AREA01",
                site=self.site,
                name="Duplicate Area"
            )

    def test_cascade_deletion(self):
        """Test cascade deletion behavior"""
        # Count objects before deletion
        assert Machine.objects.count() == 1
        assert Cell.objects.count() == 1
        assert ProductionLine.objects.count() == 1
        assert Area.objects.count() == 1

        # Delete site should cascade
        self.site.delete()

        # All related objects should be deleted
        assert Site.objects.count() == 0
        assert Area.objects.count() == 0
        assert ProductionLine.objects.count() == 0
        assert Cell.objects.count() == 0
        assert Machine.objects.count() == 0


class TestCanonicalTags(TestCase):
    """Test canonical tag definitions and mappings"""

    def setUp(self):
        """Create test tags"""
        self.tag_good_count = CanonicalTag.objects.create(
            tag_name="counter.good",
            description="Good parts counter",
            tag_type="counter.good",
            data_type="INT",
            unit="parts",
            min_value=Decimal('0'),
            max_value=Decimal('999999')
        )

        self.tag_temperature = CanonicalTag.objects.create(
            tag_name="temperature",
            description="Machine temperature",
            tag_type="temperature",
            data_type="REAL",
            unit="°C",
            min_value=Decimal('0'),
            max_value=Decimal('200'),
            deadband_absolute=Decimal('0.5')
        )

        self.tag_running = CanonicalTag.objects.create(
            tag_name="state.run",
            description="Machine running state",
            tag_type="state.run",
            data_type="BOOL"
        )

    def test_tag_type_classification(self):
        """Test tag type classification"""
        assert self.tag_good_count.tag_type == "counter.good"
        assert self.tag_temperature.tag_type == "temperature"
        assert self.tag_running.tag_type == "state.run"

    def test_data_type_validation(self):
        """Test data type assignments"""
        assert self.tag_good_count.data_type == "INT"
        assert self.tag_temperature.data_type == "REAL"
        assert self.tag_running.data_type == "BOOL"

    def test_engineering_units(self):
        """Test engineering unit assignments"""
        assert self.tag_good_count.unit == "parts"
        assert self.tag_temperature.unit == "°C"

    def test_range_validation(self):
        """Test min/max range definitions"""
        assert self.tag_good_count.min_value == 0
        assert self.tag_good_count.max_value == 999999
        assert self.tag_temperature.min_value == 0
        assert self.tag_temperature.max_value == 200

    def test_deadband_configuration(self):
        """Test deadband settings"""
        assert self.tag_temperature.deadband_absolute == Decimal('0.5')
        assert self.tag_good_count.deadband_absolute == Decimal('0.0')


class TestAssetTagMapping(TestCase):
    """Test asset-to-canonical-tag mapping"""

    def setUp(self):
        """Create test hierarchy and mappings"""
        # Create hierarchy
        self.site = Site.objects.create(site_id="SITE01", name="Plant A")
        self.area = Area.objects.create(area_id="AREA01", site=self.site, name="Floor 1")
        self.line = ProductionLine.objects.create(line_id="LINE01", area=self.area, name="Line 1")
        self.cell = Cell.objects.create(cell_id="CELL01", line=self.line, name="Cell 1", sequence_order=1)
        self.machine = Machine.objects.create(
            machine_id="M001",
            cell=self.cell,
            name="PLC 1",
            ip_address="192.168.1.100",
            protocol="OPCUA"
        )

        # Create canonical tag
        self.tag = CanonicalTag.objects.create(
            tag_name="counter.good",
            description="Good parts counter",
            tag_type="counter.good",
            data_type="INT"
        )

        # Create mapping
        self.mapping = AssetTagMapping.objects.create(
            machine=self.machine,
            canonical_tag=self.tag,
            source_address="ns=2;i=1001",
            source_name="GoodPartsCount",
            scale_factor=Decimal('1.0'),
            offset=Decimal('0.0'),
            sampling_interval_ms=1000
        )

    def test_mapping_creation(self):
        """Test tag mapping creation"""
        assert self.mapping.machine == self.machine
        assert self.mapping.canonical_tag == self.tag
        assert self.mapping.source_address == "ns=2;i=1001"

    def test_sparkplug_metric_name_generation(self):
        """Test Sparkplug metric name generation"""
        metric_name = self.mapping.get_sparkplug_metric_name()
        assert metric_name == "SITE01.AREA01.LINE01.CELL01.M001.counter.good"

    def test_value_transformation(self):
        """Test scale and offset transformation"""
        # Test with scale=1, offset=0
        assert self.mapping.apply_transformation(100.0) == 100.0

        # Test with scale factor
        self.mapping.scale_factor = Decimal('2.0')
        assert self.mapping.apply_transformation(100.0) == 200.0

        # Test with offset
        self.mapping.scale_factor = Decimal('1.0')
        self.mapping.offset = Decimal('10.0')
        assert self.mapping.apply_transformation(100.0) == 110.0

        # Test with both
        self.mapping.scale_factor = Decimal('2.0')
        self.mapping.offset = Decimal('5.0')
        assert self.mapping.apply_transformation(100.0) == 205.0

    def test_unique_mapping_constraint(self):
        """Test unique constraint on machine+tag+source"""
        with pytest.raises(Exception):
            AssetTagMapping.objects.create(
                machine=self.machine,
                canonical_tag=self.tag,
                source_address="ns=2;i=1001",  # Same source address
                source_name="Duplicate"
            )

    def test_multiple_mappings_per_machine(self):
        """Test multiple tag mappings for same machine"""
        tag2 = CanonicalTag.objects.create(
            tag_name="counter.total",
            tag_type="counter.total",
            data_type="INT"
        )

        mapping2 = AssetTagMapping.objects.create(
            machine=self.machine,
            canonical_tag=tag2,
            source_address="ns=2;i=1002",
            source_name="TotalPartsCount"
        )

        assert self.machine.tag_mappings.count() == 2


class TestSparkplugNamespace(TestCase):
    """Test Sparkplug B namespace implementation"""

    def setUp(self):
        """Create Sparkplug node and device"""
        self.node = SparkplugNode.objects.create(
            node_id="EDGE-GATEWAY-01",
            group_id="SITE01",
            mqtt_broker_host="mqtt.example.com",
            mqtt_broker_port=8883,
            mqtt_use_tls=True
        )

        self.device = SparkplugDevice.objects.create(
            device_id="PLC-01",
            node=self.node,
            device_type="PLC",
            manufacturer="Siemens",
            model="S7-1200"
        )

    def test_sparkplug_topic_namespace(self):
        """Test Sparkplug topic namespace generation"""
        assert self.node.topic_namespace == "spBv1.0/SITE01/NEDGE-GATEWAY-01"

    def test_node_device_relationship(self):
        """Test node-device relationship"""
        assert self.device.node == self.node
        assert self.device in self.node.devices.all()

    def test_sequence_number_tracking(self):
        """Test sequence number validation"""
        # Initial sequence
        assert self.node.last_sequence_number == 0

        # Valid increment
        assert self.node.update_sequence_number(1) is True
        assert self.node.last_sequence_number == 1

        # Another valid increment
        assert self.node.update_sequence_number(2) is True
        assert self.node.last_sequence_number == 2

        # Sequence gap (invalid)
        assert self.node.update_sequence_number(5) is False
        assert self.node.error_count == 1

        # Birth resets sequence
        assert self.node.update_sequence_number(0) is True
        assert self.node.last_sequence_number == 0

    def test_node_status_tracking(self):
        """Test node status transitions"""
        assert self.node.status == "OFFLINE"
        assert not self.node.is_online()

        self.node.status = "BIRTH"
        assert self.node.is_online()

        self.node.status = "ONLINE"
        assert self.node.is_online()

        self.node.status = "DEATH"
        assert not self.node.is_online()

    def test_unique_group_node_constraint(self):
        """Test unique group_id + node_id constraint"""
        with pytest.raises(Exception):
            SparkplugNode.objects.create(
                node_id="EDGE-GATEWAY-01",  # Same node_id
                group_id="SITE01",  # Same group_id
                mqtt_broker_host="mqtt2.example.com"
            )


class TestSignalTypes(TestCase):
    """Test signal type definitions and usage"""

    def test_state_signal_types(self):
        """Test state-based signal types"""
        states = [
            ('state.run', 'BOOL'),
            ('state.idle', 'BOOL'),
            ('state.down', 'BOOL'),
            ('state.blocked', 'BOOL'),
        ]

        for tag_type, data_type in states:
            tag = CanonicalTag.objects.create(
                tag_name=tag_type,
                tag_type=tag_type,
                data_type=data_type
            )
            assert tag.data_type == data_type

    def test_counter_signal_types(self):
        """Test counter-based signal types"""
        counters = [
            ('counter.good', 'INT'),
            ('counter.total', 'INT'),
            ('counter.reject', 'INT'),
        ]

        for tag_type, data_type in counters:
            tag = CanonicalTag.objects.create(
                tag_name=tag_type,
                tag_type=tag_type,
                data_type=data_type
            )
            assert tag.data_type == data_type

    def test_rate_signal_types(self):
        """Test rate-based signal types"""
        rates = [
            ('rate.instant', 'REAL'),
            ('rate.average', 'REAL'),
        ]

        for tag_type, data_type in rates:
            tag = CanonicalTag.objects.create(
                tag_name=tag_type,
                tag_type=tag_type,
                data_type=data_type,
                unit="parts/min"
            )
            assert tag.data_type == data_type
            assert tag.unit == "parts/min"

    def test_fault_signal_types(self):
        """Test fault-related signal types"""
        faults = [
            ('fault.code', 'INT'),
            ('fault.active', 'BOOL'),
            ('fault.severity', 'INT'),
        ]

        for tag_type, data_type in faults:
            tag = CanonicalTag.objects.create(
                tag_name=tag_type,
                tag_type=tag_type,
                data_type=data_type
            )
            assert tag.data_type == data_type

    def test_process_signal_types(self):
        """Test process variable signal types"""
        process_vars = [
            ('temperature', 'REAL', '°C'),
            ('pressure', 'REAL', 'bar'),
            ('speed', 'REAL', 'rpm'),
            ('power', 'REAL', 'kW'),
        ]

        for tag_type, data_type, unit in process_vars:
            tag = CanonicalTag.objects.create(
                tag_name=tag_type,
                tag_type=tag_type,
                data_type=data_type,
                unit=unit
            )
            assert tag.data_type == data_type
            assert tag.unit == unit


class TestMachineConnectionString(TestCase):
    """Test machine connection string generation"""

    def setUp(self):
        """Create test site and machine"""
        site = Site.objects.create(site_id="SITE01", name="Plant A")
        area = Area.objects.create(area_id="AREA01", site=site, name="Floor 1")
        line = ProductionLine.objects.create(line_id="LINE01", area=area, name="Line 1")
        cell = Cell.objects.create(cell_id="CELL01", line=line, name="Cell 1", sequence_order=1)

        self.machine_opcua = Machine.objects.create(
            machine_id="M001",
            cell=cell,
            name="OPC-UA PLC",
            ip_address="192.168.1.100",
            port=4840,
            protocol="OPCUA"
        )

        self.machine_modbus = Machine.objects.create(
            machine_id="M002",
            cell=cell,
            name="Modbus Device",
            ip_address="192.168.1.101",
            port=502,
            protocol="MODBUS"
        )

        self.machine_http = Machine.objects.create(
            machine_id="M003",
            cell=cell,
            name="HTTP Device",
            ip_address="192.168.1.102",
            port=80,
            protocol="HTTP"
        )

    def test_opcua_connection_string(self):
        """Test OPC-UA connection string generation"""
        conn_str = self.machine_opcua.get_connection_string()
        assert conn_str == "opc.tcp://192.168.1.100:4840"

    def test_modbus_connection_string(self):
        """Test Modbus connection string generation"""
        conn_str = self.machine_modbus.get_connection_string()
        assert conn_str == "modbus://192.168.1.101:502"

    def test_http_connection_string(self):
        """Test HTTP connection string generation"""
        conn_str = self.machine_http.get_connection_string()
        assert conn_str == "http://192.168.1.102:80"


class TestMaintenanceTracking(TestCase):
    """Test machine maintenance tracking"""

    def setUp(self):
        """Create test machine with maintenance info"""
        site = Site.objects.create(site_id="SITE01", name="Plant A")
        area = Area.objects.create(area_id="AREA01", site=site, name="Floor 1")
        line = ProductionLine.objects.create(line_id="LINE01", area=area, name="Line 1")
        cell = Cell.objects.create(cell_id="CELL01", line=line, name="Cell 1", sequence_order=1)

        self.machine = Machine.objects.create(
            machine_id="M001",
            cell=cell,
            name="Test Machine",
            last_maintenance_date=timezone.now().date() - timedelta(days=80),
            maintenance_interval_days=90
        )

    def test_maintenance_due_calculation(self):
        """Test maintenance due date calculation"""
        # Set next maintenance to tomorrow
        self.machine.next_maintenance_date = timezone.now().date() + timedelta(days=1)
        assert not self.machine.is_maintenance_due()

        # Set next maintenance to yesterday
        self.machine.next_maintenance_date = timezone.now().date() - timedelta(days=1)
        assert self.machine.is_maintenance_due()

        # Set next maintenance to today
        self.machine.next_maintenance_date = timezone.now().date()
        assert self.machine.is_maintenance_due()


class TestQualityThresholds(TestCase):
    """Test quality code and threshold validation"""

    def test_quality_threshold_default(self):
        """Test default quality threshold (192 = Good in Sparkplug)"""
        tag = CanonicalTag.objects.create(
            tag_name="test.tag",
            tag_type="temperature",
            data_type="REAL"
        )
        assert tag.quality_threshold == 192  # Default GOOD quality

    def test_quality_threshold_custom(self):
        """Test custom quality threshold"""
        tag = CanonicalTag.objects.create(
            tag_name="test.tag",
            tag_type="temperature",
            data_type="REAL",
            quality_threshold=128  # Custom threshold
        )
        assert tag.quality_threshold == 128


class TestDataModelIndexing(TestCase):
    """Test database indexing for performance"""

    def test_site_indexes(self):
        """Test Site model indexes"""
        indexes = [idx.name for idx in Site._meta.indexes]
        # Verify key indexes exist
        assert any('site_id' in str(idx.fields) for idx in Site._meta.indexes)

    def test_machine_indexes(self):
        """Test Machine model indexes"""
        # Verify critical indexes
        assert any('status' in str(idx.fields) for idx in Machine._meta.indexes)
        assert any('machine_id' in str(idx.fields) for idx in Machine._meta.indexes)

    def test_sparkplug_node_indexes(self):
        """Test SparkplugNode indexes"""
        assert any('group_id' in str(idx.fields) for idx in SparkplugNode._meta.indexes)
        assert any('status' in str(idx.fields) for idx in SparkplugNode._meta.indexes)
