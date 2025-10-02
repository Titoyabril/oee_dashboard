"""
Asset Hierarchy Models
Implements site → area → line → cell → machine hierarchy as per specification
Supports manufacturing organizational structure and canonical tag namespace
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import json
from typing import Dict, Any, Optional, List


class Site(models.Model):
    """Manufacturing Site (Plant/Factory)"""

    site_id = models.CharField(max_length=50, unique=True, help_text="Unique site identifier")
    name = models.CharField(max_length=200, help_text="Site display name")
    description = models.TextField(blank=True, null=True)

    # Location
    address = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC')

    # Contact information
    site_manager = models.CharField(max_length=100, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # Operational status
    active = models.BooleanField(default=True)
    commission_date = models.DateField(blank=True, null=True)

    # Metadata
    metadata = models.JSONField(default=dict, help_text="Additional site metadata")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_site'
        ordering = ['name']
        indexes = [
            models.Index(fields=['site_id']),
            models.Index(fields=['active', 'name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.site_id})"

    def get_canonical_path(self) -> str:
        """Get canonical namespace path"""
        return f"site.{self.site_id}"


class Area(models.Model):
    """Production Area within a Site"""

    area_id = models.CharField(max_length=50, help_text="Unique area identifier within site")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='areas')
    name = models.CharField(max_length=200, help_text="Area display name")
    description = models.TextField(blank=True, null=True)

    # Area classification
    AREA_TYPE_CHOICES = [
        ('PRODUCTION', 'Production'),
        ('ASSEMBLY', 'Assembly'),
        ('PACKAGING', 'Packaging'),
        ('QUALITY', 'Quality Control'),
        ('MAINTENANCE', 'Maintenance'),
        ('WAREHOUSE', 'Warehouse'),
        ('UTILITIES', 'Utilities'),
        ('OTHER', 'Other'),
    ]
    area_type = models.CharField(max_length=20, choices=AREA_TYPE_CHOICES, default='PRODUCTION')

    # Physical properties
    floor_area_sqm = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    floor_level = models.IntegerField(blank=True, null=True)

    # Operational status
    active = models.BooleanField(default=True)

    # Metadata
    metadata = models.JSONField(default=dict, help_text="Additional area metadata")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_area'
        unique_together = ('site', 'area_id')
        ordering = ['site', 'name']
        indexes = [
            models.Index(fields=['site', 'area_id']),
            models.Index(fields=['site', 'active']),
            models.Index(fields=['area_type']),
        ]

    def __str__(self):
        return f"{self.site.name} > {self.name}"

    def get_canonical_path(self) -> str:
        """Get canonical namespace path"""
        return f"site.{self.site.site_id}.area.{self.area_id}"


class ProductionLine(models.Model):
    """Production Line within an Area"""

    line_id = models.CharField(max_length=50, help_text="Unique line identifier within area")
    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name='lines')
    name = models.CharField(max_length=200, help_text="Line display name")
    description = models.TextField(blank=True, null=True)

    # Line specifications
    design_capacity_per_hour = models.IntegerField(blank=True, null=True, help_text="Design capacity units/hour")
    actual_capacity_per_hour = models.IntegerField(blank=True, null=True, help_text="Actual capacity units/hour")

    # Product information
    primary_product = models.CharField(max_length=100, blank=True, null=True)
    product_variants = models.JSONField(default=list, help_text="List of product variants")

    # Operational parameters
    standard_cycle_time_seconds = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    changeover_time_minutes = models.IntegerField(blank=True, null=True)

    # Schedule
    scheduled_uptime_hours_per_day = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal('24.0'))
    shifts_per_day = models.IntegerField(default=3)

    # Status
    active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=[
        ('RUNNING', 'Running'),
        ('IDLE', 'Idle'),
        ('DOWN', 'Down'),
        ('MAINTENANCE', 'Maintenance'),
        ('CHANGEOVER', 'Changeover'),
    ], default='IDLE')

    # Metadata
    metadata = models.JSONField(default=dict, help_text="Additional line metadata")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_production_line'
        unique_together = ('area', 'line_id')
        ordering = ['area', 'name']
        indexes = [
            models.Index(fields=['area', 'line_id']),
            models.Index(fields=['area', 'active']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.area.site.name} > {self.area.name} > {self.name}"

    def get_canonical_path(self) -> str:
        """Get canonical namespace path"""
        return f"site.{self.area.site.site_id}.area.{self.area.area_id}.line.{self.line_id}"


class Cell(models.Model):
    """Manufacturing Cell within a Production Line"""

    cell_id = models.CharField(max_length=50, help_text="Unique cell identifier within line")
    line = models.ForeignKey(ProductionLine, on_delete=models.CASCADE, related_name='cells')
    name = models.CharField(max_length=200, help_text="Cell display name")
    description = models.TextField(blank=True, null=True)

    # Cell type and function
    CELL_TYPE_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('ASSEMBLY', 'Assembly'),
        ('TESTING', 'Testing'),
        ('INSPECTION', 'Inspection'),
        ('PACKAGING', 'Packaging'),
        ('MATERIAL_HANDLING', 'Material Handling'),
        ('BUFFER', 'Buffer'),
        ('OTHER', 'Other'),
    ]
    cell_type = models.CharField(max_length=20, choices=CELL_TYPE_CHOICES, default='PROCESSING')

    # Sequence and positioning
    sequence_order = models.IntegerField(help_text="Order in the production line")

    # Operational parameters
    cycle_time_seconds = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    setup_time_minutes = models.IntegerField(blank=True, null=True)

    # Quality parameters
    target_yield_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.0'))
    scrap_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.0'))

    # Status
    active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=[
        ('RUNNING', 'Running'),
        ('IDLE', 'Idle'),
        ('BLOCKED', 'Blocked'),
        ('STARVED', 'Starved'),
        ('DOWN', 'Down'),
        ('MAINTENANCE', 'Maintenance'),
    ], default='IDLE')

    # Metadata
    metadata = models.JSONField(default=dict, help_text="Additional cell metadata")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_cell'
        unique_together = ('line', 'cell_id')
        ordering = ['line', 'sequence_order', 'name']
        indexes = [
            models.Index(fields=['line', 'cell_id']),
            models.Index(fields=['line', 'sequence_order']),
            models.Index(fields=['cell_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.line.area.site.name} > {self.line.area.name} > {self.line.name} > {self.name}"

    def get_canonical_path(self) -> str:
        """Get canonical namespace path"""
        return f"site.{self.line.area.site.site_id}.area.{self.line.area.area_id}.line.{self.line.line_id}.cell.{self.cell_id}"


class Machine(models.Model):
    """Individual Machine within a Cell"""

    machine_id = models.CharField(max_length=50, help_text="Unique machine identifier within cell")
    cell = models.ForeignKey(Cell, on_delete=models.CASCADE, related_name='machines')
    name = models.CharField(max_length=200, help_text="Machine display name")
    description = models.TextField(blank=True, null=True)

    # Machine identification
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    asset_tag = models.CharField(max_length=50, blank=True, null=True)

    # Machine type and function
    MACHINE_TYPE_CHOICES = [
        ('CNC', 'CNC Machine'),
        ('ROBOT', 'Robot'),
        ('CONVEYOR', 'Conveyor'),
        ('PRESS', 'Press'),
        ('FURNACE', 'Furnace'),
        ('PUMP', 'Pump'),
        ('MOTOR', 'Motor'),
        ('SENSOR', 'Sensor'),
        ('PLC', 'PLC'),
        ('HMI', 'HMI'),
        ('OTHER', 'Other'),
    ]
    machine_type = models.CharField(max_length=20, choices=MACHINE_TYPE_CHOICES, default='OTHER')

    # Technical specifications
    rated_power_kw = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    voltage = models.IntegerField(blank=True, null=True)
    max_speed_rpm = models.IntegerField(blank=True, null=True)

    # Operational parameters
    design_oee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('85.0'))
    target_availability_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('90.0'))
    target_performance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('95.0'))
    target_quality_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('99.0'))

    # Maintenance
    install_date = models.DateField(blank=True, null=True)
    last_maintenance_date = models.DateField(blank=True, null=True)
    next_maintenance_date = models.DateField(blank=True, null=True)
    maintenance_interval_days = models.IntegerField(default=90)

    # Network connectivity
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    port = models.IntegerField(blank=True, null=True)
    protocol = models.CharField(max_length=20, choices=[
        ('OPCUA', 'OPC-UA'),
        ('MODBUS', 'Modbus'),
        ('ETHERNET_IP', 'EtherNet/IP'),
        ('PROFINET', 'Profinet'),
        ('S7', 'Siemens S7'),
        ('HTTP', 'HTTP'),
        ('MQTT', 'MQTT'),
        ('OTHER', 'Other'),
    ], blank=True, null=True)

    # Status
    active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=[
        ('RUNNING', 'Running'),
        ('IDLE', 'Idle'),
        ('DOWN', 'Down'),
        ('ALARM', 'Alarm'),
        ('WARNING', 'Warning'),
        ('MAINTENANCE', 'Maintenance'),
        ('OFFLINE', 'Offline'),
    ], default='OFFLINE')

    # Current readings (cached for performance)
    current_oee_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    current_availability_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    current_performance_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    current_quality_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    last_data_update = models.DateTimeField(blank=True, null=True)

    # Metadata
    metadata = models.JSONField(default=dict, help_text="Additional machine metadata")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_machine'
        unique_together = ('cell', 'machine_id')
        ordering = ['cell', 'name']
        indexes = [
            models.Index(fields=['cell', 'machine_id']),
            models.Index(fields=['machine_type']),
            models.Index(fields=['status']),
            models.Index(fields=['active', 'status']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['last_data_update']),
        ]

    def __str__(self):
        return f"{self.cell.line.area.site.name} > {self.cell.line.area.name} > {self.cell.line.name} > {self.cell.name} > {self.name}"

    def get_canonical_path(self) -> str:
        """Get canonical namespace path"""
        return f"site.{self.cell.line.area.site.site_id}.area.{self.cell.line.area.area_id}.line.{self.cell.line.line_id}.cell.{self.cell.cell_id}.machine.{self.machine_id}"

    def get_full_hierarchy(self) -> Dict[str, str]:
        """Get full hierarchy information"""
        return {
            'site_id': self.cell.line.area.site.site_id,
            'site_name': self.cell.line.area.site.name,
            'area_id': self.cell.line.area.area_id,
            'area_name': self.cell.line.area.name,
            'line_id': self.cell.line.line_id,
            'line_name': self.cell.line.name,
            'cell_id': self.cell.cell_id,
            'cell_name': self.cell.name,
            'machine_id': self.machine_id,
            'machine_name': self.name,
            'canonical_path': self.get_canonical_path()
        }

    def is_maintenance_due(self) -> bool:
        """Check if maintenance is due"""
        if not self.next_maintenance_date:
            return False
        return timezone.now().date() >= self.next_maintenance_date

    def get_connection_string(self) -> Optional[str]:
        """Get connection string for this machine"""
        if not self.ip_address:
            return None

        if self.protocol == 'OPCUA':
            return f"opc.tcp://{self.ip_address}:{self.port or 4840}"
        elif self.protocol == 'MODBUS':
            return f"modbus://{self.ip_address}:{self.port or 502}"
        elif self.protocol == 'HTTP':
            return f"http://{self.ip_address}:{self.port or 80}"
        elif self.ip_address and self.port:
            return f"{self.ip_address}:{self.port}"

        return str(self.ip_address)


class CanonicalTag(models.Model):
    """Canonical tag definitions for the hierarchy"""

    tag_name = models.CharField(max_length=200, unique=True, help_text="Canonical tag name")
    description = models.TextField(help_text="Tag description")

    # Tag classification
    TAG_TYPE_CHOICES = [
        ('state.run', 'Running State'),
        ('state.idle', 'Idle State'),
        ('state.down', 'Down State'),
        ('state.blocked', 'Blocked State'),
        ('counter.good', 'Good Parts Counter'),
        ('counter.total', 'Total Parts Counter'),
        ('counter.reject', 'Reject Parts Counter'),
        ('rate.instant', 'Instantaneous Rate'),
        ('rate.average', 'Average Rate'),
        ('cycle.time_actual', 'Actual Cycle Time'),
        ('cycle.time_ideal', 'Ideal Cycle Time'),
        ('fault.code', 'Fault Code'),
        ('fault.active', 'Active Fault'),
        ('fault.severity', 'Fault Severity'),
        ('utilization.planned_time', 'Planned Time'),
        ('utilization.runtime', 'Runtime'),
        ('temperature', 'Temperature'),
        ('pressure', 'Pressure'),
        ('vibration', 'Vibration'),
        ('speed', 'Speed'),
        ('power', 'Power'),
        ('energy', 'Energy'),
    ]
    tag_type = models.CharField(max_length=30, choices=TAG_TYPE_CHOICES)

    # Data type and format
    data_type = models.CharField(max_length=20, choices=[
        ('BOOL', 'Boolean'),
        ('INT', 'Integer'),
        ('REAL', 'Real/Float'),
        ('STRING', 'String'),
        ('TIMESTAMP', 'Timestamp'),
    ], default='REAL')

    unit = models.CharField(max_length=20, blank=True, null=True, help_text="Engineering unit")
    min_value = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    max_value = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)

    # Quality and validation
    quality_threshold = models.IntegerField(default=192, help_text="Minimum quality threshold (0-255)")
    deadband_absolute = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0'))
    deadband_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.0'))

    # Metadata
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'canonical_tag'
        ordering = ['tag_type', 'tag_name']
        indexes = [
            models.Index(fields=['tag_type']),
            models.Index(fields=['data_type']),
        ]

    def __str__(self):
        return f"{self.tag_name} ({self.tag_type})"


class AssetTagMapping(models.Model):
    """Mapping between physical assets and canonical tags"""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='tag_mappings')
    canonical_tag = models.ForeignKey(CanonicalTag, on_delete=models.CASCADE)

    # Source mapping (from PLC/OPC-UA/etc.)
    source_address = models.CharField(max_length=500, help_text="Source tag address (e.g., ns=2;i=1001)")
    source_name = models.CharField(max_length=200, blank=True, null=True, help_text="Original tag name")

    # Data transformation
    scale_factor = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('1.0'))
    offset = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0'))

    # Sampling configuration
    sampling_interval_ms = models.IntegerField(default=1000, help_text="Sampling interval in milliseconds")
    deadband_type = models.IntegerField(default=1, help_text="0=None, 1=Absolute, 2=Percent")
    deadband_value = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0'))

    # Status
    enabled = models.BooleanField(default=True)
    last_value = models.TextField(blank=True, null=True)
    last_timestamp = models.DateTimeField(blank=True, null=True)
    last_quality = models.IntegerField(default=192)

    # Metadata
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_tag_mapping'
        unique_together = ('machine', 'canonical_tag', 'source_address')
        ordering = ['machine', 'canonical_tag']
        indexes = [
            models.Index(fields=['machine', 'enabled']),
            models.Index(fields=['canonical_tag']),
            models.Index(fields=['last_timestamp']),
        ]

    def __str__(self):
        return f"{self.machine.name} - {self.canonical_tag.tag_name}"

    def get_sparkplug_metric_name(self) -> str:
        """Generate Sparkplug metric name"""
        hierarchy = self.machine.get_full_hierarchy()
        return f"{hierarchy['site_id']}.{hierarchy['area_id']}.{hierarchy['line_id']}.{hierarchy['cell_id']}.{hierarchy['machine_id']}.{self.canonical_tag.tag_name}"

    def apply_transformation(self, raw_value: float) -> float:
        """Apply scale and offset transformation"""
        return (raw_value * float(self.scale_factor)) + float(self.offset)