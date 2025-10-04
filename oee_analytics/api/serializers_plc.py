"""
PLC Configuration Serializers
Handles validation and serialization for machine/PLC configuration
"""
from rest_framework import serializers
from oee_analytics.models.asset_hierarchy import Machine
from typing import Dict, Any
import re


class PLCConnectionSerializer(serializers.ModelSerializer):
    """
    Serializer for PLC connection configuration
    Includes dynamic validation based on protocol type
    """
    # Protocol-specific configuration stored in metadata JSON field
    protocol_config = serializers.JSONField(required=False, default=dict)

    # Connection info
    ip_address = serializers.IPAddressField(required=True)
    port = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=65535)
    protocol = serializers.ChoiceField(choices=[
        ('OPCUA', 'OPC-UA'),
        ('ETHERNET_IP', 'Allen-Bradley EtherNet/IP'),
        ('S7', 'Siemens S7'),
        ('MODBUS', 'Modbus TCP'),
        ('HTTP', 'HTTP/REST'),
        ('MQTT', 'MQTT'),
    ], required=True)

    # Derived fields
    line_name = serializers.CharField(source='cell.line.name', read_only=True, allow_null=True)
    cell_name = serializers.CharField(source='cell.name', read_only=True, allow_null=True)
    full_path = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = [
            'id', 'machine_id', 'name', 'description',
            'manufacturer', 'model', 'serial_number',
            'machine_type', 'ip_address', 'port', 'protocol',
            'protocol_config', 'status', 'active',
            'line_name', 'cell_name', 'full_path',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status', 'machine_id']

    def get_full_path(self, obj):
        """Get full hierarchical path"""
        return obj.get_canonical_path()

    def validate(self, data):
        """Protocol-specific validation"""
        protocol = data.get('protocol')
        protocol_config = data.get('protocol_config', {}) or data.get('metadata', {})
        ip_address = data.get('ip_address')
        port = data.get('port')

        # Validate protocol-specific requirements
        if protocol == 'ETHERNET_IP':
            self._validate_allen_bradley(protocol_config, port)
        elif protocol == 'S7':
            self._validate_siemens_s7(protocol_config, port)
        elif protocol == 'OPCUA':
            self._validate_opcua(protocol_config, ip_address, port)
        elif protocol == 'MODBUS':
            self._validate_modbus(protocol_config, port)

        return data

    def _validate_allen_bradley(self, config: Dict, port: int):
        """Validate Allen-Bradley specific configuration"""
        # Set default port if not provided
        if not port:
            self.initial_data['port'] = 44818

        # Slot validation
        slot = config.get('slot')
        if slot is not None:
            if not isinstance(slot, int) or slot < 0 or slot > 17:
                raise serializers.ValidationError({
                    'protocol_config': {'slot': 'Slot must be between 0 and 17'}
                })

        # PLC family validation
        plc_family = config.get('plc_family')
        valid_families = ['ControlLogix', 'CompactLogix', 'MicroLogix', 'SLC-500', 'PLC-5', 'Micro800']
        if plc_family and plc_family not in valid_families:
            raise serializers.ValidationError({
                'protocol_config': {'plc_family': f'PLC family must be one of: {", ".join(valid_families)}'}
            })

    def _validate_siemens_s7(self, config: Dict, port: int):
        """Validate Siemens S7 specific configuration"""
        # Set default port if not provided
        if not port:
            self.initial_data['port'] = 102

        # Rack validation
        rack = config.get('rack')
        if rack is not None:
            if not isinstance(rack, int) or rack < 0 or rack > 7:
                raise serializers.ValidationError({
                    'protocol_config': {'rack': 'Rack must be between 0 and 7'}
                })

        # Slot validation
        slot = config.get('slot')
        if slot is not None:
            if not isinstance(slot, int) or slot < 0 or slot > 17:
                raise serializers.ValidationError({
                    'protocol_config': {'slot': 'Slot must be between 0 and 17'}
                })

        # PLC type validation
        plc_type = config.get('plc_type')
        valid_types = ['S7-300', 'S7-400', 'S7-1200', 'S7-1500', 'LOGO!', 'ET200SP']
        if plc_type and plc_type not in valid_types:
            raise serializers.ValidationError({
                'protocol_config': {'plc_type': f'PLC type must be one of: {", ".join(valid_types)}'}
            })

    def _validate_opcua(self, config: Dict, ip_address: str, port: int):
        """Validate OPC-UA specific configuration"""
        # Set default port if not provided
        if not port:
            self.initial_data['port'] = 4840

        # Endpoint URL validation (optional override)
        endpoint_url = config.get('endpoint_url')
        if endpoint_url:
            if not endpoint_url.startswith('opc.tcp://'):
                raise serializers.ValidationError({
                    'protocol_config': {'endpoint_url': 'OPC-UA endpoint must start with opc.tcp://'}
                })

        # Security policy validation
        security_policy = config.get('security_policy')
        valid_policies = ['None', 'Basic256', 'Basic256Sha256', 'Aes128_Sha256_RsaOaep', 'Aes256_Sha256_RsaPss']
        if security_policy and security_policy not in valid_policies:
            raise serializers.ValidationError({
                'protocol_config': {'security_policy': f'Security policy must be one of: {", ".join(valid_policies)}'}
            })

        # Message security mode validation
        message_security = config.get('message_security_mode')
        valid_modes = ['None', 'Sign', 'SignAndEncrypt']
        if message_security and message_security not in valid_modes:
            raise serializers.ValidationError({
                'protocol_config': {'message_security_mode': f'Message security mode must be one of: {", ".join(valid_modes)}'}
            })

        # Authentication mode validation
        auth_mode = config.get('authentication_mode')
        valid_auth = ['Anonymous', 'UserPassword', 'Certificate']
        if auth_mode and auth_mode not in valid_auth:
            raise serializers.ValidationError({
                'protocol_config': {'authentication_mode': f'Authentication mode must be one of: {", ".join(valid_auth)}'}
            })

        # If UserPassword auth, require username
        if auth_mode == 'UserPassword' and not config.get('username'):
            raise serializers.ValidationError({
                'protocol_config': {'username': 'Username is required for UserPassword authentication'}
            })

    def _validate_modbus(self, config: Dict, port: int):
        """Validate Modbus TCP specific configuration"""
        # Set default port if not provided
        if not port:
            self.initial_data['port'] = 502

        # Unit ID validation
        unit_id = config.get('unit_id')
        if unit_id is not None:
            if not isinstance(unit_id, int) or unit_id < 0 or unit_id > 255:
                raise serializers.ValidationError({
                    'protocol_config': {'unit_id': 'Unit ID must be between 0 and 255'}
                })

    def create(self, validated_data):
        """Create machine with protocol configuration"""
        from oee_analytics.models.asset_hierarchy import Site, Area, ProductionLine, Cell
        import uuid

        # Move protocol_config to metadata field
        protocol_config = validated_data.pop('protocol_config', {})
        if protocol_config:
            validated_data['metadata'] = {**validated_data.get('metadata', {}), **protocol_config}

        # Auto-create default hierarchy if cell not provided
        if 'cell' not in validated_data or validated_data.get('cell') is None:
            # Get or create default site
            site, _ = Site.objects.get_or_create(
                site_id='UNASSIGNED',
                defaults={
                    'name': 'Unassigned Devices',
                    'description': 'Default site for standalone PLC connections'
                }
            )

            # Get or create default area
            area, _ = Area.objects.get_or_create(
                site=site,
                area_id='UNASSIGNED',
                defaults={
                    'name': 'Unassigned',
                    'description': 'Default area for standalone PLC connections'
                }
            )

            # Get or create default line
            line, _ = ProductionLine.objects.get_or_create(
                area=area,
                line_id='UNASSIGNED',
                defaults={
                    'name': 'Unassigned',
                    'description': 'Default line for standalone PLC connections'
                }
            )

            # Get or create default cell
            cell, _ = Cell.objects.get_or_create(
                line=line,
                cell_id='UNASSIGNED',
                defaults={
                    'name': 'Unassigned',
                    'description': 'Default cell for standalone PLC connections',
                    'sequence_order': 1
                }
            )

            validated_data['cell'] = cell

        # Auto-generate machine_id if not provided
        if 'machine_id' not in validated_data or not validated_data.get('machine_id'):
            # Create machine_id from name or IP address
            base_id = validated_data.get('name', '').upper().replace(' ', '_')
            if not base_id:
                base_id = f"PLC_{validated_data['ip_address'].replace('.', '_')}"

            # Ensure uniqueness
            machine_id = base_id
            counter = 1
            while Machine.objects.filter(cell=validated_data['cell'], machine_id=machine_id).exists():
                machine_id = f"{base_id}_{counter}"
                counter += 1

            validated_data['machine_id'] = machine_id

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update machine with protocol configuration"""
        # Merge protocol_config into metadata
        protocol_config = validated_data.pop('protocol_config', {})
        if protocol_config:
            instance.metadata = {**instance.metadata, **protocol_config}

        return super().update(instance, validated_data)


class PLCConnectionTestSerializer(serializers.Serializer):
    """Serializer for testing PLC connections without saving"""
    ip_address = serializers.IPAddressField(required=True)
    port = serializers.IntegerField(required=True, min_value=1, max_value=65535)
    protocol = serializers.CharField(required=True)
    protocol_config = serializers.JSONField(required=False, default=dict)
    timeout = serializers.FloatField(default=5.0, min_value=1.0, max_value=30.0)


class PLCTagDefinitionSerializer(serializers.Serializer):
    """Serializer for PLC tag definitions"""
    name = serializers.CharField(max_length=200)
    address = serializers.CharField(max_length=500)
    data_type = serializers.CharField(max_length=50)
    description = serializers.CharField(required=False, allow_blank=True)
    units = serializers.CharField(required=False, allow_blank=True, max_length=20)
    scaling_factor = serializers.FloatField(default=1.0)
    scaling_offset = serializers.FloatField(default=0.0)
    min_value = serializers.FloatField(required=False, allow_null=True)
    max_value = serializers.FloatField(required=False, allow_null=True)
    sampling_interval_ms = serializers.IntegerField(default=1000, min_value=100)


class PLCTagDiscoverySerializer(serializers.Serializer):
    """Serializer for tag discovery requests"""
    machine_id = serializers.CharField(required=True)
    filter_pattern = serializers.CharField(required=False, allow_blank=True)
    max_tags = serializers.IntegerField(default=1000, min_value=1, max_value=10000)
