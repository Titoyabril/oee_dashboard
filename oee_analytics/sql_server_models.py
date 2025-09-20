"""
OEE Dashboard - SQL Server Django Models
Production-Ready Models for Manufacturing Analytics
Maps to SQL Server schema for high-performance OEE calculations
"""

from django.db import models
from django.utils import timezone as django_timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


# =============================================
# 1. MASTER DATA MODELS
# =============================================

class Plant(models.Model):
    """Manufacturing plant/facility"""
    plant_id = models.CharField(max_length=20, primary_key=True)
    plant_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC')
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'Plants'
        indexes = [
            models.Index(fields=['is_active'], condition=models.Q(is_active=True), name='idx_plants_active'),
        ]
    
    def __str__(self):
        return f"{self.plant_id} - {self.plant_name}"


class Area(models.Model):
    """Production area within a plant"""
    area_id = models.CharField(max_length=30, primary_key=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, to_field='plant_id', db_column='plant_id')
    area_name = models.CharField(max_length=100)
    description = models.TextField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'Areas'
        indexes = [
            models.Index(fields=['plant']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.area_id} - {self.area_name}"


class ProductionLine(models.Model):
    """Production line within an area"""
    line_id = models.CharField(max_length=50, primary_key=True)
    area = models.ForeignKey(Area, on_delete=models.PROTECT, to_field='area_id', db_column='area_id')
    line_name = models.CharField(max_length=100)
    line_type = models.CharField(max_length=50, blank=True, null=True)  # Assembly, Packaging, etc.
    theoretical_cycle_time_seconds = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    target_availability_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('85.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    target_performance_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('95.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    target_quality_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('99.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ProductionLines'
        indexes = [
            models.Index(fields=['area']),
            models.Index(fields=['is_active']),
        ]
    
    @property
    def target_oee_percent(self):
        """Calculate target OEE percentage"""
        return (self.target_availability_percent / 100) * \
               (self.target_performance_percent / 100) * \
               (self.target_quality_percent / 100) * 100
    
    def __str__(self):
        return f"{self.line_id} - {self.line_name}"


class Machine(models.Model):
    """Individual machine/station within a production line"""
    machine_id = models.CharField(max_length=50, primary_key=True)
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    machine_name = models.CharField(max_length=100)
    machine_type = models.CharField(max_length=50, blank=True, null=True)  # Station, Robot, Conveyor, etc.
    asset_number = models.CharField(max_length=50, blank=True, null=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    installation_date = models.DateField(blank=True, null=True)
    theoretical_cycle_time_seconds = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    max_temperature = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    max_pressure = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'Machines'
        indexes = [
            models.Index(fields=['line']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.machine_id} - {self.machine_name}"


class Product(models.Model):
    """Product/part definitions"""
    product_id = models.CharField(max_length=50, primary_key=True)
    product_name = models.CharField(max_length=200)
    product_family = models.CharField(max_length=100, blank=True, null=True)
    sku = models.CharField(max_length=100, blank=True, null=True)
    standard_cycle_time_seconds = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    target_units_per_hour = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'Products'
        indexes = [
            models.Index(fields=['product_family']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.product_id} - {self.product_name}"


class Recipe(models.Model):
    """Production recipes/procedures"""
    recipe_id = models.CharField(max_length=50, primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, to_field='product_id', db_column='product_id')
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    recipe_name = models.CharField(max_length=200)
    version = models.CharField(max_length=20, blank=True, null=True)
    target_cycle_time_seconds = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    setup_time_minutes = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0'))]
    )
    teardown_time_minutes = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0'))]
    )
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'Recipes'
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['line']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.recipe_id} - {self.recipe_name}"


class ShiftPattern(models.Model):
    """Shift pattern definitions"""
    shift_pattern_id = models.AutoField(primary_key=True)
    pattern_name = models.CharField(max_length=100)
    shift_1_start = models.TimeField()
    shift_1_end = models.TimeField()
    shift_2_start = models.TimeField(blank=True, null=True)
    shift_2_end = models.TimeField(blank=True, null=True)
    shift_3_start = models.TimeField(blank=True, null=True)
    shift_3_end = models.TimeField(blank=True, null=True)
    break_1_start = models.TimeField(blank=True, null=True)
    break_1_duration_minutes = models.IntegerField(blank=True, null=True)
    break_2_start = models.TimeField(blank=True, null=True)
    break_2_duration_minutes = models.IntegerField(blank=True, null=True)
    lunch_start = models.TimeField(blank=True, null=True)
    lunch_duration_minutes = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ShiftPatterns'
        indexes = [
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.pattern_name


class DowntimeReason(models.Model):
    """Downtime reason code definitions"""
    reason_code = models.CharField(max_length=20, primary_key=True)
    reason_category = models.CharField(max_length=50)  # PLANNED, UNPLANNED
    reason_subcategory = models.CharField(max_length=50, blank=True, null=True)
    reason_description = models.CharField(max_length=200)
    mttr_target_minutes = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0'))]
    )
    is_planned = models.BooleanField(default=False)
    severity_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'DowntimeReasons'
        indexes = [
            models.Index(fields=['reason_category']),
            models.Index(fields=['is_planned']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.reason_code} - {self.reason_description}"


class QualityDefect(models.Model):
    """Quality defect code definitions"""
    defect_code = models.CharField(max_length=20, primary_key=True)
    defect_category = models.CharField(max_length=50)
    defect_description = models.CharField(max_length=200)
    severity_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    rework_possible = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=django_timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'QualityDefects'
        indexes = [
            models.Index(fields=['defect_category']),
            models.Index(fields=['severity_level']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.defect_code} - {self.defect_description}"


# =============================================
# 2. TIME-SERIES DATA MODELS
# =============================================

class SQLMachineEvent(models.Model):
    """High-frequency machine telemetry events"""
    event_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, to_field='machine_id', db_column='machine_id')
    timestamp_utc = models.DateTimeField(db_index=True)
    event_type = models.CharField(max_length=50)  # CYCLE_START, CYCLE_END, ALARM, SENSOR_DATA
    event_value = models.DecimalField(max_digits=18, decimal_places=6, blank=True, null=True)
    event_text = models.CharField(max_length=500, blank=True, null=True)
    payload_json = models.TextField(blank=True, null=True)  # Additional flexible data
    source_system = models.CharField(max_length=50, default='PLC')
    quality_score = models.SmallIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'MachineEvents'
        indexes = [
            models.Index(fields=['machine', 'timestamp_utc']),  # Clustered equivalent
            models.Index(fields=['timestamp_utc']),
            models.Index(fields=['event_type']),
            models.Index(fields=['source_system']),
            # Recent data index (last 72 hours) - approximated with conditional
            models.Index(fields=['machine', 'timestamp_utc', 'event_type']),
        ]
        # Note: Partitioning would be handled at database level
    
    def __str__(self):
        return f"{self.machine_id} - {self.timestamp_utc} - {self.event_type}"


class ProductionCycle(models.Model):
    """Completed production cycles/units"""
    
    STATUS_CHOICES = [
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('ABORTED', 'Aborted'),
    ]
    
    cycle_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, to_field='machine_id', db_column='machine_id')
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, to_field='recipe_id', db_column='recipe_id', blank=True, null=True)
    start_timestamp_utc = models.DateTimeField()
    end_timestamp_utc = models.DateTimeField(blank=True, null=True)
    cycle_time_seconds = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    target_cycle_time_seconds = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    good_parts_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    scrap_parts_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    rework_parts_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    cycle_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RUNNING')
    operator_id = models.CharField(max_length=50, blank=True, null=True)
    shift_id = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'ProductionCycles'
        indexes = [
            models.Index(fields=['machine', 'start_timestamp_utc']),  # Clustered equivalent
            models.Index(fields=['line', 'start_timestamp_utc']),
            models.Index(fields=['recipe']),
            models.Index(fields=['cycle_status']),
            models.Index(fields=['shift_id']),
            # Covering index for OEE calculations
            models.Index(fields=['machine', 'start_timestamp_utc'], include=['cycle_time_seconds', 'good_parts_count', 'scrap_parts_count', 'target_cycle_time_seconds'], name='idx_cycle_oee_covering'),
        ]
    
    @property
    def total_parts_count(self):
        return self.good_parts_count + self.scrap_parts_count + self.rework_parts_count
    
    @property
    def is_good_cycle(self):
        return self.scrap_parts_count == 0
    
    def __str__(self):
        return f"Cycle {self.cycle_id} - {self.machine_id} - {self.start_timestamp_utc}"


class SQLDowntimeEvent(models.Model):
    """Machine downtime events"""
    downtime_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, to_field='machine_id', db_column='machine_id')
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    start_timestamp_utc = models.DateTimeField()
    end_timestamp_utc = models.DateTimeField(blank=True, null=True)
    duration_minutes = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0'))]
    )
    reason_code = models.ForeignKey(DowntimeReason, on_delete=models.PROTECT, to_field='reason_code', db_column='reason_code')
    sub_reason = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(max_length=500, blank=True, null=True)
    operator_id = models.CharField(max_length=50, blank=True, null=True)
    technician_id = models.CharField(max_length=50, blank=True, null=True)
    shift_id = models.CharField(max_length=20, blank=True, null=True)
    is_planned = models.BooleanField(default=False)
    severity_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    repair_cost = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0'))]
    )
    parts_used = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'DowntimeEvents'
        indexes = [
            models.Index(fields=['machine', 'start_timestamp_utc']),  # Clustered equivalent
            models.Index(fields=['line', 'start_timestamp_utc']),
            models.Index(fields=['reason_code']),
            models.Index(fields=['is_planned']),
            models.Index(fields=['shift_id']),
            # Covering index for Pareto analysis
            models.Index(fields=['reason_code', 'start_timestamp_utc'], include=['duration_minutes', 'machine', 'line'], name='idx_downtime_pareto_covering'),
        ]
    
    @property
    def is_ongoing(self):
        return self.end_timestamp_utc is None
    
    def __str__(self):
        return f"Downtime {self.downtime_id} - {self.machine_id} - {self.reason_code_id}"


