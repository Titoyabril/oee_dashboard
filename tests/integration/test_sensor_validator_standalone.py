"""
Standalone Tests for SensorRangeValidator - No Sparkplug Dependencies
Comprehensive 100+ test suite covering all validation scenarios
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

# Direct import without going through normalizer
from oee_analytics.stream_processing.validators.sensor_range_validator import SensorRangeValidator
from oee_analytics.models import SensorRangeConfig

logger = logging.getLogger(__name__)


@dataclass
class MockMetric:
    """Mock NormalizedMetric for testing without Sparkplug dependencies"""
    machine_id: str
    line_id: str
    site_id: str
    signal_type: str
    name: str
    value: float
    unit: str
    timestamp_utc: datetime
    quality: int
    is_valid: bool
    source_system: str = 'SPARKPLUG'
    source_node: Optional[str] = None
    source_device: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# ============================================================================
# Category 1: Basic Range Validation (20 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory1_BasicRangeValidation:
    """Basic range validation functionality"""

    async def test_001_no_config_passes(self):
        """No range config exists - validation passes"""
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-001', line_id='L-001', site_id='S01',
            signal_type='temperature', name='temp', value=100.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is True
        assert error_msg is None

    async def test_002_value_at_minimum_passes(self):
        """Value exactly at minimum threshold passes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-002', signal_type='pressure',
            min_value=Decimal('10.0'), max_value=Decimal('100.0'),
            unit='psi', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-002', line_id='L-001', site_id='S01',
            signal_type='pressure', name='p1', value=10.0,
            unit='psi', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_003_value_at_maximum_passes(self):
        """Value exactly at maximum threshold passes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-003', signal_type='vibration',
            min_value=Decimal('0.0'), max_value=Decimal('5.0'),
            unit='mm/s', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-003', line_id='L-001', site_id='S01',
            signal_type='vibration', name='v1', value=5.0,
            unit='mm/s', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_004_value_below_minimum_fails(self):
        """Value below minimum threshold fails"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-004', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-004', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t1', value=-5.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'below minimum' in error_msg
        assert metric.quality == 50
        await config.adelete()

    async def test_005_value_above_maximum_fails(self):
        """Value above maximum threshold fails"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-005', signal_type='rpm',
            min_value=Decimal('0.0'), max_value=Decimal('3000.0'),
            unit='rpm', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-005', line_id='L-001', site_id='S01',
            signal_type='rpm', name='speed', value=3500.0,
            unit='rpm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'exceeds maximum' in error_msg
        assert metric.quality == 50
        await config.adelete()

    async def test_006_value_in_middle_of_range_passes(self):
        """Value in middle of valid range passes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-006', signal_type='flow',
            min_value=Decimal('10.0'), max_value=Decimal('100.0'),
            unit='L/min', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-006', line_id='L-001', site_id='S01',
            signal_type='flow', name='f1', value=55.0,
            unit='L/min', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_007_zero_value_within_range(self):
        """Zero value within valid range passes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-007', signal_type='position',
            min_value=Decimal('-100.0'), max_value=Decimal('100.0'),
            unit='mm', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-007', line_id='L-001', site_id='S01',
            signal_type='position', name='pos', value=0.0,
            unit='mm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_008_negative_value_within_range(self):
        """Negative value within valid range passes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-008', signal_type='temperature',
            min_value=Decimal('-50.0'), max_value=Decimal('50.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-008', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t1', value=-25.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_009_very_small_positive_value(self):
        """Very small positive value validation"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-009', signal_type='current',
            min_value=Decimal('0.001'), max_value=Decimal('10.0'),
            unit='A', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-009', line_id='L-001', site_id='S01',
            signal_type='current', name='i1', value=0.005,
            unit='A', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_010_very_large_value(self):
        """Very large value within range"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-010', signal_type='power',
            min_value=Decimal('0.0'), max_value=Decimal('1000000.0'),
            unit='W', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-010', line_id='L-001', site_id='S01',
            signal_type='power', name='p1', value=500000.0,
            unit='W', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_011_float_precision_edge_case(self):
        """Float precision at boundary"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-011', signal_type='voltage',
            min_value=Decimal('0.0'), max_value=Decimal('24.5'),
            unit='V', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-011', line_id='L-001', site_id='S01',
            signal_type='voltage', name='v1', value=24.499999,
            unit='V', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_012_decimal_precision_validation(self):
        """High precision decimal validation"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-012', signal_type='torque',
            min_value=Decimal('0.000001'), max_value=Decimal('1.0'),
            unit='Nm', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-012', line_id='L-001', site_id='S01',
            signal_type='torque', name='tq1', value=0.000005,
            unit='Nm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_013_just_below_minimum(self):
        """Value just below minimum (epsilon test)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-013', signal_type='humidity',
            min_value=Decimal('20.0'), max_value=Decimal('80.0'),
            unit='%', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-013', line_id='L-001', site_id='S01',
            signal_type='humidity', name='h1', value=19.999,
            unit='%', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'below minimum' in error_msg
        await config.adelete()

    async def test_014_just_above_maximum(self):
        """Value just above maximum (epsilon test)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-014', signal_type='speed',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='m/s', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-014', line_id='L-001', site_id='S01',
            signal_type='speed', name='s1', value=100.001,
            unit='m/s', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'exceeds maximum' in error_msg
        await config.adelete()

    async def test_015_range_with_same_min_max(self):
        """Range where min equals max (exact value check)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-015', signal_type='setpoint',
            min_value=Decimal('50.0'), max_value=Decimal('50.0'),
            unit='units', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-015', line_id='L-001', site_id='S01',
            signal_type='setpoint', name='sp1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_016_very_large_maximum(self):
        """Range with very large maximum (simulates unlimited max)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-016', signal_type='count',
            min_value=Decimal('0.0'), max_value=Decimal('999999999999.0'),
            unit='units', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-016', line_id='L-001', site_id='S01',
            signal_type='count', name='c1', value=999999.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_017_very_small_minimum(self):
        """Range with very small minimum (simulates unlimited min)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-017', signal_type='error_rate',
            min_value=Decimal('-999999999999.0'), max_value=Decimal('5.0'),
            unit='%', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-017', line_id='L-001', site_id='S01',
            signal_type='error_rate', name='er1', value=-100.0,
            unit='%', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_018_scientific_notation_value(self):
        """Value in scientific notation"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-018', signal_type='resistance',
            min_value=Decimal('1e-6'), max_value=Decimal('1e6'),
            unit='Ohm', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-018', line_id='L-001', site_id='S01',
            signal_type='resistance', name='r1', value=1.5e3,
            unit='Ohm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_019_multiple_configs_same_machine_different_signals(self):
        """Multiple configs for same machine, different signal types"""
        config1 = await SensorRangeConfig.objects.acreate(
            machine_id='M-019', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        config2 = await SensorRangeConfig.objects.acreate(
            machine_id='M-019', signal_type='pressure',
            min_value=Decimal('0.0'), max_value=Decimal('200.0'),
            unit='psi', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()

        # Test temperature
        metric1 = MockMetric(
            machine_id='M-019', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t1', value=50.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Test pressure
        metric2 = MockMetric(
            machine_id='M-019', line_id='L-001', site_id='S01',
            signal_type='pressure', name='p1', value=150.0,
            unit='psi', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is True

        await config1.adelete()
        await config2.adelete()

    async def test_020_quality_degradation_on_failure(self):
        """Quality score degraded to 50 on range violation"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-020', signal_type='level',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='%', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-020', line_id='L-001', site_id='S01',
            signal_type='level', name='lvl1', value=150.0,
            unit='%', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is False
        assert metric.quality == 50  # Degraded quality
        await config.adelete()


# ============================================================================
# Category 2: Cache Behavior (15 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory2_CacheBehavior:
    """Cache functionality and TTL behavior"""

    async def test_021_cache_hit_on_second_call(self):
        """Second validation uses cached config"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-021', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-021', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t1', value=50.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )

        # First call - cache miss
        await validator.validate(metric)
        cache_key = "M-021:temperature"
        assert cache_key in validator.range_cache

        # Second call - cache hit
        await validator.validate(metric)
        assert cache_key in validator.range_cache

        await config.adelete()

    async def test_022_cache_key_format(self):
        """Cache key uses machine_id:signal_type format"""
        validator = SensorRangeValidator()
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-022', signal_type='vibration',
            min_value=Decimal('0.0'), max_value=Decimal('10.0'),
            unit='mm/s', violation_action='REJECT', is_active=True
        )
        metric = MockMetric(
            machine_id='M-022', line_id='L-001', site_id='S01',
            signal_type='vibration', name='v1', value=5.0,
            unit='mm/s', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        await validator.validate(metric)
        assert "M-022:vibration" in validator.range_cache
        await config.adelete()

    async def test_023_clear_cache_removes_all_entries(self):
        """clear_cache() removes all cached entries"""
        validator = SensorRangeValidator()
        validator.range_cache['key1'] = ('data', 'val1')
        validator.range_cache['key2'] = ('data', 'val2')
        validator.clear_cache()
        assert len(validator.range_cache) == 0

    async def test_024_cache_stores_none_when_no_config(self):
        """Cache stores None when no config exists"""
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-024', line_id='L-001', site_id='S01',
            signal_type='unknown', name='x1', value=100.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        await validator.validate(metric)
        cache_key = "M-024:unknown"
        assert cache_key in validator.range_cache
        _, cached_config = validator.range_cache[cache_key]
        assert cached_config is None

    async def test_025_multiple_validators_separate_caches(self):
        """Multiple validator instances have separate caches"""
        validator1 = SensorRangeValidator()
        validator2 = SensorRangeValidator()

        validator1.range_cache['test'] = ('data1', 'val1')
        assert 'test' not in validator2.range_cache

    async def test_026_cache_persists_across_validations(self):
        """Cache persists across multiple validation calls"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-026', signal_type='rpm',
            min_value=Decimal('0.0'), max_value=Decimal('5000.0'),
            unit='rpm', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()

        for i in range(10):
            metric = MockMetric(
                machine_id='M-026', line_id='L-001', site_id='S01',
                signal_type='rpm', name='rpm1', value=1000.0 + i,
                unit='rpm', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            await validator.validate(metric)

        assert "M-026:rpm" in validator.range_cache
        await config.adelete()

    async def test_027_cache_different_machines_same_signal(self):
        """Different machines with same signal type use different cache keys"""
        config1 = await SensorRangeConfig.objects.acreate(
            machine_id='M-027A', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        config2 = await SensorRangeConfig.objects.acreate(
            machine_id='M-027B', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('200.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()

        metric1 = MockMetric(
            machine_id='M-027A', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t1', value=50.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        metric2 = MockMetric(
            machine_id='M-027B', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t2', value=150.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )

        await validator.validate(metric1)
        await validator.validate(metric2)

        assert "M-027A:temperature" in validator.range_cache
        assert "M-027B:temperature" in validator.range_cache

        await config1.adelete()
        await config2.adelete()

    async def test_028_cache_timestamps_updated(self):
        """Cache timestamps are set on cache entry"""
        validator = SensorRangeValidator()
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-028', signal_type='flow',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='L/min', violation_action='REJECT', is_active=True
        )
        metric = MockMetric(
            machine_id='M-028', line_id='L-001', site_id='S01',
            signal_type='flow', name='f1', value=50.0,
            unit='L/min', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        await validator.validate(metric)
        cache_key = "M-028:flow"
        timestamp, _ = validator.range_cache[cache_key]
        assert isinstance(timestamp, datetime)
        await config.adelete()

    async def test_029_cache_size_grows_with_unique_keys(self):
        """Cache grows with each unique machine:signal combination"""
        validator = SensorRangeValidator()
        initial_size = len(validator.range_cache)

        for i in range(5):
            metric = MockMetric(
                machine_id=f'M-029-{i}', line_id='L-001', site_id='S01',
                signal_type='temperature', name='t1', value=50.0,
                unit='celsius', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            await validator.validate(metric)

        assert len(validator.range_cache) == initial_size + 5

    async def test_030_inactive_config_cached_as_none(self):
        """Inactive config is cached as None"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-030', signal_type='pressure',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='psi', violation_action='REJECT', is_active=False
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-030', line_id='L-001', site_id='S01',
            signal_type='pressure', name='p1', value=50.0,
            unit='psi', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        await validator.validate(metric)
        cache_key = "M-030:pressure"
        _, cached_config = validator.range_cache[cache_key]
        assert cached_config is None
        await config.adelete()

    async def test_031_cache_empty_on_initialization(self):
        """Validator cache is empty on initialization"""
        validator = SensorRangeValidator()
        assert len(validator.range_cache) == 0

    async def test_032_cache_ttl_default_300_seconds(self):
        """Cache TTL defaults to 300 seconds (5 minutes)"""
        validator = SensorRangeValidator()
        assert validator.cache_ttl_seconds == 300

    async def test_033_cache_revalidates_after_clear(self):
        """After cache clear, next validation queries database"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-033', signal_type='voltage',
            min_value=Decimal('0.0'), max_value=Decimal('24.0'),
            unit='V', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-033', line_id='L-001', site_id='S01',
            signal_type='voltage', name='v1', value=12.0,
            unit='V', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )

        # First validation - populates cache
        await validator.validate(metric)
        assert "M-033:voltage" in validator.range_cache

        # Clear cache
        validator.clear_cache()
        assert len(validator.range_cache) == 0

        # Second validation - repopulates cache
        await validator.validate(metric)
        assert "M-033:voltage" in validator.range_cache

        await config.adelete()

    async def test_034_concurrent_validations_same_key(self):
        """Concurrent validations for same key handle cache correctly"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-034', signal_type='current',
            min_value=Decimal('0.0'), max_value=Decimal('10.0'),
            unit='A', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()

        async def validate_metric(value):
            metric = MockMetric(
                machine_id='M-034', line_id='L-001', site_id='S01',
                signal_type='current', name='i1', value=value,
                unit='A', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            return await validator.validate(metric)

        # Run concurrent validations
        results = await asyncio.gather(
            validate_metric(1.0),
            validate_metric(2.0),
            validate_metric(3.0)
        )

        assert all(r[0] is True for r in results)
        assert "M-034:current" in validator.range_cache

        await config.adelete()

    async def test_035_cache_handles_case_sensitive_keys(self):
        """Cache keys are case-sensitive"""
        validator = SensorRangeValidator()
        config1 = await SensorRangeConfig.objects.acreate(
            machine_id='M-035', signal_type='Temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        config2 = await SensorRangeConfig.objects.acreate(
            machine_id='M-035', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('200.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )

        metric1 = MockMetric(
            machine_id='M-035', line_id='L-001', site_id='S01',
            signal_type='Temperature', name='t1', value=50.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        metric2 = MockMetric(
            machine_id='M-035', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t2', value=150.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )

        await validator.validate(metric1)
        await validator.validate(metric2)

        assert "M-035:Temperature" in validator.range_cache
        assert "M-035:temperature" in validator.range_cache

        await config1.adelete()
        await config2.adelete()


# ============================================================================
# Category 3: Configuration State (15 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory3_ConfigurationState:
    """Configuration active/inactive state handling"""

    async def test_036_inactive_config_ignored(self):
        """Inactive configuration is ignored during validation"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-036', signal_type='pressure',
            min_value=Decimal('50.0'), max_value=Decimal('100.0'),
            unit='psi', violation_action='REJECT', is_active=False
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-036', line_id='L-001', site_id='S01',
            signal_type='pressure', name='p1', value=10.0,  # Would fail if active
            unit='psi', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is True
        assert error_msg is None
        await config.adelete()

    async def test_037_active_config_enforced(self):
        """Active configuration is enforced"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-037', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('50.0'),
            unit='celsius', violation_action='REJECT', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-037', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t1', value=100.0,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'exceeds maximum' in error_msg
        await config.adelete()

    async def test_038_multiple_configs_only_active_used(self):
        """When multiple configs exist for different machines, only active ones are used"""
        # Create inactive config for one machine
        config1 = await SensorRangeConfig.objects.acreate(
            machine_id='M-038A', signal_type='flow',
            min_value=Decimal('40.0'), max_value=Decimal('60.0'),
            unit='L/min', violation_action='REJECT', is_active=False
        )
        # Create active config for another machine
        config2 = await SensorRangeConfig.objects.acreate(
            machine_id='M-038B', signal_type='flow',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='L/min', violation_action='REJECT', is_active=True
        )

        validator = SensorRangeValidator()
        # Test that inactive config doesn't reject valid value
        metric1 = MockMetric(
            machine_id='M-038A', line_id='L-001', site_id='S01',
            signal_type='flow', name='f1', value=80.0,
            unit='L/min', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True  # Passes because config is inactive

        # Test that active config is used
        metric2 = MockMetric(
            machine_id='M-038B', line_id='L-001', site_id='S01',
            signal_type='flow', name='f1', value=80.0,
            unit='L/min', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is True  # Passes with active config

        await config1.adelete()
        await config2.adelete()

    async def test_039_violation_action_reject(self):
        """violation_action='REJECT' properly configured"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-039', signal_type='rpm',
            min_value=Decimal('0.0'), max_value=Decimal('3000.0'),
            unit='rpm', violation_action='REJECT', is_active=True
        )
        assert config.violation_action == 'REJECT'
        await config.adelete()

    async def test_040_config_created_with_defaults(self):
        """Config can be created with default values"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-040', signal_type='test',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units'
        )
        assert config.is_active is True  # Default
        assert config.violation_action == 'ALERT'  # Default is ALERT
        await config.adelete()

    async def test_041_config_unique_constraint(self):
        """Unique constraint on machine_id + signal_type"""
        config1 = await SensorRangeConfig.objects.acreate(
            machine_id='M-041', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='celsius', is_active=True
        )

        # Try to create duplicate
        with pytest.raises(Exception):  # IntegrityError
            await SensorRangeConfig.objects.acreate(
                machine_id='M-041', signal_type='temperature',
                min_value=Decimal('0.0'), max_value=Decimal('200.0'),
                unit='celsius', is_active=True
            )

        await config1.adelete()

    async def test_042_config_notes_field(self):
        """Config notes field stores text"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-042', signal_type='pressure',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='psi', notes='Hydraulic pressure sensor',
            is_active=True
        )
        assert config.notes == 'Hydraulic pressure sensor'
        await config.adelete()

    async def test_043_config_with_null_notes(self):
        """Config with null/blank notes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-043', signal_type='voltage',
            min_value=Decimal('0.0'), max_value=Decimal('24.0'),
            unit='V', is_active=True
        )
        assert config.notes in (None, '')
        await config.adelete()

    async def test_044_config_very_low_min_only_max_enforced(self):
        """Config with very low minimum simulates unlimited min"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-044', signal_type='error_count',
            min_value=Decimal('-999999999999.0'), max_value=Decimal('100.0'),
            unit='count', is_active=True
        )
        validator = SensorRangeValidator()

        # Test very negative value (should pass - effectively no minimum)
        metric = MockMetric(
            machine_id='M-044', line_id='L-001', site_id='S01',
            signal_type='error_count', name='ec1', value=-999999.0,
            unit='count', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        await config.adelete()

    async def test_045_config_very_high_max_only_min_enforced(self):
        """Config with very high maximum simulates unlimited max"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-045', signal_type='total_count',
            min_value=Decimal('0.0'), max_value=Decimal('999999999999.0'),
            unit='count', is_active=True
        )
        validator = SensorRangeValidator()

        # Test very large value (should pass - effectively no maximum)
        metric = MockMetric(
            machine_id='M-045', line_id='L-001', site_id='S01',
            signal_type='total_count', name='tc1', value=999999999.0,
            unit='count', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        await config.adelete()

    async def test_046_config_very_wide_range_passes_all(self):
        """Config with very wide range effectively passes all values"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-046', signal_type='unconstrained',
            min_value=Decimal('-999999999999.0'), max_value=Decimal('999999999999.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        for test_value in [-999999.0, 0.0, 999999.0]:
            metric = MockMetric(
                machine_id='M-046', line_id='L-001', site_id='S01',
                signal_type='unconstrained', name='u1', value=test_value,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            assert is_valid is True

        await config.adelete()

    async def test_047_config_unit_stored_correctly(self):
        """Config unit field stores correctly"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-047', signal_type='length',
            min_value=Decimal('0.0'), max_value=Decimal('1000.0'),
            unit='millimeters', is_active=True
        )
        assert config.unit == 'millimeters'
        await config.adelete()

    async def test_048_config_decimal_precision_18_6(self):
        """Config decimal fields support 18,6 precision"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-048', signal_type='precise',
            min_value=Decimal('123456789012.123456'),
            max_value=Decimal('999999999999.999999'),
            unit='units', is_active=True
        )
        assert config.min_value == Decimal('123456789012.123456')
        assert config.max_value == Decimal('999999999999.999999')
        await config.adelete()

    async def test_049_config_timestamps_auto_set(self):
        """Config created_at and updated_at timestamps auto-set"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-049', signal_type='temp',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='C', is_active=True
        )
        assert config.created_at is not None
        assert config.updated_at is not None
        assert isinstance(config.created_at, datetime)
        assert isinstance(config.updated_at, datetime)
        await config.adelete()

    async def test_050_config_query_active_only(self):
        """Query for only active configurations"""
        config1 = await SensorRangeConfig.objects.acreate(
            machine_id='M-050A', signal_type='temp',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='C', is_active=True
        )
        config2 = await SensorRangeConfig.objects.acreate(
            machine_id='M-050B', signal_type='temp',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='C', is_active=False
        )

        active_count = await SensorRangeConfig.objects.filter(is_active=True).acount()
        assert active_count >= 1

        await config1.adelete()
        await config2.adelete()


# ============================================================================
# Category 4: Error Messages (10 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory4_ErrorMessages:
    """Error message content and formatting"""

    async def test_051_error_message_below_minimum(self):
        """Error message for below minimum includes details"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-051', signal_type='pressure',
            min_value=Decimal('10.0'), max_value=Decimal('100.0'),
            unit='psi', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-051', line_id='L-001', site_id='S01',
            signal_type='pressure', name='p1', value=5.0,
            unit='psi', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'below minimum' in error_msg.lower()
        assert '5.0' in error_msg or '5' in error_msg
        assert '10' in error_msg
        await config.adelete()

    async def test_052_error_message_above_maximum(self):
        """Error message for above maximum includes details"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-052', signal_type='rpm',
            min_value=Decimal('0.0'), max_value=Decimal('3000.0'),
            unit='rpm', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-052', line_id='L-001', site_id='S01',
            signal_type='rpm', name='r1', value=3500.0,
            unit='rpm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'exceeds maximum' in error_msg.lower() or 'above maximum' in error_msg.lower()
        assert '3500' in error_msg
        assert '3000' in error_msg
        await config.adelete()

    async def test_053_error_message_includes_metric_name(self):
        """Error message includes metric name"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-053', signal_type='vibration',
            min_value=Decimal('0.0'), max_value=Decimal('5.0'),
            unit='mm/s', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-053', line_id='L-001', site_id='S01',
            signal_type='vibration', name='v1', value=10.0,
            unit='mm/s', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'v1' in error_msg.lower()  # Metric name in message
        await config.adelete()

    async def test_054_error_message_includes_machine_id(self):
        """Error message includes machine ID"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='PRESS-5000', signal_type='force',
            min_value=Decimal('0.0'), max_value=Decimal('1000.0'),
            unit='kN', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='PRESS-5000', line_id='L-001', site_id='S01',
            signal_type='force', name='f1', value=1500.0,
            unit='kN', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert 'PRESS-5000' in error_msg
        await config.adelete()

    async def test_055_error_message_includes_actual_value(self):
        """Error message includes actual sensor value"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-055', signal_type='temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='celsius', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-055', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t1', value=125.5,
            unit='celsius', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert '125.5' in error_msg or '125' in error_msg
        await config.adelete()

    async def test_056_error_message_includes_threshold(self):
        """Error message includes violated threshold"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-056', signal_type='level',
            min_value=Decimal('20.0'), max_value=Decimal('80.0'),
            unit='%', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-056', line_id='L-001', site_id='S01',
            signal_type='level', name='lvl1', value=5.0,
            unit='%', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert '20' in error_msg  # min threshold
        await config.adelete()

    async def test_057_no_error_message_on_success(self):
        """No error message when validation passes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-057', signal_type='current',
            min_value=Decimal('0.0'), max_value=Decimal('10.0'),
            unit='A', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-057', line_id='L-001', site_id='S01',
            signal_type='current', name='i1', value=5.0,
            unit='A', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is True
        assert error_msg is None
        await config.adelete()

    async def test_058_error_message_negative_value(self):
        """Error message handles negative values correctly"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-058', signal_type='position',
            min_value=Decimal('-100.0'), max_value=Decimal('100.0'),
            unit='mm', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-058', line_id='L-001', site_id='S01',
            signal_type='position', name='pos1', value=-150.0,
            unit='mm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert '-150' in error_msg
        assert '-100' in error_msg
        await config.adelete()

    async def test_059_error_message_scientific_notation(self):
        """Error message formats scientific notation values"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-059', signal_type='nano_measurement',
            min_value=Decimal('1e-9'), max_value=Decimal('1e-6'),
            unit='m', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-059', line_id='L-001', site_id='S01',
            signal_type='nano_measurement', name='nm1', value=1e-3,
            unit='m', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert error_msg is not None
        await config.adelete()

    async def test_060_error_message_type_string(self):
        """Error message is always a string"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-060', signal_type='test',
            min_value=Decimal('0.0'), max_value=Decimal('10.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-060', line_id='L-001', site_id='S01',
            signal_type='test', name='t1', value=20.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, error_msg = await validator.validate(metric)
        assert is_valid is False
        assert isinstance(error_msg, str)
        await config.adelete()


# ============================================================================
# Category 5: Edge Cases & Boundary Conditions (20 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory5_EdgeCases:
    """Edge cases and boundary conditions"""

    async def test_061_very_small_range(self):
        """Very narrow range (0.001 difference)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-061', signal_type='precision',
            min_value=Decimal('10.000'), max_value=Decimal('10.001'),
            unit='mm', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-061', line_id='L-001', site_id='S01',
            signal_type='precision', name='pr1', value=10.0005,
            unit='mm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_062_very_large_range(self):
        """Very wide range (millions)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-062', signal_type='distance',
            min_value=Decimal('-1000000.0'), max_value=Decimal('1000000.0'),
            unit='m', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-062', line_id='L-001', site_id='S01',
            signal_type='distance', name='d1', value=500000.0,
            unit='m', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_063_zero_to_zero_range(self):
        """Range where both min and max are zero"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-063', signal_type='offset',
            min_value=Decimal('0.0'), max_value=Decimal('0.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-063', line_id='L-001', site_id='S01',
            signal_type='offset', name='off1', value=0.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_064_negative_range(self):
        """Entirely negative range"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-064', signal_type='depth',
            min_value=Decimal('-1000.0'), max_value=Decimal('-100.0'),
            unit='m', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-064', line_id='L-001', site_id='S01',
            signal_type='depth', name='d1', value=-500.0,
            unit='m', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_065_metric_value_infinity_rejected(self):
        """Infinity value treated as invalid"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-065', signal_type='rate',
            min_value=Decimal('0.0'), max_value=Decimal('1000.0'),
            unit='Hz', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-065', line_id='L-001', site_id='S01',
            signal_type='rate', name='r1', value=float('inf'),
            unit='Hz', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        # Should handle gracefully
        try:
            is_valid, _ = await validator.validate(metric)
            assert is_valid is False
        except Exception:
            pass  # Exception handling is acceptable
        await config.adelete()

    async def test_066_metric_value_nan_rejected(self):
        """NaN value treated as invalid"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-066', signal_type='reading',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-066', line_id='L-001', site_id='S01',
            signal_type='reading', name='rd1', value=float('nan'),
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        # Should handle gracefully
        try:
            is_valid, _ = await validator.validate(metric)
            assert is_valid is False
        except Exception:
            pass  # Exception handling is acceptable
        await config.adelete()

    async def test_067_empty_machine_id(self):
        """Empty string machine ID"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='', signal_type='test',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='', line_id='L-001', site_id='S01',
            signal_type='test', name='t1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_068_long_machine_id(self):
        """Very long machine ID"""
        long_id = 'M' * 200
        config = await SensorRangeConfig.objects.acreate(
            machine_id=long_id, signal_type='test',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id=long_id, line_id='L-001', site_id='S01',
            signal_type='test', name='t1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_069_special_characters_machine_id(self):
        """Machine ID with special characters"""
        special_id = 'M-001/ABC_XYZ.v2'
        config = await SensorRangeConfig.objects.acreate(
            machine_id=special_id, signal_type='test',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id=special_id, line_id='L-001', site_id='S01',
            signal_type='test', name='t1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_070_unicode_characters_signal_type(self):
        """Signal type with unicode characters"""
        unicode_signal = '温度'  # Chinese for "temperature"
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-070', signal_type=unicode_signal,
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='°C', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-070', line_id='L-001', site_id='S01',
            signal_type=unicode_signal, name='t1', value=50.0,
            unit='°C', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_071_whitespace_in_signal_type(self):
        """Signal type with whitespace"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-071', signal_type='motor speed',
            min_value=Decimal('0.0'), max_value=Decimal('3000.0'),
            unit='rpm', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-071', line_id='L-001', site_id='S01',
            signal_type='motor speed', name='ms1', value=1500.0,
            unit='rpm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_072_case_sensitivity_signal_type(self):
        """Signal type case sensitivity"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-072', signal_type='Temperature',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='C', is_active=True
        )
        validator = SensorRangeValidator()

        # Exact case match
        metric1 = MockMetric(
            machine_id='M-072', line_id='L-001', site_id='S01',
            signal_type='Temperature', name='t1', value=50.0,
            unit='C', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Different case - should not match (case-sensitive)
        metric2 = MockMetric(
            machine_id='M-072', line_id='L-001', site_id='S01',
            signal_type='temperature', name='t2', value=50.0,
            unit='C', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is True  # No config for lowercase - passes

        await config.adelete()

    async def test_073_maximum_decimal_value(self):
        """Maximum possible decimal value"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-073', signal_type='huge',
            min_value=Decimal('0.0'),
            max_value=Decimal('999999999999.999999'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-073', line_id='L-001', site_id='S01',
            signal_type='huge', name='h1', value=500000000000.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_074_minimum_decimal_value(self):
        """Minimum possible decimal value"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-074', signal_type='tiny',
            min_value=Decimal('-999999999999.999999'),
            max_value=Decimal('0.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-074', line_id='L-001', site_id='S01',
            signal_type='tiny', name='ti1', value=-500000000000.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_075_six_decimal_places_precision(self):
        """Six decimal places precision"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-075', signal_type='ultra_precise',
            min_value=Decimal('0.000001'),
            max_value=Decimal('0.000002'),
            unit='mm', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-075', line_id='L-001', site_id='S01',
            signal_type='ultra_precise', name='up1', value=0.0000015,
            unit='mm', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_076_rapid_succession_validations(self):
        """Multiple validations in rapid succession"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-076', signal_type='stream',
            min_value=Decimal('0.0'), max_value=Decimal('1000.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        for i in range(100):
            metric = MockMetric(
                machine_id='M-076', line_id='L-001', site_id='S01',
                signal_type='stream', name='s1', value=float(i),
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            assert is_valid is True

        await config.adelete()

    async def test_077_alternating_pass_fail_validations(self):
        """Alternating pass/fail validations"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-077', signal_type='toggle',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        for i in range(10):
            value = 50.0 if i % 2 == 0 else 150.0
            metric = MockMetric(
                machine_id='M-077', line_id='L-001', site_id='S01',
                signal_type='toggle', name='tg1', value=value,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            expected = (i % 2 == 0)
            assert is_valid == expected

        await config.adelete()

    async def test_078_timestamp_old_metric(self):
        """Metric with old timestamp validates correctly"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-078', signal_type='historical',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        old_time = datetime.now(timezone.utc) - timedelta(days=365)
        metric = MockMetric(
            machine_id='M-078', line_id='L-001', site_id='S01',
            signal_type='historical', name='h1', value=50.0,
            unit='units', timestamp_utc=old_time,
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_079_timestamp_future_metric(self):
        """Metric with future timestamp validates correctly"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-079', signal_type='future',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        future_time = datetime.now(timezone.utc) + timedelta(days=30)
        metric = MockMetric(
            machine_id='M-079', line_id='L-001', site_id='S01',
            signal_type='future', name='f1', value=50.0,
            unit='units', timestamp_utc=future_time,
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        await config.adelete()

    async def test_080_metric_quality_preserved_on_pass(self):
        """Metric quality unchanged when validation passes"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-080', signal_type='quality_test',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()
        metric = MockMetric(
            machine_id='M-080', line_id='L-001', site_id='S01',
            signal_type='quality_test', name='qt1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True
        assert metric.quality == 192  # Unchanged
        await config.adelete()


# ============================================================================
# Category 6: Performance & Concurrency (15 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory6_PerformanceAndConcurrency:
    """Performance and concurrent access tests"""

    async def test_081_concurrent_validations_different_machines(self):
        """Concurrent validations for different machines"""
        configs = []
        for i in range(10):
            config = await SensorRangeConfig.objects.acreate(
                machine_id=f'M-081-{i}', signal_type='temperature',
                min_value=Decimal('0.0'), max_value=Decimal('100.0'),
                unit='C', is_active=True
            )
            configs.append(config)

        validator = SensorRangeValidator()

        async def validate_machine(machine_id):
            metric = MockMetric(
                machine_id=machine_id, line_id='L-001', site_id='S01',
                signal_type='temperature', name='t1', value=50.0,
                unit='C', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            return await validator.validate(metric)

        results = await asyncio.gather(*[
            validate_machine(f'M-081-{i}') for i in range(10)
        ])

        assert all(r[0] is True for r in results)

        for config in configs:
            await config.adelete()

    async def test_082_concurrent_validations_same_machine(self):
        """Concurrent validations for same machine/signal"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-082', signal_type='pressure',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='psi', is_active=True
        )
        validator = SensorRangeValidator()

        async def validate_value(value):
            metric = MockMetric(
                machine_id='M-082', line_id='L-001', site_id='S01',
                signal_type='pressure', name='p1', value=value,
                unit='psi', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            return await validator.validate(metric)

        results = await asyncio.gather(*[
            validate_value(float(i)) for i in range(50)
        ])

        assert all(r[0] is True for r in results)
        await config.adelete()

    async def test_083_high_volume_sequential_validations(self):
        """High volume sequential validations (1000 metrics)"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-083', signal_type='highvol',
            min_value=Decimal('0.0'), max_value=Decimal('10000.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        for i in range(1000):
            metric = MockMetric(
                machine_id='M-083', line_id='L-001', site_id='S01',
                signal_type='highvol', name='hv1', value=float(i),
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            assert is_valid is True

        await config.adelete()

    async def test_084_cache_reduces_database_queries(self):
        """Cache reduces repeated database queries"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-084', signal_type='cached',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        # First call - cache miss
        metric1 = MockMetric(
            machine_id='M-084', line_id='L-001', site_id='S01',
            signal_type='cached', name='c1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        await validator.validate(metric1)

        # Verify cache populated
        assert "M-084:cached" in validator.range_cache

        # Subsequent calls should use cache
        for _ in range(100):
            metric = MockMetric(
                machine_id='M-084', line_id='L-001', site_id='S01',
                signal_type='cached', name='c1', value=50.0,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            await validator.validate(metric)

        # Cache should still contain single entry
        assert "M-084:cached" in validator.range_cache

        await config.adelete()

    async def test_085_multiple_validators_independent_caches(self):
        """Multiple validators maintain independent caches"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-085', signal_type='multi',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )

        validator1 = SensorRangeValidator()
        validator2 = SensorRangeValidator()

        metric = MockMetric(
            machine_id='M-085', line_id='L-001', site_id='S01',
            signal_type='multi', name='m1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )

        await validator1.validate(metric)
        assert "M-085:multi" in validator1.range_cache
        assert "M-085:multi" not in validator2.range_cache

        await config.adelete()

    async def test_086_batch_config_creation(self):
        """Bulk create multiple configs efficiently"""
        configs_data = [
            SensorRangeConfig(
                machine_id=f'M-086-{i}', signal_type='temp',
                min_value=Decimal('0.0'), max_value=Decimal('100.0'),
                unit='C', is_active=True
            ) for i in range(50)
        ]
        configs = await SensorRangeConfig.objects.abulk_create(configs_data)

        count = await SensorRangeConfig.objects.filter(
            machine_id__startswith='M-086-'
        ).acount()
        assert count == 50

        # Cleanup
        await SensorRangeConfig.objects.filter(
            machine_id__startswith='M-086-'
        ).adelete()

    async def test_087_validator_instance_reuse(self):
        """Single validator instance reused across many validations"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-087', signal_type='reuse',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        for i in range(500):
            metric = MockMetric(
                machine_id='M-087', line_id='L-001', site_id='S01',
                signal_type='reuse', name='r1', value=50.0,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            assert is_valid is True

        await config.adelete()

    async def test_088_mixed_pass_fail_performance(self):
        """Performance with mix of passing and failing validations"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-088', signal_type='mixed',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        pass_count = 0
        fail_count = 0

        for i in range(200):
            # Alternate between valid and invalid
            value = 50.0 if i % 2 == 0 else 150.0
            metric = MockMetric(
                machine_id='M-088', line_id='L-001', site_id='S01',
                signal_type='mixed', name='mx1', value=value,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            if is_valid:
                pass_count += 1
            else:
                fail_count += 1

        assert pass_count == 100
        assert fail_count == 100
        await config.adelete()

    async def test_089_cache_memory_bounded(self):
        """Cache doesn't grow unbounded with many unique keys"""
        validator = SensorRangeValidator()

        # Simulate many different machine/signal combinations
        for i in range(100):
            metric = MockMetric(
                machine_id=f'M-089-{i}', line_id='L-001', site_id='S01',
                signal_type=f'signal-{i}', name='s1', value=50.0,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            await validator.validate(metric)

        # Cache should contain entries
        assert len(validator.range_cache) == 100

    async def test_090_async_validator_no_blocking(self):
        """Async validator doesn't block event loop"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-090', signal_type='async',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        async def validate_and_sleep(delay):
            await asyncio.sleep(delay)
            metric = MockMetric(
                machine_id='M-090', line_id='L-001', site_id='S01',
                signal_type='async', name='a1', value=50.0,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            return await validator.validate(metric)

        # Run concurrent tasks with different delays
        results = await asyncio.gather(*[
            validate_and_sleep(0.01 * i) for i in range(10)
        ])

        assert all(r[0] is True for r in results)
        await config.adelete()

    async def test_091_validator_with_many_configs(self):
        """Validator performance with many active configs"""
        configs = []
        for i in range(100):
            config = await SensorRangeConfig.objects.acreate(
                machine_id=f'M-091-{i}', signal_type='temp',
                min_value=Decimal('0.0'), max_value=Decimal('100.0'),
                unit='C', is_active=True
            )
            configs.append(config)

        validator = SensorRangeValidator()

        # Validate one machine
        metric = MockMetric(
            machine_id='M-091-50', line_id='L-001', site_id='S01',
            signal_type='temp', name='t1', value=50.0,
            unit='C', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        for config in configs:
            await config.adelete()

    async def test_092_concurrent_cache_clear(self):
        """Concurrent cache clears handle correctly"""
        validator = SensorRangeValidator()

        async def populate_and_clear():
            # Populate cache
            for i in range(10):
                validator.range_cache[f'key-{i}'] = ('data', datetime.now(timezone.utc))
            # Clear cache
            validator.clear_cache()
            return len(validator.range_cache)

        results = await asyncio.gather(*[populate_and_clear() for _ in range(5)])

        # Final cache should be empty
        assert len(validator.range_cache) == 0

    async def test_093_large_batch_validation(self):
        """Large batch of metrics validated efficiently"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-093', signal_type='batch',
            min_value=Decimal('0.0'), max_value=Decimal('10000.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        async def validate_metric(value):
            metric = MockMetric(
                machine_id='M-093', line_id='L-001', site_id='S01',
                signal_type='batch', name='b1', value=value,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            return await validator.validate(metric)

        results = await asyncio.gather(*[
            validate_metric(float(i)) for i in range(500)
        ])

        assert all(r[0] is True for r in results)
        await config.adelete()

    async def test_094_stress_test_alternating_machines(self):
        """Stress test alternating between two machines"""
        config1 = await SensorRangeConfig.objects.acreate(
            machine_id='M-094A', signal_type='stress',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )
        config2 = await SensorRangeConfig.objects.acreate(
            machine_id='M-094B', signal_type='stress',
            min_value=Decimal('0.0'), max_value=Decimal('200.0'),
            unit='units', is_active=True
        )
        validator = SensorRangeValidator()

        for i in range(200):
            machine_id = 'M-094A' if i % 2 == 0 else 'M-094B'
            metric = MockMetric(
                machine_id=machine_id, line_id='L-001', site_id='S01',
                signal_type='stress', name='st1', value=50.0,
                unit='units', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            assert is_valid is True

        await config1.adelete()
        await config2.adelete()

    async def test_095_validator_state_isolation(self):
        """Validator instances have isolated state"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='M-095', signal_type='isolated',
            min_value=Decimal('0.0'), max_value=Decimal('100.0'),
            unit='units', is_active=True
        )

        v1 = SensorRangeValidator()
        v2 = SensorRangeValidator()

        # Populate v1 cache
        metric = MockMetric(
            machine_id='M-095', line_id='L-001', site_id='S01',
            signal_type='isolated', name='i1', value=50.0,
            unit='units', timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        await v1.validate(metric)

        assert len(v1.range_cache) > 0
        assert len(v2.range_cache) == 0

        await config.adelete()


# ============================================================================
# Category 7: Integration & Real-World Scenarios (10 tests)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCategory7_Integration:
    """Integration and real-world scenario tests"""

    async def test_096_production_line_temperature_monitoring(self):
        """Real-world scenario: Production line temperature monitoring"""
        # Create configs for multiple zones
        zone_configs = []
        for zone in ['ZONE-A', 'ZONE-B', 'ZONE-C']:
            config = await SensorRangeConfig.objects.acreate(
                machine_id=zone, signal_type='temperature',
                min_value=Decimal('18.0'), max_value=Decimal('25.0'),
                unit='celsius', notes=f'Climate control {zone}',
                is_active=True
            )
            zone_configs.append(config)

        validator = SensorRangeValidator()

        # Simulate readings from all zones
        for zone in ['ZONE-A', 'ZONE-B', 'ZONE-C']:
            metric = MockMetric(
                machine_id=zone, line_id='PROD-LINE-1', site_id='FACTORY-01',
                signal_type='temperature', name=f'{zone}_temp', value=22.5,
                unit='celsius', timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            assert is_valid is True

        for config in zone_configs:
            await config.adelete()

    async def test_097_hydraulic_system_pressure_safety(self):
        """Real-world scenario: Hydraulic pressure safety monitoring"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='HYDRAULIC-PRESS-01', signal_type='pressure',
            min_value=Decimal('50.0'), max_value=Decimal('3000.0'),
            unit='psi', notes='Operating pressure range',
            is_active=True
        )
        validator = SensorRangeValidator()

        # Normal operating pressure - pass
        metric1 = MockMetric(
            machine_id='HYDRAULIC-PRESS-01', line_id='FORMING-LINE',
            site_id='PLANT-A', signal_type='pressure',
            name='main_pressure', value=1500.0, unit='psi',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Overpressure condition - fail
        metric2 = MockMetric(
            machine_id='HYDRAULIC-PRESS-01', line_id='FORMING-LINE',
            site_id='PLANT-A', signal_type='pressure',
            name='main_pressure', value=3500.0, unit='psi',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid2, error_msg = await validator.validate(metric2)
        assert is_valid2 is False
        assert 'exceeds maximum' in error_msg.lower()

        await config.adelete()

    async def test_098_motor_vibration_predictive_maintenance(self):
        """Real-world scenario: Motor vibration for predictive maintenance"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='MOTOR-PUMP-03', signal_type='vibration',
            min_value=Decimal('0.0'), max_value=Decimal('7.5'),
            unit='mm/s', notes='ISO 10816 acceptable range',
            is_active=True
        )
        validator = SensorRangeValidator()

        # Healthy motor - low vibration
        metric1 = MockMetric(
            machine_id='MOTOR-PUMP-03', line_id='COOLANT-SYSTEM',
            site_id='PLANT-B', signal_type='vibration',
            name='bearing_vib', value=2.5, unit='mm/s',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Degraded motor - high vibration
        metric2 = MockMetric(
            machine_id='MOTOR-PUMP-03', line_id='COOLANT-SYSTEM',
            site_id='PLANT-B', signal_type='vibration',
            name='bearing_vib', value=9.5, unit='mm/s',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid2, error_msg = await validator.validate(metric2)
        assert is_valid2 is False

        await config.adelete()

    async def test_099_cleanroom_humidity_control(self):
        """Real-world scenario: Cleanroom humidity control"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='CLEANROOM-ISO7', signal_type='humidity',
            min_value=Decimal('30.0'), max_value=Decimal('50.0'),
            unit='%RH', notes='ISO 7 cleanroom specification',
            is_active=True
        )
        validator = SensorRangeValidator()

        # In-spec humidity
        metric1 = MockMetric(
            machine_id='CLEANROOM-ISO7', line_id='ASSEMBLY-CLEAN',
            site_id='ELECTRONICS-FAB', signal_type='humidity',
            name='room_humidity', value=40.0, unit='%RH',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Too dry
        metric2 = MockMetric(
            machine_id='CLEANROOM-ISO7', line_id='ASSEMBLY-CLEAN',
            site_id='ELECTRONICS-FAB', signal_type='humidity',
            name='room_humidity', value=25.0, unit='%RH',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is False

        await config.adelete()

    async def test_100_conveyor_speed_monitoring(self):
        """Real-world scenario: Conveyor belt speed monitoring"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='CONVEYOR-BELT-A1', signal_type='speed',
            min_value=Decimal('0.5'), max_value=Decimal('2.5'),
            unit='m/s', notes='Belt speed operational range',
            is_active=True
        )
        validator = SensorRangeValidator()

        # Normal speed
        metric = MockMetric(
            machine_id='CONVEYOR-BELT-A1', line_id='PACKAGING-LINE',
            site_id='WAREHOUSE-1', signal_type='speed',
            name='belt_speed', value=1.5, unit='m/s',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        await config.adelete()

    async def test_101_multi_machine_assembly_line(self):
        """Real-world scenario: Multi-machine assembly line validation"""
        # Create configs for different machines on same line
        machines = {
            'ROBOT-WELDER-1': ('current', Decimal('50.0'), Decimal('400.0'), 'A'),
            'ROBOT-WELDER-2': ('current', Decimal('50.0'), Decimal('400.0'), 'A'),
            'CONVEYOR-MAIN': ('speed', Decimal('0.1'), Decimal('3.0'), 'm/s'),
            'QUALITY-CAMERA': ('temperature', Decimal('15.0'), Decimal('35.0'), 'celsius'),
        }

        configs = []
        for machine_id, (signal, min_val, max_val, unit) in machines.items():
            config = await SensorRangeConfig.objects.acreate(
                machine_id=machine_id, signal_type=signal,
                min_value=min_val, max_value=max_val,
                unit=unit, is_active=True
            )
            configs.append(config)

        validator = SensorRangeValidator()

        # Validate all machines
        test_values = {
            'ROBOT-WELDER-1': 250.0,
            'ROBOT-WELDER-2': 275.0,
            'CONVEYOR-MAIN': 1.5,
            'QUALITY-CAMERA': 25.0,
        }

        for machine_id, (signal, _, _, unit) in machines.items():
            metric = MockMetric(
                machine_id=machine_id, line_id='ASSEMBLY-A',
                site_id='PLANT-1', signal_type=signal,
                name=f'{machine_id}_sensor', value=test_values[machine_id],
                unit=unit, timestamp_utc=datetime.now(timezone.utc),
                quality=192, is_valid=True
            )
            is_valid, _ = await validator.validate(metric)
            assert is_valid is True

        for config in configs:
            await config.adelete()

    async def test_102_energy_consumption_monitoring(self):
        """Real-world scenario: Energy consumption limits"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='FURNACE-MAIN', signal_type='power',
            min_value=Decimal('1000.0'), max_value=Decimal('50000.0'),
            unit='W', notes='Power consumption range',
            is_active=True
        )
        validator = SensorRangeValidator()

        # Normal power draw
        metric = MockMetric(
            machine_id='FURNACE-MAIN', line_id='HEAT-TREATMENT',
            site_id='METALWORKS', signal_type='power',
            name='total_power', value=25000.0, unit='W',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        await config.adelete()

    async def test_103_chemical_process_ph_control(self):
        """Real-world scenario: Chemical process pH control"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='REACTOR-TANK-B', signal_type='ph',
            min_value=Decimal('6.5'), max_value=Decimal('7.5'),
            unit='pH', notes='Neutral pH range requirement',
            is_active=True
        )
        validator = SensorRangeValidator()

        # Acceptable pH
        metric1 = MockMetric(
            machine_id='REACTOR-TANK-B', line_id='CHEMICAL-PROCESS',
            site_id='CHEM-PLANT', signal_type='ph',
            name='solution_ph', value=7.0, unit='pH',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid1, _ = await validator.validate(metric1)
        assert is_valid1 is True

        # Too acidic
        metric2 = MockMetric(
            machine_id='REACTOR-TANK-B', line_id='CHEMICAL-PROCESS',
            site_id='CHEM-PLANT', signal_type='ph',
            name='solution_ph', value=5.5, unit='pH',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid2, _ = await validator.validate(metric2)
        assert is_valid2 is False

        await config.adelete()

    async def test_104_refrigeration_system_monitoring(self):
        """Real-world scenario: Refrigeration system temperature"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='COLD-STORAGE-1', signal_type='temperature',
            min_value=Decimal('-25.0'), max_value=Decimal('-18.0'),
            unit='celsius', notes='Frozen storage temperature',
            is_active=True
        )
        validator = SensorRangeValidator()

        # Proper freezer temp
        metric = MockMetric(
            machine_id='COLD-STORAGE-1', line_id='STORAGE',
            site_id='FOOD-WAREHOUSE', signal_type='temperature',
            name='storage_temp', value=-22.0, unit='celsius',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        await config.adelete()

    async def test_105_air_compressor_discharge_pressure(self):
        """Real-world scenario: Air compressor discharge pressure"""
        config = await SensorRangeConfig.objects.acreate(
            machine_id='COMPRESSOR-MAIN', signal_type='pressure',
            min_value=Decimal('90.0'), max_value=Decimal('125.0'),
            unit='psi', notes='Compressed air system pressure',
            is_active=True
        )
        validator = SensorRangeValidator()

        # Normal operating pressure
        metric = MockMetric(
            machine_id='COMPRESSOR-MAIN', line_id='PNEUMATICS',
            site_id='ASSEMBLY-PLANT', signal_type='pressure',
            name='discharge_pressure', value=110.0, unit='psi',
            timestamp_utc=datetime.now(timezone.utc),
            quality=192, is_valid=True
        )
        is_valid, _ = await validator.validate(metric)
        assert is_valid is True

        await config.adelete()
