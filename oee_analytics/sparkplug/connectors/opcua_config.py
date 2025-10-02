"""
OPC-UA Configuration Management
Handles YAML/JSON configuration files and environment variables
Provides tag mapping and discovery functionality
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging

from pydantic import BaseModel, Field, validator
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OPCUATagMapping(BaseModel):
    """Mapping between OPC-UA nodes and Sparkplug metrics"""
    opcua_node_id: str = Field(..., description="OPC-UA Node ID")
    sparkplug_metric_name: str = Field(..., description="Sparkplug metric name")
    display_name: str = Field(..., description="Human-readable name")

    # Data processing
    data_type: str = Field(default="REAL", description="Data type")
    scale_factor: float = Field(default=1.0, description="Scale factor")
    offset: float = Field(default=0.0, description="Offset value")
    unit: Optional[str] = Field(None, description="Engineering unit")

    # Subscription settings
    sampling_interval_ms: int = Field(default=250, ge=50, le=10000)
    deadband_type: int = Field(default=1, ge=0, le=2)  # 0=None, 1=Absolute, 2=Percent
    deadband_value: float = Field(default=0.0, ge=0.0)

    # OEE mapping
    oee_metric_type: Optional[str] = Field(None, description="OEE metric type")
    machine_id: Optional[str] = Field(None, description="Machine identifier")
    line_id: Optional[str] = Field(None, description="Production line ID")


class OPCUAServerConfig(BaseModel):
    """Configuration for an OPC-UA server connection"""
    id: str = Field(..., description="Unique server identifier")
    name: str = Field(..., description="Server display name")
    endpoint_url: str = Field(..., description="OPC-UA endpoint URL")
    enabled: bool = Field(default=True)

    # Security
    security_mode: str = Field(default="SignAndEncrypt", description="None, Sign, SignAndEncrypt")
    security_policy: str = Field(default="Basic256Sha256")
    auth_mode: str = Field(default="Certificate", description="Anonymous, UsernamePassword, Certificate")

    # Credentials
    username: Optional[str] = Field(None)
    password: Optional[str] = Field(None)

    # Certificates
    client_cert_path: Optional[str] = Field(None)
    client_key_path: Optional[str] = Field(None)
    server_cert_path: Optional[str] = Field(None)

    # Connection settings
    session_timeout_ms: int = Field(default=30000, ge=5000)
    keep_alive_interval_ms: int = Field(default=10000, ge=1000)
    reconnect_interval_s: int = Field(default=5, ge=1)
    max_reconnect_attempts: int = Field(default=-1)  # -1 = infinite

    # Subscription settings
    publishing_interval_ms: int = Field(default=250, ge=50)
    max_notifications_per_publish: int = Field(default=1000, ge=1)

    # Performance
    max_concurrent_reads: int = Field(default=100, ge=1)
    batch_read_size: int = Field(default=50, ge=1)

    # Tag mappings
    tags: List[OPCUATagMapping] = Field(default_factory=list)

    @validator('endpoint_url')
    def validate_endpoint_url(cls, v):
        if not v.startswith('opc.tcp://'):
            raise ValueError('Endpoint URL must start with opc.tcp://')
        return v


class OPCUAConfigManager:
    """Manages OPC-UA configuration from files and environment"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("config/opcua_config.yaml")
        self.servers: Dict[str, OPCUAServerConfig] = {}
        self.tag_mappings: Dict[str, List[OPCUATagMapping]] = {}
        self.canonical_mappings: Dict[str, str] = {}  # opcua_node -> canonical_name

    def load_config(self, config_file: Optional[str] = None) -> bool:
        """Load configuration from YAML/JSON file"""
        config_path = Path(config_file) if config_file else self.config_path

        if not config_path.exists():
            logger.warning(f"Configuration file not found: {config_path}")
            return False

        try:
            with open(config_path, 'r') as f:
                if config_path.suffix in ['.yml', '.yaml']:
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)

            # Load servers
            for server_config in config_data.get('opcua_servers', []):
                server = OPCUAServerConfig(**server_config)
                self.servers[server.id] = server
                self.tag_mappings[server.id] = server.tags

                # Build canonical mappings
                for tag in server.tags:
                    self.canonical_mappings[tag.opcua_node_id] = tag.sparkplug_metric_name

            logger.info(f"Loaded {len(self.servers)} OPC-UA server configurations")
            return True

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False

    def save_config(self, config_file: Optional[str] = None) -> bool:
        """Save configuration to file"""
        config_path = Path(config_file) if config_file else self.config_path

        try:
            config_data = {
                'opcua_servers': [
                    server.dict() for server in self.servers.values()
                ]
            }

            # Create directory if needed
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, 'w') as f:
                if config_path.suffix in ['.yml', '.yaml']:
                    yaml.dump(config_data, f, default_flow_style=False)
                else:
                    json.dump(config_data, f, indent=2)

            logger.info(f"Saved configuration to {config_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def get_server_config(self, server_id: str) -> Optional[OPCUAServerConfig]:
        """Get configuration for a specific server"""
        return self.servers.get(server_id)

    def get_tag_mapping(self, server_id: str, opcua_node_id: str) -> Optional[OPCUATagMapping]:
        """Get tag mapping for a specific OPC-UA node"""
        if server_id not in self.tag_mappings:
            return None

        for tag in self.tag_mappings[server_id]:
            if tag.opcua_node_id == opcua_node_id:
                return tag

        return None

    def add_discovered_tag(self, server_id: str, node_id: str, display_name: str,
                          data_type: str = "REAL", oee_type: Optional[str] = None) -> bool:
        """Add a discovered tag to configuration"""
        if server_id not in self.servers:
            return False

        # Generate Sparkplug metric name
        sparkplug_name = self._generate_sparkplug_name(server_id, display_name)

        # Create tag mapping
        tag = OPCUATagMapping(
            opcua_node_id=node_id,
            sparkplug_metric_name=sparkplug_name,
            display_name=display_name,
            data_type=data_type,
            oee_metric_type=oee_type
        )

        # Add to server
        self.servers[server_id].tags.append(tag)
        self.tag_mappings[server_id].append(tag)
        self.canonical_mappings[node_id] = sparkplug_name

        return True

    def _generate_sparkplug_name(self, server_id: str, display_name: str) -> str:
        """Generate Sparkplug metric name from display name"""
        # Clean and format name
        name = display_name.replace(' ', '_').replace('.', '_').lower()
        return f"{server_id}/{name}"

    def load_from_environment(self) -> bool:
        """Load configuration from environment variables"""
        try:
            # Check for OPC-UA environment variables
            servers_json = os.getenv('OPCUA_SERVERS')
            if servers_json:
                servers_data = json.loads(servers_json)
                for server_config in servers_data:
                    server = OPCUAServerConfig(**server_config)
                    self.servers[server.id] = server
                    self.tag_mappings[server.id] = server.tags

            # Individual server from env
            endpoint = os.getenv('OPCUA_ENDPOINT_URL')
            if endpoint:
                server = OPCUAServerConfig(
                    id="env_server",
                    name="Environment Server",
                    endpoint_url=endpoint,
                    username=os.getenv('OPCUA_USERNAME'),
                    password=os.getenv('OPCUA_PASSWORD'),
                    security_mode=os.getenv('OPCUA_SECURITY_MODE', 'SignAndEncrypt'),
                    auth_mode=os.getenv('OPCUA_AUTH_MODE', 'UsernamePassword')
                )
                self.servers["env_server"] = server

            return len(self.servers) > 0

        except Exception as e:
            logger.error(f"Error loading from environment: {e}")
            return False


class CertificateManager:
    """Manages OPC-UA certificates and PKI"""

    def __init__(self, cert_dir: str = "certs/opcua"):
        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    def generate_self_signed_cert(self, common_name: str,
                                  valid_days: int = 365) -> tuple[str, str]:
        """Generate self-signed certificate and key"""

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OEE Dashboard"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=valid_days)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName(common_name),
            ]),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).sign(private_key, hashes.SHA256(), backend=default_backend())

        # Save certificate
        cert_path = self.cert_dir / f"{common_name}.crt"
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Save private key
        key_path = self.cert_dir / f"{common_name}.key"
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        logger.info(f"Generated certificate: {cert_path}")
        return str(cert_path), str(key_path)

    def load_certificate(self, cert_path: str) -> Optional[x509.Certificate]:
        """Load certificate from file"""
        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
                return cert
        except Exception as e:
            logger.error(f"Error loading certificate: {e}")
            return None

    def validate_certificate(self, cert_path: str) -> bool:
        """Validate certificate is not expired"""
        cert = self.load_certificate(cert_path)
        if not cert:
            return False

        now = datetime.utcnow()
        return cert.not_valid_before <= now <= cert.not_valid_after

    def get_certificate_info(self, cert_path: str) -> Dict[str, Any]:
        """Get certificate information"""
        cert = self.load_certificate(cert_path)
        if not cert:
            return {}

        return {
            'subject': cert.subject.rfc4514_string(),
            'issuer': cert.issuer.rfc4514_string(),
            'serial_number': str(cert.serial_number),
            'not_before': cert.not_valid_before.isoformat(),
            'not_after': cert.not_valid_after.isoformat(),
            'signature_algorithm': cert.signature_algorithm_oid.dotted_string,
            'version': cert.version.name,
        }