class SQLQualityEvent(models.Model):
    """Quality inspection and defect events"""
    quality_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, to_field='machine_id', db_column='machine_id')
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    cycle = models.ForeignKey(ProductionCycle, on_delete=models.PROTECT, blank=True, null=True)
    timestamp_utc = models.DateTimeField()
    defect_code = models.ForeignKey(QualityDefect, on_delete=models.PROTECT, to_field='defect_code', db_column='defect_code', blank=True, null=True)
    parts_inspected = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    parts_passed = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    parts_failed = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    parts_reworked = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    inspector_id = models.CharField(max_length=50, blank=True, null=True)
    inspection_method = models.CharField(max_length=50, blank=True, null=True)  # MANUAL, VISION, CMM
    shift_id = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'QualityEvents'
        indexes = [
            models.Index(fields=['machine', 'timestamp_utc']),  # Clustered equivalent
            models.Index(fields=['line', 'timestamp_utc']),
            models.Index(fields=['defect_code']),
            models.Index(fields=['cycle']),
            models.Index(fields=['shift_id']),
        ]
    
    @property
    def pass_rate(self):
        if self.parts_inspected > 0:
            return (self.parts_passed / self.parts_inspected) * 100
        return 0
    
    def __str__(self):
        return f"Quality {self.quality_id} - {self.machine_id} - {self.timestamp_utc}"


