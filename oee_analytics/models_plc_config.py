"""
Django Models for PLC Connection Configuration
Stores PLC connection settings, tags, and metadata in database for easy management
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
import json


class PLCConnection(models.Model):
    """PLC Connection Configuration"""

    PLC_TYPES = [
        ('ALLEN_BRADLEY', 'Allen-Bradley'),
        ('SIEMENS_S7', 'Siemens S7'),
        ('MODBUS_TCP', 'Modbus TCP'),
        ('OPCUA', 'OPC UA'),
    ]

    PLC_FAMILIES = [
        ('CONTROLLOGIX', 'ControlLogix'),
        ('COMPACTLOGIX', 'CompactLogix'),
        ('MICROLOGIX', 'MicroLogix'),
        ('MICRO800', 'Micro800'),
        ('SLC500', 'SLC-500'),
        ('PLC5', 'PLC-5'),
    ]

    # Basic Information
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for this PLC connection (e.g., LINE-001-ControlLogix)"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of this PLC and its purpose"
    )
    plc_type = models.CharField(
        max_length=20,
        choices=PLC_TYPES,
        default='ALLEN_BRADLEY',
        help_text="Type of PLC"
    )
    plc_family = models.CharField(
        max_length=20,
        choices=PLC_FAMILIES,
        default='CONTROLLOGIX',
        help_text="PLC family/model"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable this connection"
    )

    # Connection Settings
    ip_address = models.CharField(
        max_length=255,
        help_text="IP address or hostname of the PLC"
    )
    port = models.IntegerField(
        default=44818,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text="Port number (default: 44818 for EtherNet/IP)"
    )
    slot = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(17)],
        help_text="Slot number in the rack (0-17)"
    )
    timeout = models.FloatField(
        default=5.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(60.0)],
        help_text="Connection timeout in seconds"
    )
    simulator_mode = models.BooleanField(
        default=False,
        help_text="Use simulator instead of real hardware"
    )

    # Polling Configuration
    polling_interval_ms = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(100), MaxValueValidator(60000)],
        help_text="Polling interval in milliseconds"
    )
    batch_size = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Number of tags to read in a single batch"
    )

    # Metadata
    site_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Site identifier"
    )
    area_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Area identifier"
    )
    line_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Production line identifier"
    )
    machine_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of machine (e.g., Assembly Line, CNC Mill)"
    )
    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        default="Rockwell Automation"
    )
    model = models.CharField(
        max_length=100,
        blank=True,
        help_text="PLC model number"
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Physical location (e.g., Building A - Floor 2)"
    )

    # Status
    last_connection_test = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time connection was tested"
    )
    connection_status = models.CharField(
        max_length=20,
        default='unknown',
        help_text="Current connection status"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "PLC Connection"
        verbose_name_plural = "PLC Connections"

    def __str__(self):
        return f"{self.name} ({self.plc_family})"

    def clean(self):
        """Validate the configuration"""
        super().clean()

        # Validate IP address format
        if not self.ip_address:
            raise ValidationError({'ip_address': 'IP address is required'})

        # Ensure polling interval is reasonable
        if self.polling_interval_ms < 100:
            raise ValidationError({
                'polling_interval_ms': 'Polling interval must be at least 100ms'
            })

    def to_json_config(self):
        """Export to JSON configuration format"""
        return {
            'name': self.name,
            'type': self.plc_type,
            'family': self.plc_family,
            'enabled': self.enabled,
            'connection': {
                'ip_address': self.ip_address,
                'port': self.port,
                'slot': self.slot,
                'timeout': self.timeout,
                'simulator_mode': self.simulator_mode,
            },
            'polling': {
                'interval_ms': self.polling_interval_ms,
                'batch_size': self.batch_size,
            },
            'metadata': {
                'site_id': self.site_id,
                'area_id': self.area_id,
                'line_id': self.line_id,
                'machine_type': self.machine_type,
                'manufacturer': self.manufacturer,
                'model': self.model,
                'location': self.location,
            },
            'tags': [tag.to_json_config() for tag in self.tags.all()]
        }


class PLCTag(models.Model):
    """PLC Tag Configuration"""

    DATA_TYPES = [
        ('BOOL', 'Boolean (BOOL)'),
        ('SINT', 'Short Integer (SINT)'),
        ('INT', 'Integer (INT)'),
        ('DINT', 'Double Integer (DINT)'),
        ('LINT', 'Long Integer (LINT)'),
        ('REAL', 'Real (REAL)'),
        ('LREAL', 'Long Real (LREAL)'),
        ('STRING', 'String (STRING)'),
    ]

    connection = models.ForeignKey(
        PLCConnection,
        on_delete=models.CASCADE,
        related_name='tags'
    )

    # Tag Configuration
    name = models.CharField(
        max_length=100,
        help_text="Friendly name for this tag"
    )
    address = models.CharField(
        max_length=200,
        help_text="PLC tag address (e.g., Program:MainProgram.ProductionCount)"
    )
    data_type = models.CharField(
        max_length=10,
        choices=DATA_TYPES,
        default='INT',
        help_text="Data type of the tag"
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Description of what this tag represents"
    )

    # Sparkplug Mapping
    sparkplug_metric = models.CharField(
        max_length=100,
        blank=True,
        help_text="Sparkplug B metric name (e.g., production_count)"
    )

    # Optional Settings
    units = models.CharField(
        max_length=20,
        blank=True,
        help_text="Engineering units (e.g., %, seconds, parts)"
    )
    scale_factor = models.FloatField(
        default=1.0,
        help_text="Multiply tag value by this factor"
    )
    offset = models.FloatField(
        default=0.0,
        help_text="Add this offset to tag value after scaling"
    )

    # Display Order
    sort_order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers first)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['connection', 'sort_order', 'name']
        unique_together = [['connection', 'name']]
        verbose_name = "PLC Tag"
        verbose_name_plural = "PLC Tags"

    def __str__(self):
        return f"{self.connection.name} - {self.name}"

    def clean(self):
        """Validate tag configuration"""
        super().clean()

        if not self.address:
            raise ValidationError({'address': 'Tag address is required'})

    def to_json_config(self):
        """Export to JSON configuration format"""
        config = {
            'name': self.name,
            'address': self.address,
            'data_type': self.data_type,
        }

        if self.description:
            config['description'] = self.description
        if self.sparkplug_metric:
            config['sparkplug_metric'] = self.sparkplug_metric
        if self.units:
            config['units'] = self.units
        if self.scale_factor != 1.0:
            config['scale_factor'] = self.scale_factor
        if self.offset != 0.0:
            config['offset'] = self.offset

        return config


class PLCConnectionTemplate(models.Model):
    """Pre-configured templates for common PLC setups"""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Template name (e.g., 'Standard Assembly Line')"
    )
    description = models.TextField(
        help_text="Description of this template"
    )
    plc_type = models.CharField(
        max_length=20,
        choices=PLCConnection.PLC_TYPES,
    )
    plc_family = models.CharField(
        max_length=20,
        choices=PLCConnection.PLC_FAMILIES,
    )

    # Default settings
    default_port = models.IntegerField(default=44818)
    default_slot = models.IntegerField(default=0)
    default_timeout = models.FloatField(default=5.0)
    default_polling_interval = models.IntegerField(default=1000)

    # Template tags (stored as JSON)
    template_tags = models.JSONField(
        default=list,
        help_text="List of standard tags for this template"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "PLC Connection Template"
        verbose_name_plural = "PLC Connection Templates"

    def __str__(self):
        return self.name

    def apply_to_connection(self, connection):
        """Apply this template to a PLC connection"""
        connection.plc_type = self.plc_type
        connection.plc_family = self.plc_family
        connection.port = self.default_port
        connection.slot = self.default_slot
        connection.timeout = self.default_timeout
        connection.polling_interval_ms = self.default_polling_interval
        connection.save()

        # Create tags from template
        for tag_config in self.template_tags:
            PLCTag.objects.create(
                connection=connection,
                name=tag_config['name'],
                address=tag_config.get('address', ''),
                data_type=tag_config.get('data_type', 'INT'),
                description=tag_config.get('description', ''),
                sparkplug_metric=tag_config.get('sparkplug_metric', ''),
                units=tag_config.get('units', ''),
            )
