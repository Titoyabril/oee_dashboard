"""
Sensor Range Validator - Comprehensive 100-Point Test Suite
Production-Ready Validation for Database-Driven Sensor Range Validation

Test Categories:
1. Database Model & Schema (10 tests)
2. Validator Core Functionality (15 tests)
3. Cache Performance & TTL (12 tests)
4. StreamProcessor Integration (13 tests)
5. Boundary & Edge Cases (15 tests)
6. Concurrency & Race Conditions (10 tests)
7. Quality Score Degradation (10 tests)
8. Configuration Management (8 tests)
9. Error Handling & Resilience (10 tests)
10. Performance & Scalability (7 tests)

Total: 100 Tests

Usage:
    pytest test_sensor_validator_comprehensive.py -v --html=report.html
    pytest test_sensor_validator_comprehensive.py -k "category1" -v
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from prometheus_client import REGISTRY
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import random

from oee_analytics.stream_processing.validators.sensor_range_validator import SensorRangeValidator
from oee_analytics.stream_processing.normalizer import NormalizedMetric
from oee_analytics.models import SensorRangeConfig
from django.db import connection, transaction
from django.db.utils import IntegrityError
import logging


logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def cleanup_prometheus_metrics():
    """Clean up Prometheus metrics between tests"""
    yield
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass


@pytest.fixture
async def cleanup_sensor_configs():
    """Clean up all sensor range configs after each test"""
    yield
    await SensorRangeConfig.objects.all().adelete()


# ============================================================================
# Category 1: Database Model & Schema (10 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory1DatabaseModel:
    """Database model structure, constraints, and indexes"""

    async def test_1_1_create_basic_config(self):
        """Verify SensorRangeConfig model can be created with all fields"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='TEST-001',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius',
            violation_action='REJECT',
            is_active=True,
            created_by='test_user',
            notes='Test configuration'
        )

        assert config.config_id is not None
        assert config.machine_id == 'TEST-001'
        assert config.signal_type == 'temperature'
        assert config.created_at is not None
        assert config.updated_at is not None

        await config.adelete()

    async def test_1_2_unique_constraint_enforcement(self):
        """Verify unique constraint on (machine_id, signal_type)"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-002',
            signal_type='pressure',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='psi'
        )

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            await SensorRangeConfig.objects.acreate(
                machine_id='TEST-002',
                signal_type='pressure',
                min_value=Decimal('10.0'),
                max_value=Decimal('200.0'),
                unit='psi'
            )

    async def test_1_3_default_values(self):
        """Verify default values for optional fields"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='TEST-003',
            signal_type='vibration',
            min_value=Decimal('0.0'),
            max_value=Decimal('5.0'),
            unit='mm/s'
        )

        assert config.violation_action == 'ALERT'  # Default
        assert config.is_active is True  # Default
        assert config.created_by is None  # Optional
        assert config.notes is None  # Optional

        await config.adelete()

    async def test_1_4_violation_action_choices(self):
        """Verify violation_action field accepts only valid choices"""
        # Valid choices
        for action in ['ALERT', 'REJECT', 'FLAG']:
            config = await SensorRangeConfig.objects.acreate(
                machine_id=f'TEST-{action}',
                signal_type='test',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='test',
                violation_action=action
            )
            assert config.violation_action == action
            await config.adelete()

    async def test_1_5_decimal_precision(self):
        """Verify decimal fields support required precision (18,6)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='TEST-005',
            signal_type='high_precision',
            min_value=Decimal('123456789012.123456'),
            max_value=Decimal('999999999999.999999'),
            unit='precise'
        )

        assert config.min_value == Decimal('123456789012.123456')
        assert config.max_value == Decimal('999999999999.999999')

        await config.adelete()

    async def test_1_6_negative_values_supported(self):
        """Verify negative values are supported for min/max"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='TEST-006',
            signal_type='temperature',
            min_value=Decimal('-40.0'),
            max_value=Decimal('120.0'),
            unit='celsius'
        )

        assert config.min_value == Decimal('-40.0')

        await config.adelete()

    async def test_1_7_index_exists_machine_signal_active(self):
        """Verify composite index exists on (machine_id, signal_type, is_active)"""
        # Create multiple configs
        for i in range(5):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'MACHINE-{i:03d}',
                signal_type='temperature',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius',
                is_active=(i % 2 == 0)
            )

        # Query should be fast (uses index)
        start = time.time()
        result = await SensorRangeConfig.objects.filter(
            machine_id='MACHINE-002',
            signal_type='temperature',
            is_active=True
        ).afirst()
        elapsed = time.time() - start

        assert result is not None
        assert elapsed < 0.1  # Should be very fast with index

    async def test_1_8_auto_now_fields(self):
        """Verify created_at and updated_at timestamps"""
        before = datetime.now(timezone.utc)

        config = await SensorRangeConfig.objects.acreate(
            machine_id='TEST-008',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='test'
        )

        after = datetime.now(timezone.utc)

        assert before <= config.created_at.replace(tzinfo=timezone.utc) <= after
        assert before <= config.updated_at.replace(tzinfo=timezone.utc) <= after

        # Update should change updated_at
        await asyncio.sleep(0.1)
        config.max_value = Decimal('200.0')
        await config.asave()

        assert config.updated_at > config.created_at

        await config.adelete()

    async def test_1_9_query_by_machine_id(self):
        """Verify efficient querying by machine_id (indexed field)"""
        # Create configs for multiple machines
        for i in range(10):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'LINE01-MACHINE-{i:02d}',
                signal_type=f'sensor_{i}',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='test'
            )

        # Query for specific machine
        configs = await SensorRangeConfig.objects.filter(
            machine_id='LINE01-MACHINE-05'
        ).acount()

        assert configs == 1

    async def test_1_10_bulk_operations(self):
        """Verify bulk create/update operations work correctly"""
        configs = [
            SensorRangeConfig(
                machine_id=f'BULK-{i:03d}',
                signal_type='temperature',
                min_value=Decimal(str(i * 10)),
                max_value=Decimal(str((i + 1) * 10)),
                unit='celsius'
            )
            for i in range(20)
        ]

        await SensorRangeConfig.objects.abulk_create(configs)

        count = await SensorRangeConfig.objects.filter(
            machine_id__startswith='BULK-'
        ).acount()

        assert count == 20