# =============================================
# 3. PRE-AGGREGATED ROLLUP MODELS
# =============================================

class OEERollupHourly(models.Model):
    """Hourly OEE performance rollups"""
    rollup_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, to_field='machine_id', db_column='machine_id')
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    bucket_start_utc = models.DateTimeField()
    bucket_end_utc = models.DateTimeField()
    shift_id = models.CharField(max_length=20, blank=True, null=True)
    
    # Production metrics
    planned_production_time_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    actual_production_time_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    downtime_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    planned_downtime_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    unplanned_downtime_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Cycle metrics
    total_cycles = models.IntegerField(default=0)
    good_cycles = models.IntegerField(default=0)
    scrap_cycles = models.IntegerField(default=0)
    rework_cycles = models.IntegerField(default=0)
    average_cycle_time_seconds = models.DecimalField(max_digits=10, decimal_places=3)
    target_cycle_time_seconds = models.DecimalField(max_digits=10, decimal_places=3)
    
    # OEE Components
    availability_percent = models.DecimalField(max_digits=5, decimal_places=2)
    performance_percent = models.DecimalField(max_digits=5, decimal_places=2)
    quality_percent = models.DecimalField(max_digits=5, decimal_places=2)
    oee_percent = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Additional metrics
    throughput_units_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    efficiency_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    utilization_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    
    # Top downtime reason
    top_downtime_reason = models.CharField(max_length=20, blank=True, null=True)
    top_downtime_minutes = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'OEE_Rollup_Hourly'
        indexes = [
            models.Index(fields=['machine', 'bucket_start_utc']),
            models.Index(fields=['line', 'bucket_start_utc']),
            models.Index(fields=['shift_id']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['machine', 'bucket_start_utc'], name='unique_machine_bucket'),
        ]
    
    def __str__(self):
        return f"Hourly OEE {self.machine_id} - {self.bucket_start_utc}"