def create_default_config() -> Dict[str, Any]:
    """Create default OPC-UA configuration"""
    return {
        'opcua_servers': [
            {
                'id': 'demo_server',
                'name': 'Demo OPC-UA Server',
                'endpoint_url': 'opc.tcp://localhost:4840',
                'enabled': True,
                'security_mode': 'None',
                'auth_mode': 'Anonymous',
                'publishing_interval_ms': 500,
                'tags': [
                    {
                        'opcua_node_id': 'ns=2;i=1001',
                        'sparkplug_metric_name': 'demo/temperature',
                        'display_name': 'Temperature',
                        'data_type': 'REAL',
                        'unit': '°C',
                        'sampling_interval_ms': 1000,
                        'deadband_type': 1,
                        'deadband_value': 0.5,
                        'oee_metric_type': 'TEMPERATURE'
                    },
                    {
                        'opcua_node_id': 'ns=2;i=1002',
                        'sparkplug_metric_name': 'demo/pressure',
                        'display_name': 'Pressure',
                        'data_type': 'REAL',
                        'unit': 'bar',
                        'sampling_interval_ms': 1000,
                        'deadband_type': 1,
                        'deadband_value': 0.1,
                        'oee_metric_type': 'PRESSURE'
                    },
                    {
                        'opcua_node_id': 'ns=2;i=1003',
                        'sparkplug_metric_name': 'demo/cycle_count',
                        'display_name': 'Cycle Count',
                        'data_type': 'DINT',
                        'sampling_interval_ms': 250,
                        'oee_metric_type': 'CYCLE_COUNT'
                    },
                    {
                        'opcua_node_id': 'ns=2;i=1004',
                        'sparkplug_metric_name': 'demo/good_parts',
                        'display_name': 'Good Parts',
                        'data_type': 'DINT',
                        'sampling_interval_ms': 250,
                        'oee_metric_type': 'PART_COUNT_GOOD'
                    },
                    {
                        'opcua_node_id': 'ns=2;i=1005',
                        'sparkplug_metric_name': 'demo/machine_state',
                        'display_name': 'Machine State',
                        'data_type': 'INT',
                        'sampling_interval_ms': 500,
                        'oee_metric_type': 'MACHINE_STATUS'
                    }
                ]
            }
        ]
    }


# Example usage
if __name__ == "__main__":
    # Create config manager
    config_mgr = OPCUAConfigManager()

    # Load from file or create default
    if not config_mgr.load_config():
        default_config = create_default_config()
        with open("config/opcua_config.yaml", "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)
        config_mgr.load_config()

    # Certificate management
    cert_mgr = CertificateManager()

    # Generate certificates if needed
    for server_id, server in config_mgr.servers.items():
        if server.auth_mode == "Certificate":
            if not server.client_cert_path or not Path(server.client_cert_path).exists():
                cert_path, key_path = cert_mgr.generate_self_signed_cert(server_id)
                server.client_cert_path = cert_path
                server.client_key_path = key_path

    # Save updated config
    config_mgr.save_config()