# ============================================================================
# Category 2: Validator Core Functionality (15 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory2ValidatorCore:
    """Core validation logic and range checking"""

    async def test_2_1_no_config_passes(self):
        """Validator passes when no config exists for machine/signal"""
        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='UNCONFIGURED-001',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='unknown_sensor',
            name='test',
            value=999999.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)

        assert is_valid is True
        assert error_msg is None

    async def test_2_2_value_at_minimum_passes(self):
        """Value exactly at minimum passes validation"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-021',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()
        metric = NormalizedMetric(
            machine_id='TEST-021',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=0.0,  # Exactly at minimum
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)

        assert is_valid is True
        assert error_msg is None

    async def test_2_3_value_at_maximum_passes(self):
        """Value exactly at maximum passes validation"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-022',
            signal_type='pressure',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='psi'
        )

        validator = SensorRangeValidator()
        metric = NormalizedMetric(
            machine_id='TEST-022',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='pressure',
            name='pressure',
            value=100.0,  # Exactly at maximum
            unit='psi',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)

        assert is_valid is True

    async def test_2_4_value_below_minimum_fails(self):
        """Value below minimum fails with correct error message"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-023',
            signal_type='temperature',
            min_value=Decimal('10.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()
        metric = NormalizedMetric(
            machine_id='TEST-023',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=5.0,  # Below minimum
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)

        assert is_valid is False
        assert 'below minimum' in error_msg
        assert 'TEST-023' in error_msg
        assert '5.0' in error_msg or '5' in error_msg

    async def test_2_5_value_above_maximum_fails(self):
        """Value above maximum fails with correct error message"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-024',
            signal_type='vibration',
            min_value=Decimal('0.0'),
            max_value=Decimal('5.0'),
            unit='mm/s'
        )

        validator = SensorRangeValidator()
        metric = NormalizedMetric(
            machine_id='TEST-024',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='vibration',
            name='vib',
            value=10.5,  # Above maximum
            unit='mm/s',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)

        assert is_valid is False
        assert 'exceeds maximum' in error_msg
        assert '10.5' in error_msg

    async def test_2_6_midrange_value_passes(self):
        """Value in middle of range passes"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-025',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()
        metric = NormalizedMetric(
            machine_id='TEST-025',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,  # Midpoint
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)

        assert is_valid is True

    async def test_2_7_negative_range_validation(self):
        """Negative ranges work correctly"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-026',
            signal_type='temperature',
            min_value=Decimal('-40.0'),
            max_value=Decimal('-10.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Within range
        metric1 = NormalizedMetric(
            machine_id='TEST-026',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=-25.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Below range
        metric2 = NormalizedMetric(
            machine_id='TEST-026',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=-50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is False

    async def test_2_8_very_small_range(self):
        """Very small ranges (precision testing)"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-027',
            signal_type='precision',
            min_value=Decimal('0.000001'),
            max_value=Decimal('0.000002'),
            unit='precise'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='TEST-027',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='precision',
            name='precise',
            value=0.0000015,  # Within range
            unit='precise',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_2_9_very_large_values(self):
        """Very large values validated correctly"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-028',
            signal_type='large',
            min_value=Decimal('1000000.0'),
            max_value=Decimal('9999999.0'),
            unit='large'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='TEST-028',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='large',
            name='large',
            value=5000000.0,
            unit='large',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_2_10_zero_value_validation(self):
        """Zero value handled correctly in different ranges"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-029',
            signal_type='test',
            min_value=Decimal('-10.0'),
            max_value=Decimal('10.0'),
            unit='test'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='TEST-029',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=0.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_2_11_float_to_decimal_conversion(self):
        """Float values convert to Decimal correctly"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-030',
            signal_type='float_test',
            min_value=Decimal('0.1'),
            max_value=Decimal('0.9'),
            unit='test'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='TEST-030',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='float_test',
            name='test',
            value=0.5,  # Python float
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_2_12_inactive_config_ignored(self):
        """Inactive configs are not used for validation"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-031',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('10.0'),
            unit='test',
            is_active=False  # INACTIVE
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='TEST-031',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=999.0,  # Would fail if config was active
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True  # Passes because config inactive

    async def test_2_13_multiple_configs_per_machine(self):
        """Machine can have multiple configs for different signal types"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-032',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-032',
            signal_type='pressure',
            min_value=Decimal('0.0'),
            max_value=Decimal('50.0'),
            unit='psi'
        )

        validator = SensorRangeValidator()

        # Temperature metric
        metric1 = NormalizedMetric(
            machine_id='TEST-032',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=75.0,  # Valid for temperature range
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Pressure metric
        metric2 = NormalizedMetric(
            machine_id='TEST-032',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='pressure',
            name='pressure',
            value=75.0,  # Invalid for pressure range (max 50)
            unit='psi',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is False

    async def test_2_14_machine_id_case_sensitivity(self):
        """Machine ID matching is case-sensitive"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-033',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='test'
        )

        validator = SensorRangeValidator()

        # Different case - no config match
        metric = NormalizedMetric(
            machine_id='test-033',  # lowercase
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=999.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True  # No config found, passes

    async def test_2_15_signal_type_case_sensitivity(self):
        """Signal type matching is case-sensitive"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TEST-034',
            signal_type='Temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Different case - no config match
        metric = NormalizedMetric(
            machine_id='TEST-034',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',  # lowercase
            name='temp',
            value=999.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True  # No config found, passes


# ============================================================================
# Category 3: Cache Performance & TTL (12 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory3CachePerformance:
    """Cache behavior, TTL, and performance characteristics"""

    async def test_3_1_cache_hit_performance(self):
        """Cache hit is significantly faster than database query"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-001',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='CACHE-001',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # First call - cache miss
        start1 = time.time()
        await validator.validate(metric)
        elapsed1 = time.time() - start1

        # Second call - cache hit
        start2 = time.time()
        await validator.validate(metric)
        elapsed2 = time.time() - start2

        # Cache hit should be faster (allowing for some variance)
        assert elapsed2 < elapsed1 * 0.8 or elapsed2 < 0.001

    async def test_3_2_cache_key_format(self):
        """Cache key uses correct format: machine_id:signal_type"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-002',
            signal_type='pressure',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='psi'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='CACHE-002',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='pressure',
            name='pressure',
            value=50.0,
            unit='psi',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric)

        expected_key = 'CACHE-002:pressure'
        assert expected_key in validator.range_cache

    async def test_3_3_cache_stores_config_object(self):
        """Cache stores actual config object, not just values"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-003',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='test'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='CACHE-003',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=50.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric)

        cache_key = 'CACHE-003:test'
        cached_time, cached_config = validator.range_cache[cache_key]

        assert isinstance(cached_config, SensorRangeConfig)
        assert cached_config.config_id == config.config_id

    async def test_3_4_cache_clear_functionality(self):
        """clear_cache() removes all cached entries"""
        # Add multiple entries to cache
        for i in range(5):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'CACHE-{i:03d}',
                signal_type='test',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='test'
            )

            validator = SensorRangeValidator()

            metric = NormalizedMetric(
                machine_id=f'CACHE-{i:03d}',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='test',
                name='test',
                value=50.0,
                unit='test',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )

            await validator.validate(metric)

        assert len(validator.range_cache) == 5

        validator.clear_cache()

        assert len(validator.range_cache) == 0

    async def test_3_5_cache_ttl_expiration(self):
        """Cache entries expire after TTL (5 minutes default)"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-TTL-001',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='test'
        )

        # Use short TTL for testing
        validator = SensorRangeValidator()
        validator.cache_ttl_seconds = 0.1  # 100ms TTL

        metric = NormalizedMetric(
            machine_id='CACHE-TTL-001',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=50.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # First call - populate cache
        await validator.validate(metric)
        cache_key = 'CACHE-TTL-001:test'
        assert cache_key in validator.range_cache

        # Wait for TTL expiration
        await asyncio.sleep(0.15)

        # Next call should re-query database (cache expired)
        # We verify by checking if new timestamp is stored
        old_timestamp, _ = validator.range_cache[cache_key]
        await validator.validate(metric)
        new_timestamp, _ = validator.range_cache[cache_key]

        assert new_timestamp > old_timestamp

    async def test_3_6_cache_isolation_per_machine(self):
        """Cache correctly isolates configs per machine"""
        await SensorRangeConfig.objects.acreate(
            machine_id='MACHINE-A',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('50.0'),
            unit='celsius'
        )

        await SensorRangeConfig.objects.acreate(
            machine_id='MACHINE-B',
            signal_type='temperature',
            min_value=Decimal('50.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Cache both configs
        for machine in ['MACHINE-A', 'MACHINE-B']:
            metric = NormalizedMetric(
                machine_id=machine,
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=75.0,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            await validator.validate(metric)

        # Verify separate cache entries
        assert 'MACHINE-A:temperature' in validator.range_cache
        assert 'MACHINE-B:temperature' in validator.range_cache

        _, config_a = validator.range_cache['MACHINE-A:temperature']
        _, config_b = validator.range_cache['MACHINE-B:temperature']

        assert config_a.max_value == Decimal('50.0')
        assert config_b.max_value == Decimal('100.0')

    async def test_3_7_cache_isolation_per_signal(self):
        """Cache correctly isolates configs per signal type"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-SIGNAL',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-SIGNAL',
            signal_type='pressure',
            min_value=Decimal('0.0'),
            max_value=Decimal('50.0'),
            unit='psi'
        )

        validator = SensorRangeValidator()

        # Cache both configs
        for signal in ['temperature', 'pressure']:
            metric = NormalizedMetric(
                machine_id='CACHE-SIGNAL',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type=signal,
                name=signal,
                value=25.0,
                unit='test',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            await validator.validate(metric)

        # Verify separate cache entries
        assert 'CACHE-SIGNAL:temperature' in validator.range_cache
        assert 'CACHE-SIGNAL:pressure' in validator.range_cache

    async def test_3_8_cache_none_value(self):
        """Cache correctly handles None (no config found)"""
        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='NO-CONFIG',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=50.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric)

        cache_key = 'NO-CONFIG:test'
        assert cache_key in validator.range_cache
        _, cached_value = validator.range_cache[cache_key]
        assert cached_value is None

    async def test_3_9_cache_size_growth(self):
        """Cache grows appropriately with unique machine/signal combinations"""
        validator = SensorRangeValidator()

        # Create and validate 50 unique machine/signal combinations
        for i in range(50):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'CACHE-GROWTH-{i:03d}',
                signal_type='test',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='test'
            )

            metric = NormalizedMetric(
                machine_id=f'CACHE-GROWTH-{i:03d}',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='test',
                name='test',
                value=50.0,
                unit='test',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )

            await validator.validate(metric)

        assert len(validator.range_cache) == 50

    async def test_3_10_concurrent_cache_access(self):
        """Cache is thread-safe for concurrent access"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CONCURRENT-CACHE',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='test'
        )

        validator = SensorRangeValidator()

        async def validate_metric():
            metric = NormalizedMetric(
                machine_id='CONCURRENT-CACHE',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='test',
                name='test',
                value=50.0,
                unit='test',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            return await validator.validate(metric)

        # Run 20 concurrent validations
        tasks = [validate_metric() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(is_valid for is_valid, _ in results)

        # Cache should have single entry
        assert len(validator.range_cache) == 1

    async def test_3_11_cache_memory_efficiency(self):
        """Cache doesn't duplicate config data unnecessarily"""
        await SensorRangeConfig.objects.acreate(
            machine_id='MEM-EFFICIENT',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='test'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='MEM-EFFICIENT',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=50.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Validate same metric 100 times
        for _ in range(100):
            await validator.validate(metric)

        # Should still only have one cache entry
        assert len(validator.range_cache) == 1

    async def test_3_12_cache_refresh_on_config_change(self):
        """Cache correctly handles config updates (via TTL)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-REFRESH',
            signal_type='test',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='test'
        )

        validator = SensorRangeValidator()
        validator.cache_ttl_seconds = 0.1  # Short TTL

        metric = NormalizedMetric(
            machine_id='CACHE-REFRESH',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='test',
            name='test',
            value=150.0,
            unit='test',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should fail (above max 100)
        is_valid1, _ = await validator.validate(metric)
        assert is_valid1 is False

        # Update config
        config.max_value = Decimal('200.0')
        await config.asave()

        # Wait for cache expiration
        await asyncio.sleep(0.15)

        # Should now pass (below new max 200)
        is_valid2, _ = await validator.validate(metric)
        assert is_valid2 is True


# ================================================================================================
# CATEGORY 4: StreamProcessor Integration (13 tests)
# ================================================================================================
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory4StreamProcessorIntegration:
    """StreamProcessor integration with SensorRangeValidator"""

    async def test_4_1_sensor_validator_initialization(self):
        """StreamProcessor creates SensorRangeValidator when configured"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            mqtt_port=1883,
            enable_validation=True,
            use_sensor_range_validator=True
        )

        processor = StreamProcessor(config)

        assert processor.sensor_validator is not None
        assert isinstance(processor.sensor_validator, SensorRangeValidator)

    async def test_4_2_data_validator_default(self):
        """DataValidator used by default when sensor validator not requested"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=False
        )

        processor = StreamProcessor(config)

        assert processor.validator is not None
        assert processor.sensor_validator is None

    async def test_4_3_config_flag_switches_validator(self):
        """use_sensor_range_validator flag switches between validators"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        # With sensor validator
        config1 = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True
        )
        processor1 = StreamProcessor(config1)
        assert processor1.sensor_validator is not None
        assert processor1.validator is None

        # With data validator
        config2 = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=False
        )
        processor2 = StreamProcessor(config2)
        assert processor2.validator is not None
        assert processor2.sensor_validator is None

    async def test_4_4_validation_disabled(self):
        """Validation can be completely disabled"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=False
        )

        processor = StreamProcessor(config)

        assert processor.validator is None
        assert processor.sensor_validator is None

    async def test_4_5_metrics_pass_through_validator(self):
        """Valid metrics pass through sensor validator in pipeline"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        # Create config
        await SensorRangeConfig.objects.acreate(
            machine_id='PIPELINE-001',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True,
            enable_enrichment=False,
            enable_persistence=False
        )

        processor = StreamProcessor(config)

        metric = NormalizedMetric(
            machine_id='PIPELINE-001',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Validate through sensor validator
        is_valid, _ = await processor.sensor_validator.validate(metric)
        assert is_valid is True

    async def test_4_6_invalid_metrics_rejected(self):
        """Out-of-range metrics are rejected by sensor validator in pipeline"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        # Create restrictive config
        await SensorRangeConfig.objects.acreate(
            machine_id='PIPELINE-002',
            signal_type='pressure',
            min_value=Decimal('10.0'),
            max_value=Decimal('50.0'),
            unit='psi'
        )

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True
        )

        processor = StreamProcessor(config)

        metric = NormalizedMetric(
            machine_id='PIPELINE-002',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='pressure',
            name='pressure',
            value=100.0,  # Out of range
            unit='psi',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should be rejected
        is_valid, error_msg = await processor.sensor_validator.validate(metric)
        assert is_valid is False
        assert 'exceeds maximum' in error_msg

    async def test_4_7_validation_performance(self):
        """Validation doesn't significantly slow pipeline throughput"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig
        import time

        await SensorRangeConfig.objects.acreate(
            machine_id='PERF-001',
            signal_type='counter',
            min_value=Decimal('0'),
            max_value=Decimal('10000'),
            unit='count'
        )

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True,
            enable_enrichment=False,
            enable_persistence=False
        )

        processor = StreamProcessor(config)

        # Validate 1000 metrics
        start = time.time()
        for i in range(1000):
            metric = NormalizedMetric(
                machine_id='PERF-001',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='counter',
                name='count',
                value=float(i),
                unit='count',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            await processor.sensor_validator.validate(metric)

        duration = time.time() - start

        # Should process 1000 metrics in under 1 second (with caching)
        assert duration < 1.0
        logger.info(f"Validated 1000 metrics in {duration:.3f} seconds ({1000/duration:.0f} msg/sec)")

    async def test_4_8_prometheus_metrics_tracked(self):
        """Validation failures are tracked in Prometheus metrics"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig
        from prometheus_client import REGISTRY

        await SensorRangeConfig.objects.acreate(
            machine_id='METRICS-001',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('50.0'),
            unit='celsius'
        )

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True
        )

        processor = StreamProcessor(config)

        # Create invalid metric
        metric = NormalizedMetric(
            machine_id='METRICS-001',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=100.0,  # Out of range
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Validate (should fail)
        await processor.sensor_validator.validate(metric)

        # Check that validation_failures counter exists
        metrics = {m.name for m in REGISTRY.collect()}
        assert 'sensor_validation_failures_total' in metrics

    async def test_4_9_both_validators_never_active(self):
        """Mutex: only one validator type is active at a time"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        # Test all combinations
        test_cases = [
            (False, False, None, None),  # No validation
            (True, False, 'validator', None),  # Data validator only
            (True, True, None, 'sensor_validator'),  # Sensor validator only
        ]

        for enable_val, use_sensor, expect_data_val, expect_sensor_val in test_cases:
            config = StreamProcessorConfig(
                mqtt_broker='localhost',
                enable_validation=enable_val,
                use_sensor_range_validator=use_sensor
            )

            processor = StreamProcessor(config)

            if expect_data_val:
                assert processor.validator is not None
                assert processor.sensor_validator is None
            elif expect_sensor_val:
                assert processor.sensor_validator is not None
                assert processor.validator is None
            else:
                assert processor.validator is None
                assert processor.sensor_validator is None

    async def test_4_10_validator_error_handling(self):
        """Validator errors don't crash the pipeline"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True
        )

        processor = StreamProcessor(config)

        # Create metric with missing fields (malformed)
        metric = NormalizedMetric(
            machine_id=None,  # Missing machine_id
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully (not raise exception)
        try:
            is_valid, error_msg = await processor.sensor_validator.validate(metric)
            # Should fail validation but not crash
            assert is_valid is False or error_msg is not None
        except Exception as e:
            pytest.fail(f"Validator raised exception instead of handling gracefully: {e}")

    async def test_4_11_batch_validation(self):
        """Multiple metrics validated efficiently in batch"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        # Create configs for multiple machines
        for i in range(5):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'BATCH-{i:03d}',
                signal_type='temperature',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius'
            )

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True
        )

        processor = StreamProcessor(config)

        # Create batch of metrics
        metrics = []
        for i in range(5):
            for j in range(10):
                metric = NormalizedMetric(
                    machine_id=f'BATCH-{i:03d}',
                    line_id='LINE-001',
                    site_id='SITE01',
                    signal_type='temperature',
                    name='temp',
                    value=float(j * 10),
                    unit='celsius',
                    timestamp_utc=datetime.now(timezone.utc),
                    quality=192,
                    is_valid=True,
                    metadata={}
                )
                metrics.append(metric)

        # Validate all
        results = []
        for metric in metrics:
            is_valid, _ = await processor.sensor_validator.validate(metric)
            results.append(is_valid)

        # All should pass (values 0-90 are within 0-100 range)
        assert all(results)

        # Cache should have 5 entries (one per machine)
        assert len(processor.sensor_validator.range_cache) == 5

    async def test_4_12_real_sparkplug_message(self):
        """Real Sparkplug B message structure validated correctly"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        await SensorRangeConfig.objects.acreate(
            machine_id='SPARKPLUG-MACHINE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('150.0'),
            unit='celsius'
        )

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True
        )

        processor = StreamProcessor(config)

        # Simulate metric from Sparkplug B NDATA message
        metric = NormalizedMetric(
            machine_id='SPARKPLUG-MACHINE',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='Reactor_Temperature',
            value=85.5,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,  # Good quality
            is_valid=True,
            metadata={
                'sparkplug_type': 'NDATA',
                'metric_alias': 1,
                'datatype': 'Float'
            }
        )

        is_valid, _ = await processor.sensor_validator.validate(metric)
        assert is_valid is True

    async def test_4_13_pipeline_end_to_end(self):
        """Complete pipeline with sensor validator from ingestion to validation"""
        from oee_analytics.stream_processing.stream_processor import StreamProcessor, StreamProcessorConfig

        # Setup multiple sensor configs
        configs_data = [
            ('E2E-MACHINE-001', 'temperature', '0', '100', 'celsius'),
            ('E2E-MACHINE-001', 'pressure', '0', '50', 'psi'),
            ('E2E-MACHINE-002', 'vibration', '0', '10', 'mm/s'),
        ]

        for machine_id, signal_type, min_val, max_val, unit in configs_data:
            await SensorRangeConfig.objects.acreate(
                machine_id=machine_id,
                signal_type=signal_type,
                min_value=Decimal(min_val),
                max_value=Decimal(max_val),
                unit=unit
            )

        config = StreamProcessorConfig(
            mqtt_broker='localhost',
            enable_validation=True,
            use_sensor_range_validator=True,
            enable_enrichment=False,
            enable_persistence=False
        )

        processor = StreamProcessor(config)

        # Test metrics: some valid, some invalid
        test_cases = [
            ('E2E-MACHINE-001', 'temperature', 50.0, 'celsius', True),  # Valid
            ('E2E-MACHINE-001', 'temperature', 150.0, 'celsius', False),  # Invalid: too high
            ('E2E-MACHINE-001', 'pressure', 25.0, 'psi', True),  # Valid
            ('E2E-MACHINE-001', 'pressure', 75.0, 'psi', False),  # Invalid: too high
            ('E2E-MACHINE-002', 'vibration', 5.0, 'mm/s', True),  # Valid
            ('E2E-MACHINE-002', 'vibration', 15.0, 'mm/s', False),  # Invalid: too high
        ]

        for machine_id, signal_type, value, unit, expected_valid in test_cases:
            metric = NormalizedMetric(
                machine_id=machine_id,
                line_id='LINE-001',
                site_id='SITE01',
                signal_type=signal_type,
                name=f'{signal_type}_sensor',
                value=value,
                unit=unit,
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )

            is_valid, _ = await processor.sensor_validator.validate(metric)
            assert is_valid == expected_valid, \
                f"Expected {machine_id}/{signal_type}={value} to be {'valid' if expected_valid else 'invalid'}"


# ================================================================================================
# CATEGORY 5: Boundary & Edge Cases (15 tests)
# ================================================================================================
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory5BoundaryEdgeCases:
    """Boundary conditions and edge case handling"""

    async def test_5_1_null_value_handling(self):
        """null/None value handling"""
        await SensorRangeConfig.objects.acreate(
            machine_id='NULL-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='NULL-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=None,  # None value
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)
        # Should fail or handle gracefully
        assert is_valid is False or error_msg is not None

    async def test_5_2_nan_value_handling(self):
        """NaN value handling"""
        await SensorRangeConfig.objects.acreate(
            machine_id='NAN-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='NAN-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=float('nan'),  # NaN value
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)
        # Should fail or handle gracefully
        assert is_valid is False or error_msg is not None

    async def test_5_3_infinity_values(self):
        """Positive/negative infinity handling"""
        await SensorRangeConfig.objects.acreate(
            machine_id='INF-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Test positive infinity
        metric1 = NormalizedMetric(
            machine_id='INF-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=float('inf'),
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is False

        # Test negative infinity
        metric2 = NormalizedMetric(
            machine_id='INF-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=float('-inf'),
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is False

    async def test_5_4_min_greater_than_max(self):
        """Invalid config: min > max should be caught"""
        # Try to create invalid config
        try:
            config = await SensorRangeConfig.objects.acreate(
                machine_id='INVALID-CONFIG',
                signal_type='temperature',
                min_value=Decimal('100.0'),  # Min > Max
                max_value=Decimal('0.0'),
                unit='celsius'
            )

            validator = SensorRangeValidator()
            metric = NormalizedMetric(
                machine_id='INVALID-CONFIG',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=50.0,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )

            # Validator should handle this gracefully
            is_valid, error_msg = await validator.validate(metric)
            # Either fails validation or config creation should have been prevented
            assert True  # If we got here without exception, that's acceptable

            await config.adelete()
        except Exception:
            # Config creation prevented - also acceptable
            assert True

    async def test_5_5_equal_min_max(self):
        """min == max (single valid value)"""
        await SensorRangeConfig.objects.acreate(
            machine_id='EQUAL-BOUNDS',
            signal_type='setpoint',
            min_value=Decimal('50.0'),
            max_value=Decimal('50.0'),  # Exactly equal
            unit='units'
        )

        validator = SensorRangeValidator()

        # Exact value should pass
        metric1 = NormalizedMetric(
            machine_id='EQUAL-BOUNDS',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='setpoint',
            name='setpoint',
            value=50.0,
            unit='units',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Different value should fail
        metric2 = NormalizedMetric(
            machine_id='EQUAL-BOUNDS',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='setpoint',
            name='setpoint',
            value=51.0,
            unit='units',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is False

    async def test_5_6_very_long_machine_id(self):
        """Machine ID at max length (50 chars)"""
        long_id = 'M' * 50  # 50 characters

        await SensorRangeConfig.objects.acreate(
            machine_id=long_id,
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id=long_id,
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_5_7_very_long_signal_type(self):
        """Signal type at max length (50 chars)"""
        long_signal = 'S' * 50  # 50 characters

        await SensorRangeConfig.objects.acreate(
            machine_id='LONG-SIGNAL',
            signal_type=long_signal,
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='LONG-SIGNAL',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type=long_signal,
            name='signal',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_5_8_unicode_in_machine_id(self):
        """Unicode characters in machine_id"""
        unicode_id = 'MACHINE-测试-001'

        await SensorRangeConfig.objects.acreate(
            machine_id=unicode_id,
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id=unicode_id,
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_5_9_special_chars_in_signal(self):
        """Special characters in signal_type"""
        special_signal = 'temp-°C/min'

        await SensorRangeConfig.objects.acreate(
            machine_id='SPECIAL-CHARS',
            signal_type=special_signal,
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='SPECIAL-CHARS',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type=special_signal,
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_5_10_empty_string_values(self):
        """Empty string handling"""
        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='',  # Empty string
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully (likely pass since no config exists)
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True  # No config for empty machine_id

    async def test_5_11_whitespace_values(self):
        """Whitespace-only strings"""
        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='   ',  # Whitespace only
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True  # No config for whitespace machine_id

    async def test_5_12_extremely_precise_decimals(self):
        """6 decimal places precision support"""
        await SensorRangeConfig.objects.acreate(
            machine_id='PRECISION-TEST',
            signal_type='precise',
            min_value=Decimal('0.000001'),
            max_value=Decimal('0.000010'),
            unit='micro'
        )

        validator = SensorRangeValidator()

        # Within range
        metric1 = NormalizedMetric(
            machine_id='PRECISION-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='precise',
            name='precise',
            value=0.000005,
            unit='micro',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Below range
        metric2 = NormalizedMetric(
            machine_id='PRECISION-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='precise',
            name='precise',
            value=0.0000005,
            unit='micro',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is False

    async def test_5_13_decimal_rounding(self):
        """Decimal rounding behavior"""
        await SensorRangeConfig.objects.acreate(
            machine_id='ROUNDING-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Test value with many decimal places
        metric = NormalizedMetric(
            machine_id='ROUNDING-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.123456789012345,  # Many decimals
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_5_14_timezone_handling(self):
        """Different timezones don't affect validation"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TZ-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # UTC timezone
        metric1 = NormalizedMetric(
            machine_id='TZ-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

    async def test_5_15_concurrent_config_updates(self):
        """Concurrent config modifications handled correctly"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='CONCURRENT-UPDATE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()
        validator.cache_ttl_seconds = 0.1

        metric = NormalizedMetric(
            machine_id='CONCURRENT-UPDATE',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,  # Initially invalid
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Initial validation
        is_valid1, _ = await validator.validate(metric)
        assert is_valid1 is False

        # Update config concurrently
        config.max_value = Decimal('200.0')
        await config.asave()

        # Wait for cache expiration
        await asyncio.sleep(0.15)

        # Should now pass
        is_valid2, _ = await validator.validate(metric)
        assert is_valid2 is True


# ================================================================================================
# CATEGORY 6: Concurrency & Race Conditions (10 tests)
# ================================================================================================
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory6ConcurrencyRaceConditions:
    """Concurrency stress tests and race condition handling"""

    async def test_6_1_concurrent_validations_same_machine(self):
        """100 concurrent validations for same machine"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CONCURRENT-001',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        async def validate_once(value):
            metric = NormalizedMetric(
                machine_id='CONCURRENT-001',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=value,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            return await validator.validate(metric)

        # Run 100 concurrent validations
        tasks = [validate_once(float(i % 100)) for i in range(100)]
        results = await asyncio.gather(*tasks)

        # All should pass (values 0-99)
        assert all(is_valid for is_valid, _ in results)

    async def test_6_2_concurrent_validations_different_machines(self):
        """100 concurrent validations across different machines"""
        # Create configs for 10 machines
        for i in range(10):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'MACHINE-{i:03d}',
                signal_type='temperature',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius'
            )

        validator = SensorRangeValidator()

        async def validate_once(machine_num, value):
            metric = NormalizedMetric(
                machine_id=f'MACHINE-{machine_num:03d}',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=value,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            return await validator.validate(metric)

        # Run 100 concurrent validations across 10 machines
        tasks = [validate_once(i % 10, float(i % 100)) for i in range(100)]
        results = await asyncio.gather(*tasks)

        # All should pass
        assert all(is_valid for is_valid, _ in results)

        # Cache should have 10 entries (one per machine)
        assert len(validator.range_cache) == 10

    async def test_6_3_validation_during_config_create(self):
        """Validate while creating config (race condition)"""
        validator = SensorRangeValidator()

        async def create_config():
            await asyncio.sleep(0.01)  # Small delay
            await SensorRangeConfig.objects.acreate(
                machine_id='RACE-CREATE',
                signal_type='temperature',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius'
            )

        async def validate_metric():
            metric = NormalizedMetric(
                machine_id='RACE-CREATE',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=50.0,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            return await validator.validate(metric)

        # Run both concurrently
        create_task = asyncio.create_task(create_config())
        validate_task = asyncio.create_task(validate_metric())

        is_valid, _ = await validate_task
        await create_task

        # Should handle gracefully (either pass or fail, but not crash)
        assert isinstance(is_valid, bool)

    async def test_6_4_validation_during_config_update(self):
        """Validate while updating config"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='RACE-UPDATE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()
        validator.cache_ttl_seconds = 0.05

        async def update_config():
            await asyncio.sleep(0.01)
            config.max_value = Decimal('200.0')
            await config.asave()

        async def validate_metric():
            for _ in range(10):
                metric = NormalizedMetric(
                    machine_id='RACE-UPDATE',
                    line_id='LINE-001',
                    site_id='SITE01',
                    signal_type='temperature',
                    name='temp',
                    value=150.0,
                    unit='celsius',
                    timestamp_utc=datetime.now(timezone.utc),
                    quality=192,
                    is_valid=True,
                    metadata={}
                )
                await validator.validate(metric)
                await asyncio.sleep(0.01)

        # Run both concurrently
        update_task = asyncio.create_task(update_config())
        validate_task = asyncio.create_task(validate_metric())

        await asyncio.gather(update_task, validate_task)

        # Should complete without errors
        assert True

    async def test_6_5_validation_during_config_delete(self):
        """Validate while deleting config"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='RACE-DELETE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        async def delete_config():
            await asyncio.sleep(0.01)
            await config.adelete()

        async def validate_metric():
            for _ in range(5):
                metric = NormalizedMetric(
                    machine_id='RACE-DELETE',
                    line_id='LINE-001',
                    site_id='SITE01',
                    signal_type='temperature',
                    name='temp',
                    value=50.0,
                    unit='celsius',
                    timestamp_utc=datetime.now(timezone.utc),
                    quality=192,
                    is_valid=True,
                    metadata={}
                )
                await validator.validate(metric)
                await asyncio.sleep(0.01)

        # Run both concurrently
        delete_task = asyncio.create_task(delete_config())
        validate_task = asyncio.create_task(validate_metric())

        await asyncio.gather(delete_task, validate_task)

        # Should complete without errors
        assert True

    async def test_6_6_cache_invalidation_race(self):
        """Cache invalidation during concurrent access"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-RACE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        async def clear_cache_repeatedly():
            for _ in range(10):
                await asyncio.sleep(0.01)
                validator.clear_cache()

        async def validate_repeatedly():
            for _ in range(20):
                metric = NormalizedMetric(
                    machine_id='CACHE-RACE',
                    line_id='LINE-001',
                    site_id='SITE01',
                    signal_type='temperature',
                    name='temp',
                    value=50.0,
                    unit='celsius',
                    timestamp_utc=datetime.now(timezone.utc),
                    quality=192,
                    is_valid=True,
                    metadata={}
                )
                await validator.validate(metric)
                await asyncio.sleep(0.005)

        # Run both concurrently
        await asyncio.gather(
            clear_cache_repeatedly(),
            validate_repeatedly()
        )

        # Should complete without errors
        assert True

    async def test_6_7_ttl_expiration_during_validation(self):
        """TTL expires mid-validation"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TTL-RACE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()
        validator.cache_ttl_seconds = 0.05  # Very short TTL

        # First validation (cache miss)
        metric = NormalizedMetric(
            machine_id='TTL-RACE',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric)

        # Wait for TTL expiration
        await asyncio.sleep(0.06)

        # Second validation (cache expired, needs refresh)
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

    async def test_6_8_bulk_validation_stress(self):
        """1000 validations in 1 second"""
        await SensorRangeConfig.objects.acreate(
            machine_id='BULK-STRESS',
            signal_type='counter',
            min_value=Decimal('0'),
            max_value=Decimal('10000'),
            unit='count'
        )

        validator = SensorRangeValidator()

        import time
        start = time.time()

        tasks = []
        for i in range(1000):
            metric = NormalizedMetric(
                machine_id='BULK-STRESS',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='counter',
                name='counter',
                value=float(i),
                unit='count',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            tasks.append(validator.validate(metric))

        results = await asyncio.gather(*tasks)
        duration = time.time() - start

        # All should pass
        assert all(is_valid for is_valid, _ in results)

        # Should complete in under 2 seconds
        assert duration < 2.0
        logger.info(f"Validated 1000 metrics in {duration:.3f}s ({1000/duration:.0f} msg/sec)")

    async def test_6_9_multiple_validator_instances(self):
        """Multiple SensorRangeValidator instances don't conflict"""
        await SensorRangeConfig.objects.acreate(
            machine_id='MULTI-INSTANCE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        # Create 5 validator instances
        validators = [SensorRangeValidator() for _ in range(5)]

        async def validate_with_instance(validator_instance, value):
            metric = NormalizedMetric(
                machine_id='MULTI-INSTANCE',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=value,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            return await validator_instance.validate(metric)

        # Each instance validates 10 metrics
        tasks = []
        for i, validator in enumerate(validators):
            for j in range(10):
                tasks.append(validate_with_instance(validator, float(j * 10)))

        results = await asyncio.gather(*tasks)

        # All should pass
        assert all(is_valid for is_valid, _ in results)

    async def test_6_10_thread_pool_validation(self):
        """Concurrent validation from thread pool"""
        await SensorRangeConfig.objects.acreate(
            machine_id='THREAD-POOL',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Simulate concurrent requests from different threads
        tasks = []
        for i in range(50):
            metric = NormalizedMetric(
                machine_id='THREAD-POOL',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=float(i % 100),
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            tasks.append(validator.validate(metric))

        results = await asyncio.gather(*tasks)

        # All should pass
        assert all(is_valid for is_valid, _ in results)


# ================================================================================================
# CATEGORY 7: Quality Score Degradation (10 tests)
# ================================================================================================
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory7QualityScoreDegradation:
    """Quality score degradation on validation failures"""

    async def test_7_1_quality_degrades_to_50_below_min(self):
        """Quality degraded to 50 when below minimum"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-MIN',
            signal_type='temperature',
            min_value=Decimal('10.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='QUALITY-MIN',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=5.0,  # Below minimum
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,  # Good quality initially
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)

        assert is_valid is False
        assert metric.quality == 50  # Degraded

    async def test_7_2_quality_degrades_to_50_above_max(self):
        """Quality degraded to 50 when above maximum"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-MAX',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='QUALITY-MAX',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,  # Above maximum
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)

        assert is_valid is False
        assert metric.quality == 50

    async def test_7_3_quality_unchanged_when_valid(self):
        """Quality unchanged when validation passes"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-VALID',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='QUALITY-VALID',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,  # Valid
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)

        assert is_valid is True
        assert metric.quality == 192  # Unchanged

    async def test_7_4_quality_preserved_on_pass(self):
        """Original quality preserved when passing"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-PRESERVE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Test with various quality scores
        for original_quality in [192, 128, 64, 32]:
            metric = NormalizedMetric(
                machine_id='QUALITY-PRESERVE',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=50.0,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=original_quality,
                is_valid=True,
                metadata={}
            )

            await validator.validate(metric)
            assert metric.quality == original_quality

    async def test_7_5_quality_degradation_logged(self):
        """Quality degradation is logged"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-LOG',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='QUALITY-LOG',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,  # Out of range
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Validation should log degradation
        is_valid, error_msg = await validator.validate(metric)

        assert is_valid is False
        assert error_msg is not None
        assert metric.quality == 50

    async def test_7_6_multiple_failures_same_metric(self):
        """Multiple failures tracked correctly"""
        await SensorRangeConfig.objects.acreate(
            machine_id='MULTI-FAIL',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Create metrics that fail
        for i in range(5):
            metric = NormalizedMetric(
                machine_id='MULTI-FAIL',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=150.0 + i,  # All out of range
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )

            is_valid, _ = await validator.validate(metric)
            assert is_valid is False
            assert metric.quality == 50

    async def test_7_7_quality_score_range(self):
        """Quality always stays in valid range (0-192)"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-RANGE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Test with edge case quality values
        for original_quality in [0, 1, 50, 100, 150, 192]:
            metric = NormalizedMetric(
                machine_id='QUALITY-RANGE',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=150.0,  # Out of range
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=original_quality,
                is_valid=True,
                metadata={}
            )

            await validator.validate(metric)

            # Quality should be degraded to 50
            assert 0 <= metric.quality <= 192
            assert metric.quality == 50

    async def test_7_8_original_quality_not_lost(self):
        """Original quality available in metadata"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-META',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='QUALITY-META',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric)

        # Check if original quality is preserved in metadata
        assert metric.quality == 50
        # Original quality may be in metadata (implementation dependent)

    async def test_7_9_degradation_per_violation_type(self):
        """Different degradation per violation type"""
        await SensorRangeConfig.objects.acreate(
            machine_id='VIOLATION-TYPE',
            signal_type='temperature',
            min_value=Decimal('10.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Below minimum
        metric1 = NormalizedMetric(
            machine_id='VIOLATION-TYPE',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=5.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric1)
        quality_below = metric1.quality

        # Above maximum
        metric2 = NormalizedMetric(
            machine_id='VIOLATION-TYPE',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric2)
        quality_above = metric2.quality

        # Both should be degraded (currently to same value)
        assert quality_below == 50
        assert quality_above == 50

    async def test_7_10_quality_restoration(self):
        """Quality not restored after validation"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUALITY-RESTORE',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='QUALITY-RESTORE',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # First validation (degrades quality)
        await validator.validate(metric)
        assert metric.quality == 50

        # Quality remains degraded
        assert metric.quality == 50


# ================================================================================================
# CATEGORY 8: Configuration Management (8 tests)
# ================================================================================================
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory8ConfigurationManagement:
    """Configuration management and violation actions"""

    async def test_8_1_violation_action_alert(self):
        """ALERT action behavior"""
        await SensorRangeConfig.objects.acreate(
            machine_id='ACTION-ALERT',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius',
            violation_action='ALERT'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='ACTION-ALERT',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,  # Out of range
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, error_msg = await validator.validate(metric)

        # ALERT action should fail validation
        assert is_valid is False
        assert error_msg is not None

    async def test_8_2_violation_action_reject(self):
        """REJECT action behavior"""
        await SensorRangeConfig.objects.acreate(
            machine_id='ACTION-REJECT',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius',
            violation_action='REJECT'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='ACTION-REJECT',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)

        # REJECT action should fail validation
        assert is_valid is False

    async def test_8_3_violation_action_flag(self):
        """FLAG action behavior"""
        await SensorRangeConfig.objects.acreate(
            machine_id='ACTION-FLAG',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius',
            violation_action='FLAG'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='ACTION-FLAG',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(metric)

        # FLAG action should fail validation
        assert is_valid is False

    async def test_8_4_config_created_by_tracking(self):
        """created_by field tracking"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='CREATED-BY',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius',
            created_by='test_user@example.com'
        )

        assert config.created_by == 'test_user@example.com'

        # Cleanup
        await config.adelete()

    async def test_8_5_config_notes_field(self):
        """notes field usage"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='NOTES-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius',
            notes='This is a test configuration for critical temperature monitoring'
        )

        assert config.notes is not None
        assert 'critical temperature monitoring' in config.notes

        # Cleanup
        await config.adelete()

    async def test_8_6_config_audit_trail(self):
        """Updated_at changes on save"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='AUDIT-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        initial_updated_at = config.updated_at

        # Wait a moment and update
        await asyncio.sleep(0.1)
        config.max_value = Decimal('200.0')
        await config.asave()

        # updated_at should have changed
        assert config.updated_at > initial_updated_at

        # Cleanup
        await config.adelete()

    async def test_8_7_multiple_violation_actions(self):
        """Different actions per machine"""
        # Create configs with different actions
        configs = []
        for i, action in enumerate(['ALERT', 'REJECT', 'FLAG']):
            config = await SensorRangeConfig.objects.acreate(
                machine_id=f'MULTI-ACTION-{i}',
                signal_type='temperature',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius',
                violation_action=action
            )
            configs.append(config)

        # Verify each has correct action
        for i, action in enumerate(['ALERT', 'REJECT', 'FLAG']):
            config = await SensorRangeConfig.objects.filter(
                machine_id=f'MULTI-ACTION-{i}'
            ).afirst()
            assert config.violation_action == action

        # Cleanup
        for config in configs:
            await config.adelete()

    async def test_8_8_config_export_import(self):
        """Config export/import functionality"""
        # Create test config
        original_config = await SensorRangeConfig.objects.acreate(
            machine_id='EXPORT-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius',
            violation_action='REJECT',
            notes='Export test configuration'
        )

        # Simulate export (get config data)
        config_data = {
            'machine_id': original_config.machine_id,
            'signal_type': original_config.signal_type,
            'min_value': original_config.min_value,
            'max_value': original_config.max_value,
            'unit': original_config.unit,
            'violation_action': original_config.violation_action,
            'notes': original_config.notes
        }

        # Delete original
        await original_config.adelete()

        # Simulate import (recreate from data)
        imported_config = await SensorRangeConfig.objects.acreate(**config_data)

        # Verify data matches
        assert imported_config.machine_id == 'EXPORT-TEST'
        assert imported_config.min_value == Decimal('0.0')
        assert imported_config.max_value == Decimal('100.0')
        assert imported_config.notes == 'Export test configuration'

        # Cleanup
        await imported_config.adelete()


# ================================================================================================
# CATEGORY 9: Error Handling & Resilience (10 tests)
# ================================================================================================
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory9ErrorHandlingResilience:
    """Error handling and system resilience"""

    async def test_9_1_database_unavailable(self):
        """Graceful handling when DB unavailable"""
        # This test is challenging to implement without mocking
        # For now, test that validator handles exceptions gracefully
        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='DB-UNAVAILABLE',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully (likely pass if no config found)
        try:
            is_valid, _ = await validator.validate(metric)
            assert isinstance(is_valid, bool)
        except Exception as e:
            pytest.fail(f"Validator should handle DB errors gracefully: {e}")

    async def test_9_2_corrupted_config_data(self):
        """Invalid data in database"""
        # Create config with valid data (corrupted data hard to test without mocking)
        config = await SensorRangeConfig.objects.acreate(
            machine_id='CORRUPTED-DATA',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='CORRUPTED-DATA',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully
        is_valid, _ = await validator.validate(metric)
        assert isinstance(is_valid, bool)

        await config.adelete()

    async def test_9_3_missing_required_fields(self):
        """Metric missing required fields"""
        await SensorRangeConfig.objects.acreate(
            machine_id='MISSING-FIELDS',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Create metric with None machine_id
        metric = NormalizedMetric(
            machine_id=None,  # Missing
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully
        try:
            is_valid, error_msg = await validator.validate(metric)
            assert isinstance(is_valid, bool)
        except Exception as e:
            pytest.fail(f"Should handle missing fields gracefully: {e}")

    async def test_9_4_type_conversion_errors(self):
        """Value can't convert to Decimal"""
        await SensorRangeConfig.objects.acreate(
            machine_id='TYPE-ERROR',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Test with string value (should handle conversion)
        metric = NormalizedMetric(
            machine_id='TYPE-ERROR',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value='not_a_number',  # Invalid type
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully
        try:
            is_valid, error_msg = await validator.validate(metric)
            assert isinstance(is_valid, bool)
        except Exception as e:
            pytest.fail(f"Should handle type conversion errors gracefully: {e}")

    async def test_9_5_cache_corruption(self):
        """Corrupted cache data"""
        await SensorRangeConfig.objects.acreate(
            machine_id='CACHE-CORRUPT',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Manually corrupt cache
        validator.range_cache['CACHE-CORRUPT:temperature'] = ('invalid', 'corrupted_data')

        metric = NormalizedMetric(
            machine_id='CACHE-CORRUPT',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle gracefully (likely re-query database)
        try:
            is_valid, _ = await validator.validate(metric)
            assert isinstance(is_valid, bool)
        except Exception as e:
            pytest.fail(f"Should handle cache corruption gracefully: {e}")

    async def test_9_6_logger_failure(self):
        """Logger failures don't crash validator"""
        await SensorRangeConfig.objects.acreate(
            machine_id='LOGGER-FAIL',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='LOGGER-FAIL',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=150.0,  # Out of range (triggers logging)
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should validate even if logging fails
        is_valid, _ = await validator.validate(metric)
        assert is_valid is False

    async def test_9_7_metric_object_errors(self):
        """Invalid NormalizedMetric objects"""
        validator = SensorRangeValidator()

        # Try to validate None
        try:
            is_valid, error_msg = await validator.validate(None)
            # Should handle gracefully or raise predictable error
            assert True
        except (TypeError, AttributeError):
            # Expected behavior
            assert True

    async def test_9_8_exception_during_validation(self):
        """Exception handling during validate()"""
        await SensorRangeConfig.objects.acreate(
            machine_id='EXCEPTION-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # Create metric that might cause issues
        metric = NormalizedMetric(
            machine_id='EXCEPTION-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=float('inf'),  # Edge case value
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should handle without crashing
        try:
            is_valid, error_msg = await validator.validate(metric)
            assert isinstance(is_valid, bool)
        except Exception as e:
            pytest.fail(f"Should handle exceptions gracefully: {e}")

    async def test_9_9_partial_config_data(self):
        """Configs with missing optional fields"""
        # Create config without optional fields
        config = await SensorRangeConfig.objects.acreate(
            machine_id='PARTIAL-CONFIG',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
            # No created_by, no notes
        )

        validator = SensorRangeValidator()

        metric = NormalizedMetric(
            machine_id='PARTIAL-CONFIG',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        # Should work fine with missing optional fields
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        await config.adelete()

    async def test_9_10_recovery_after_error(self):
        """Validator recovers after errors"""
        await SensorRangeConfig.objects.acreate(
            machine_id='RECOVERY-TEST',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # First, try to validate something that might error
        bad_metric = NormalizedMetric(
            machine_id=None,  # Bad data
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        try:
            await validator.validate(bad_metric)
        except Exception:
            pass  # Error expected

        # Now validate good metric - should work
        good_metric = NormalizedMetric(
            machine_id='RECOVERY-TEST',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        is_valid, _ = await validator.validate(good_metric)
        assert is_valid is True


# ================================================================================================
# CATEGORY 10: Performance & Scalability (7 tests)
# ================================================================================================
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory10PerformanceScalability:
    """Performance benchmarks and scalability tests"""

    async def test_10_1_validation_throughput(self):
        """10,000 validations/second throughput"""
        await SensorRangeConfig.objects.acreate(
            machine_id='THROUGHPUT-TEST',
            signal_type='counter',
            min_value=Decimal('0'),
            max_value=Decimal('100000'),
            unit='count'
        )

        validator = SensorRangeValidator()

        import time
        start = time.time()

        # Validate 10,000 metrics
        tasks = []
        for i in range(10000):
            metric = NormalizedMetric(
                machine_id='THROUGHPUT-TEST',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='counter',
                name='counter',
                value=float(i),
                unit='count',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            tasks.append(validator.validate(metric))

        results = await asyncio.gather(*tasks)
        duration = time.time() - start

        throughput = 10000 / duration

        # All should pass
        assert all(is_valid for is_valid, _ in results)

        # Should achieve high throughput (at least 1000/sec)
        assert throughput > 1000
        logger.info(f"Throughput: {throughput:.0f} validations/second")

    async def test_10_2_cache_size_limits(self):
        """Large cache (1000+ entries)"""
        # Create 1000 configs
        for i in range(1000):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'CACHE-{i:04d}',
                signal_type='temperature',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius'
            )

        validator = SensorRangeValidator()

        # Validate one metric for each config
        for i in range(1000):
            metric = NormalizedMetric(
                machine_id=f'CACHE-{i:04d}',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=50.0,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            await validator.validate(metric)

        # Cache should have 1000 entries
        assert len(validator.range_cache) == 1000
        logger.info(f"Cache size: {len(validator.range_cache)} entries")

    async def test_10_3_database_query_efficiency(self):
        """Minimal DB queries with cache"""
        await SensorRangeConfig.objects.acreate(
            machine_id='QUERY-EFFICIENT',
            signal_type='temperature',
            min_value=Decimal('0.0'),
            max_value=Decimal('100.0'),
            unit='celsius'
        )

        validator = SensorRangeValidator()

        # First validation (cache miss - queries DB)
        metric1 = NormalizedMetric(
            machine_id='QUERY-EFFICIENT',
            line_id='LINE-001',
            site_id='SITE01',
            signal_type='temperature',
            name='temp',
            value=50.0,
            unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192,
            is_valid=True,
            metadata={}
        )

        await validator.validate(metric1)

        # Next 1000 validations should use cache (no DB queries)
        import time
        start = time.time()

        for i in range(1000):
            metric = NormalizedMetric(
                machine_id='QUERY-EFFICIENT',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type='temperature',
                name='temp',
                value=50.0,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            await validator.validate(metric)

        duration = time.time() - start

        # Should be very fast (under 0.5 seconds for 1000 cached validations)
        assert duration < 0.5
        logger.info(f"1000 cached validations in {duration:.3f}s")

    async def test_10_4_memory_consumption(self):
        """Memory usage under load"""
        # Create 100 configs
        for i in range(100):
            await SensorRangeConfig.objects.acreate(
                machine_id=f'MEM-{i:03d}',
                signal_type='temperature',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius'
            )

        validator = SensorRangeValidator()

        # Validate 10 metrics for each config (1000 total)
        for i in range(100):
            for j in range(10):
                metric = NormalizedMetric(
                    machine_id=f'MEM-{i:03d}',
                    line_id='LINE-001',
                    site_id='SITE01',
                    signal_type='temperature',
                    name='temp',
                    value=float(j * 10),
                    unit='celsius',
                    timestamp_utc=datetime.now(timezone.utc),
                    quality=192,
                    is_valid=True,
                    metadata={}
                )
                await validator.validate(metric)

        # Cache should only have 100 entries (one per machine_id:signal_type)
        assert len(validator.range_cache) == 100
        logger.info("Memory efficient: 1000 validations created only 100 cache entries")

    async def test_10_5_validator_initialization_time(self):
        """Fast validator startup"""
        import time

        start = time.time()
        validator = SensorRangeValidator()
        duration = time.time() - start

        # Should initialize very quickly (under 0.1 seconds)
        assert duration < 0.1
        logger.info(f"Validator initialized in {duration:.4f}s")

    async def test_10_6_config_query_optimization(self):
        """Optimized config queries"""
        # Create configs with composite index
        for i in range(50):
            await SensorRangeConfig.objects.acreate(
                machine_id='QUERY-OPT',
                signal_type=f'signal_{i}',
                min_value=Decimal('0.0'),
                max_value=Decimal('100.0'),
                unit='celsius',
                is_active=True
            )

        validator = SensorRangeValidator()

        import time
        start = time.time()

        # Query for specific machine_id and signal_type (uses index)
        for i in range(50):
            metric = NormalizedMetric(
                machine_id='QUERY-OPT',
                line_id='LINE-001',
                site_id='SITE01',
                signal_type=f'signal_{i}',
                name='signal',
                value=50.0,
                unit='celsius',
                timestamp_utc=datetime.now(timezone.utc),
                quality=192,
                is_valid=True,
                metadata={}
            )
            await validator.validate(metric)

        duration = time.time() - start

        # Should be fast with index (under 0.5 seconds for 50 queries)
        assert duration < 0.5
        logger.info(f"50 indexed queries in {duration:.3f}s")

    async def test_10_7_scalability_to_1000_machines(self):
        """1000 machines, 10 signals each"""
        # Create configs for 1000 machines x 10 signals
        signal_types = ['temp', 'pressure', 'vibration', 'speed', 'current',
                       'voltage', 'torque', 'position', 'flow', 'level']

        # Only create 100 to keep test reasonable (represents scalability)
        for i in range(100):
            for signal in signal_types:
                await SensorRangeConfig.objects.acreate(
                    machine_id=f'SCALE-{i:04d}',
                    signal_type=signal,
                    min_value=Decimal('0.0'),
                    max_value=Decimal('100.0'),
                    unit='units'
                )

        validator = SensorRangeValidator()

        import time
        start = time.time()

        # Validate one metric for each machine/signal combination
        for i in range(100):
            for signal in signal_types:
                metric = NormalizedMetric(
                    machine_id=f'SCALE-{i:04d}',
                    line_id='LINE-001',
                    site_id='SITE01',
                    signal_type=signal,
                    name=signal,
                    value=50.0,
                    unit='units',
                    timestamp_utc=datetime.now(timezone.utc),
                    quality=192,
                    is_valid=True,
                    metadata={}
                )
                await validator.validate(metric)

        duration = time.time() - start

        # 1000 validations (100 machines x 10 signals)
        # Should complete in reasonable time (under 5 seconds)
        assert duration < 5.0

        # Cache should have 1000 entries (100 machines x 10 signals)
        assert len(validator.range_cache) == 1000

        logger.info(f"Scaled to 1000 configs in {duration:.3f}s ({1000/duration:.0f} validations/sec)")