class OEERollupShift(models.Model):
    """Shift-level OEE performance rollups"""
    rollup_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, to_field='machine_id', db_column='machine_id')
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    shift_date = models.DateField()
    shift_number = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    shift_start_utc = models.DateTimeField()
    shift_end_utc = models.DateTimeField()
    
    # Production metrics (same structure as hourly)
    planned_production_time_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    actual_production_time_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    downtime_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    planned_downtime_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    unplanned_downtime_minutes = models.DecimalField(max_digits=8, decimal_places=2)
    
    total_cycles = models.IntegerField(default=0)
    good_cycles = models.IntegerField(default=0)
    scrap_cycles = models.IntegerField(default=0)
    rework_cycles = models.IntegerField(default=0)
    average_cycle_time_seconds = models.DecimalField(max_digits=10, decimal_places=3)
    target_cycle_time_seconds = models.DecimalField(max_digits=10, decimal_places=3)
    
    availability_percent = models.DecimalField(max_digits=5, decimal_places=2)
    performance_percent = models.DecimalField(max_digits=5, decimal_places=2)
    quality_percent = models.DecimalField(max_digits=5, decimal_places=2)
    oee_percent = models.DecimalField(max_digits=5, decimal_places=2)
    
    throughput_units_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'OEE_Rollup_Shift'
        indexes = [
            models.Index(fields=['machine', 'shift_date']),
            models.Index(fields=['line', 'shift_date']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['machine', 'shift_date', 'shift_number'], name='unique_machine_shift'),
        ]
    
    def __str__(self):
        return f"Shift OEE {self.machine_id} - {self.shift_date} Shift {self.shift_number}"


class OEERollupDaily(models.Model):
    """Daily OEE performance rollups"""
    rollup_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, to_field='machine_id', db_column='machine_id')
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    date_utc = models.DateField()
    
    # Production metrics (same structure as hourly/shift)
    planned_production_time_minutes = models.DecimalField(max_digits=10, decimal_places=2)
    actual_production_time_minutes = models.DecimalField(max_digits=10, decimal_places=2)
    downtime_minutes = models.DecimalField(max_digits=10, decimal_places=2)
    planned_downtime_minutes = models.DecimalField(max_digits=10, decimal_places=2)
    unplanned_downtime_minutes = models.DecimalField(max_digits=10, decimal_places=2)
    
    total_cycles = models.IntegerField(default=0)
    good_cycles = models.IntegerField(default=0)
    scrap_cycles = models.IntegerField(default=0)
    rework_cycles = models.IntegerField(default=0)
    average_cycle_time_seconds = models.DecimalField(max_digits=10, decimal_places=3)
    target_cycle_time_seconds = models.DecimalField(max_digits=10, decimal_places=3)
    
    availability_percent = models.DecimalField(max_digits=5, decimal_places=2)
    performance_percent = models.DecimalField(max_digits=5, decimal_places=2)
    quality_percent = models.DecimalField(max_digits=5, decimal_places=2)
    oee_percent = models.DecimalField(max_digits=5, decimal_places=2)
    
    throughput_units_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'OEE_Rollup_Daily'
        indexes = [
            models.Index(fields=['machine', 'date_utc']),
            models.Index(fields=['line', 'date_utc']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['machine', 'date_utc'], name='unique_machine_date'),
        ]
    
    def __str__(self):
        return f"Daily OEE {self.machine_id} - {self.date_utc}"


# =============================================
# 4. SCHEDULE AND OPERATIONS MODELS
# =============================================

class ProductionSchedule(models.Model):
    """Production schedule and work orders"""
    
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    schedule_id = models.BigAutoField(primary_key=True)
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, to_field='recipe_id', db_column='recipe_id')
    planned_start_utc = models.DateTimeField()
    planned_end_utc = models.DateTimeField()
    planned_quantity = models.IntegerField(validators=[MinValueValidator(1)])
    actual_start_utc = models.DateTimeField(blank=True, null=True)
    actual_end_utc = models.DateTimeField(blank=True, null=True)
    actual_quantity = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0)])
    schedule_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    priority_level = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    work_order_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'ProductionSchedule'
        indexes = [
            models.Index(fields=['line', 'planned_start_utc']),
            models.Index(fields=['schedule_status']),
            models.Index(fields=['work_order_number']),
        ]
    
    def __str__(self):
        return f"Schedule {self.schedule_id} - {self.line_id} - {self.work_order_number}"


class OperatorShift(models.Model):
    """Operator shift assignments"""
    shift_assignment_id = models.BigAutoField(primary_key=True)
    operator_id = models.CharField(max_length=50)
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, to_field='line_id', db_column='line_id')
    shift_date = models.DateField()
    shift_number = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    start_time_utc = models.DateTimeField()
    end_time_utc = models.DateTimeField(blank=True, null=True)
    role = models.CharField(max_length=50, blank=True, null=True)  # OPERATOR, LEAD, TECHNICIAN
    created_at = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'OperatorShifts'
        indexes = [
            models.Index(fields=['operator_id', 'shift_date']),
            models.Index(fields=['line', 'shift_date']),
        ]
    
    def __str__(self):
        return f"Operator {self.operator_id} - {self.line_id} - {self.shift_date}"


# =============================================
# 5. AUDIT AND MONITORING MODELS
# =============================================

class DataRetentionPolicy(models.Model):
    """Data retention policy definitions"""
    policy_id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=128)
    retention_days = models.IntegerField(validators=[MinValueValidator(1)])
    archive_after_days = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(1)])
    compression_enabled = models.BooleanField(default=True)
    policy_description = models.CharField(max_length=500, blank=True, null=True)
    last_cleanup_utc = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'DataRetentionPolicies'
        indexes = [
            models.Index(fields=['table_name']),
        ]
    
    def __str__(self):
        return f"{self.table_name} - {self.retention_days} days"


class ConfigurationAudit(models.Model):
    """Audit trail for configuration changes"""
    
    OPERATION_CHOICES = [
        ('INSERT', 'Insert'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
    ]
    
    audit_id = models.BigAutoField(primary_key=True)
    table_name = models.CharField(max_length=128)
    record_id = models.CharField(max_length=100)
    operation_type = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    old_values = models.TextField(blank=True, null=True)
    new_values = models.TextField(blank=True, null=True)
    changed_by = models.CharField(max_length=100)
    changed_at = models.DateTimeField(default=django_timezone.now)
    client_ip = models.CharField(max_length=45, blank=True, null=True)
    
    class Meta:
        db_table = 'ConfigurationAudit'
        indexes = [
            models.Index(fields=['table_name', 'changed_at']),
            models.Index(fields=['changed_by', 'changed_at']),
        ]
    
    def __str__(self):
        return f"{self.operation_type} on {self.table_name} by {self.changed_by}"


class QueryPerformanceLog(models.Model):
    """Query performance monitoring"""
    log_id = models.BigAutoField(primary_key=True)
    query_type = models.CharField(max_length=100)
    execution_time_ms = models.IntegerField()
    cpu_time_ms = models.IntegerField(blank=True, null=True)
    logical_reads = models.BigIntegerField(blank=True, null=True)
    physical_reads = models.BigIntegerField(blank=True, null=True)
    row_count = models.BigIntegerField(blank=True, null=True)
    query_hash = models.BinaryField(max_length=8, blank=True, null=True)
    plan_hash = models.BinaryField(max_length=8, blank=True, null=True)
    execution_timestamp = models.DateTimeField(default=django_timezone.now)
    
    class Meta:
        db_table = 'QueryPerformanceLog'
        indexes = [
            models.Index(fields=['query_type', 'execution_timestamp']),
            models.Index(fields=['execution_time_ms', 'execution_timestamp']),
        ]
    
    def __str__(self):
        return f"{self.query_type} - {self.execution_time_ms}ms"