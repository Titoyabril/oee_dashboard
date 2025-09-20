"""
OEE Dashboard - SQL Server Django REST Serializers
High-Performance API Serializers for Manufacturing Analytics
Optimized for Real-Time Dashboard Consumption
"""

from rest_framework import serializers
from decimal import Decimal
from .sql_server_models import (
    Plant, Area, ProductionLine, Machine, Product, Recipe,
    MachineEvent, ProductionCycle, DowntimeEvent, QualityEvent,
    OEERollupHourly, OEERollupShift, OEERollupDaily,
    DowntimeReason, QualityDefect, ProductionSchedule
)


# =============================================
# 1. MASTER DATA SERIALIZERS
# =============================================

class PlantSerializer(serializers.ModelSerializer):
    """Plant/facility serializer"""
    
    class Meta:
        model = Plant
        fields = '__all__'
        read_only_fields = ('created_at',)


class AreaSerializer(serializers.ModelSerializer):
    """Production area serializer"""
    plant_name = serializers.CharField(source='plant.plant_name', read_only=True)
    
    class Meta:
        model = Area
        fields = '__all__'
        read_only_fields = ('created_at',)


class ProductionLineSerializer(serializers.ModelSerializer):
    """Production line serializer with performance targets"""
    area_name = serializers.CharField(source='area.area_name', read_only=True)
    plant_name = serializers.CharField(source='area.plant.plant_name', read_only=True)
    target_oee_percent = serializers.SerializerMethodField()
    machine_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ProductionLine
        fields = '__all__'
        read_only_fields = ('created_at',)
    
    def get_target_oee_percent(self, obj):
        """Calculate target OEE percentage"""
        return obj.target_oee_percent


class MachineSerializer(serializers.ModelSerializer):
    """Machine/station serializer with hierarchy info"""
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    area_name = serializers.CharField(source='line.area.area_name', read_only=True)
    plant_name = serializers.CharField(source='line.area.plant.plant_name', read_only=True)
    
    class Meta:
        model = Machine
        fields = '__all__'
        read_only_fields = ('created_at',)


class ProductSerializer(serializers.ModelSerializer):
    """Product definition serializer"""
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ('created_at',)


class RecipeSerializer(serializers.ModelSerializer):
    """Recipe/procedure serializer"""
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    
    class Meta:
        model = Recipe
        fields = '__all__'
        read_only_fields = ('created_at',)


class DowntimeReasonSerializer(serializers.ModelSerializer):
    """Downtime reason code serializer"""
    
    class Meta:
        model = DowntimeReason
        fields = '__all__'
        read_only_fields = ('created_at',)


class QualityDefectSerializer(serializers.ModelSerializer):
    """Quality defect code serializer"""
    
    class Meta:
        model = QualityDefect
        fields = '__all__'
        read_only_fields = ('created_at',)


# =============================================
# 2. TIME-SERIES DATA SERIALIZERS
# =============================================

class MachineEventSerializer(serializers.ModelSerializer):
    """Machine telemetry event serializer"""
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)
    
    class Meta:
        model = MachineEvent
        fields = '__all__'
        read_only_fields = ('event_id', 'created_at')
    
    def validate_timestamp_utc(self, value):
        """Ensure timestamp is not in future"""
        from django.utils import timezone
        if value > timezone.now():
            raise serializers.ValidationError("Timestamp cannot be in the future")
        return value


class MachineEventBatchSerializer(serializers.Serializer):
    """Batch machine event insertion for high throughput"""
    events = MachineEventSerializer(many=True)
    
    def create(self, validated_data):
        """Bulk create events for performance"""
        events_data = validated_data['events']
        events = [MachineEvent(**event_data) for event_data in events_data]
        return MachineEvent.objects.bulk_create(events, batch_size=1000)


class ProductionCycleSerializer(serializers.ModelSerializer):
    """Production cycle serializer"""
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    recipe_name = serializers.CharField(source='recipe.recipe_name', read_only=True)
    total_parts_count = serializers.SerializerMethodField()
    is_good_cycle = serializers.SerializerMethodField()
    performance_percent = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductionCycle
        fields = '__all__'
        read_only_fields = ('cycle_id', 'created_at')
    
    def get_total_parts_count(self, obj):
        return obj.total_parts_count
    
    def get_is_good_cycle(self, obj):
        return obj.is_good_cycle
    
    def get_performance_percent(self, obj):
        """Calculate cycle performance vs target"""
        if obj.target_cycle_time_seconds and obj.cycle_time_seconds:
            return float((obj.target_cycle_time_seconds / obj.cycle_time_seconds) * 100)
        return None
    
    def validate(self, data):
        """Validate cycle data consistency"""
        if data.get('end_timestamp_utc') and data.get('start_timestamp_utc'):
            if data['end_timestamp_utc'] <= data['start_timestamp_utc']:
                raise serializers.ValidationError("End timestamp must be after start timestamp")
        return data


class DowntimeEventSerializer(serializers.ModelSerializer):
    """Downtime event serializer"""
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    reason_description = serializers.CharField(source='reason_code.reason_description', read_only=True)
    reason_category = serializers.CharField(source='reason_code.reason_category', read_only=True)
    is_ongoing = serializers.SerializerMethodField()
    mttr_target_minutes = serializers.CharField(source='reason_code.mttr_target_minutes', read_only=True)
    
    class Meta:
        model = DowntimeEvent
        fields = '__all__'
        read_only_fields = ('downtime_id', 'created_at')
    
    def get_is_ongoing(self, obj):
        return obj.is_ongoing
    
    def validate(self, data):
        """Validate downtime event data"""
        if data.get('end_timestamp_utc') and data.get('start_timestamp_utc'):
            if data['end_timestamp_utc'] <= data['start_timestamp_utc']:
                raise serializers.ValidationError("End timestamp must be after start timestamp")
            
            # Calculate duration if not provided
            if not data.get('duration_minutes'):
                from django.utils import timezone
                duration = data['end_timestamp_utc'] - data['start_timestamp_utc']
                data['duration_minutes'] = Decimal(str(duration.total_seconds() / 60))
        
        return data


class QualityEventSerializer(serializers.ModelSerializer):
    """Quality inspection event serializer"""
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    defect_description = serializers.CharField(source='defect_code.defect_description', read_only=True)
    defect_category = serializers.CharField(source='defect_code.defect_category', read_only=True)
    pass_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = QualityEvent
        fields = '__all__'
        read_only_fields = ('quality_id', 'created_at')
    
    def get_pass_rate(self, obj):
        return obj.pass_rate
    
    def validate(self, data):
        """Validate quality event data consistency"""
        parts_inspected = data.get('parts_inspected', 0)
        parts_passed = data.get('parts_passed', 0)
        parts_failed = data.get('parts_failed', 0)
        parts_reworked = data.get('parts_reworked', 0)
        
        if parts_passed + parts_failed + parts_reworked > parts_inspected:
            raise serializers.ValidationError("Sum of passed, failed, and reworked parts cannot exceed inspected count")
        
        return data


# =============================================
# 3. OEE ROLLUP SERIALIZERS
# =============================================

class OEERollupHourlySerializer(serializers.ModelSerializer):
    """Hourly OEE rollup serializer for dashboard consumption"""
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    area_name = serializers.CharField(source='line.area.area_name', read_only=True)
    plant_name = serializers.CharField(source='line.area.plant.plant_name', read_only=True)
    
    # Target comparisons
    target_oee_percent = serializers.SerializerMethodField()
    oee_variance = serializers.SerializerMethodField()
    efficiency_percent = serializers.SerializerMethodField()
    
    class Meta:
        model = OEERollupHourly
        fields = '__all__'
        read_only_fields = ('rollup_id', 'created_at')
    
    def get_target_oee_percent(self, obj):
        """Calculate target OEE from line targets"""
        line = obj.line
        return float((line.target_availability_percent / 100) * 
                    (line.target_performance_percent / 100) * 
                    (line.target_quality_percent / 100) * 100)
    
    def get_oee_variance(self, obj):
        """Calculate OEE variance from target"""
        target = self.get_target_oee_percent(obj)
        return float(obj.oee_percent - target)
    
    def get_efficiency_percent(self, obj):
        """Calculate overall efficiency"""
        if obj.planned_production_time_minutes > 0:
            return float((obj.actual_production_time_minutes / obj.planned_production_time_minutes) * 100)
        return 0


class OEERollupShiftSerializer(serializers.ModelSerializer):
    """Shift OEE rollup serializer"""
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    area_name = serializers.CharField(source='line.area.area_name', read_only=True)
    plant_name = serializers.CharField(source='line.area.plant.plant_name', read_only=True)
    
    target_oee_percent = serializers.SerializerMethodField()
    oee_variance = serializers.SerializerMethodField()
    
    class Meta:
        model = OEERollupShift
        fields = '__all__'
        read_only_fields = ('rollup_id', 'created_at')
    
    def get_target_oee_percent(self, obj):
        line = obj.line
        return float((line.target_availability_percent / 100) * 
                    (line.target_performance_percent / 100) * 
                    (line.target_quality_percent / 100) * 100)
    
    def get_oee_variance(self, obj):
        target = self.get_target_oee_percent(obj)
        return float(obj.oee_percent - target)


class OEERollupDailySerializer(serializers.ModelSerializer):
    """Daily OEE rollup serializer"""
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    area_name = serializers.CharField(source='line.area.area_name', read_only=True)
    plant_name = serializers.CharField(source='line.area.plant.plant_name', read_only=True)
    
    target_oee_percent = serializers.SerializerMethodField()
    oee_variance = serializers.SerializerMethodField()
    day_of_week = serializers.SerializerMethodField()
    
    class Meta:
        model = OEERollupDaily
        fields = '__all__'
        read_only_fields = ('rollup_id', 'created_at')
    
    def get_target_oee_percent(self, obj):
        line = obj.line
        return float((line.target_availability_percent / 100) * 
                    (line.target_performance_percent / 100) * 
                    (line.target_quality_percent / 100) * 100)
    
    def get_oee_variance(self, obj):
        target = self.get_target_oee_percent(obj)
        return float(obj.oee_percent - target)
    
    def get_day_of_week(self, obj):
        return obj.date_utc.strftime('%A')


# =============================================
# 4. DASHBOARD-SPECIFIC SERIALIZERS
# =============================================

class CurrentShiftOEESerializer(serializers.Serializer):
    """Current shift OEE performance for dashboard"""
    machine_id = serializers.CharField()
    machine_name = serializers.CharField()
    line_name = serializers.CharField()
    area_name = serializers.CharField()
    plant_name = serializers.CharField()
    
    current_shift = serializers.IntegerField()
    shift_start = serializers.DateTimeField()
    shift_end = serializers.DateTimeField()
    shift_elapsed_minutes = serializers.IntegerField()
    shift_total_minutes = serializers.IntegerField()
    
    # OEE metrics
    current_availability_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    current_performance_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    current_quality_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    current_oee_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Production metrics
    shift_total_cycles = serializers.IntegerField()
    shift_good_cycles = serializers.IntegerField()
    shift_scrap_cycles = serializers.IntegerField()
    shift_downtime_minutes = serializers.DecimalField(max_digits=8, decimal_places=2)
    shift_planned_downtime_minutes = serializers.DecimalField(max_digits=8, decimal_places=2)
    
    # Targets and status
    current_throughput_uph = serializers.DecimalField(max_digits=10, decimal_places=2)
    target_oee_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    oee_status = serializers.CharField()
    top_downtime_reason = serializers.CharField(allow_null=True)
    
    # Data freshness
    last_event_timestamp = serializers.DateTimeField(allow_null=True)
    report_timestamp = serializers.DateTimeField()


class LinePerformanceSerializer(serializers.Serializer):
    """Line-level aggregated performance for dashboard"""
    plant_name = serializers.CharField()
    area_name = serializers.CharField()
    line_id = serializers.CharField()
    line_name = serializers.CharField()
    line_type = serializers.CharField()
    
    total_machines = serializers.IntegerField()
    machines_on_target = serializers.IntegerField()
    
    line_availability_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    line_performance_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    line_quality_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    line_oee_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    line_total_cycles = serializers.IntegerField()
    line_good_cycles = serializers.IntegerField()
    line_scrap_cycles = serializers.IntegerField()
    line_downtime_minutes = serializers.DecimalField(max_digits=8, decimal_places=2)
    
    line_avg_throughput_uph = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_total_throughput_uph = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    line_status = serializers.CharField()
    report_timestamp = serializers.DateTimeField()


class TopDowntimeReasonsSerializer(serializers.Serializer):
    """Top downtime reasons for Pareto analysis"""
    reason_code = serializers.CharField()
    reason_description = serializers.CharField()
    reason_category = serializers.CharField()
    reason_subcategory = serializers.CharField()
    severity_level = serializers.IntegerField()
    
    occurrence_count = serializers.IntegerField()
    total_minutes = serializers.DecimalField(max_digits=10, decimal_places=2)
    avg_duration_minutes = serializers.DecimalField(max_digits=10, decimal_places=2)
    percent_of_total_downtime = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    affected_machines = serializers.IntegerField()
    machine_list = serializers.CharField()
    mttr_minutes = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    mttr_target_minutes = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    
    report_timestamp = serializers.DateTimeField()


class MachineHealthIndicatorSerializer(serializers.Serializer):
    """Machine health indicators and scoring"""
    machine_id = serializers.CharField()
    machine_name = serializers.CharField()
    line_id = serializers.CharField()
    line_name = serializers.CharField()
    
    avg_oee_24h = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    min_oee_24h = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    max_oee_24h = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    oee_std_dev_24h = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    
    avg_availability_24h = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    low_availability_hours = serializers.IntegerField()
    downtime_events_24h = serializers.IntegerField()
    total_downtime_24h = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    
    quality_events_24h = serializers.IntegerField()
    failed_parts_24h = serializers.IntegerField(allow_null=True)
    
    last_data_received = serializers.DateTimeField(allow_null=True)
    data_coverage_hours = serializers.IntegerField()
    
    health_score = serializers.IntegerField()
    health_status = serializers.CharField()
    data_status = serializers.CharField()
    
    report_timestamp = serializers.DateTimeField()


# =============================================
# 5. SCHEDULE AND OPERATIONS SERIALIZERS
# =============================================

class ProductionScheduleSerializer(serializers.ModelSerializer):
    """Production schedule and work order serializer"""
    line_name = serializers.CharField(source='line.line_name', read_only=True)
    recipe_name = serializers.CharField(source='recipe.recipe_name', read_only=True)
    product_name = serializers.CharField(source='recipe.product.product_name', read_only=True)
    
    # Progress calculations
    schedule_progress_percent = serializers.SerializerMethodField()
    production_progress_percent = serializers.SerializerMethodField()
    start_variance_minutes = serializers.SerializerMethodField()
    end_variance_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductionSchedule
        fields = '__all__'
        read_only_fields = ('schedule_id', 'created_at')
    
    def get_schedule_progress_percent(self, obj):
        """Calculate schedule time progress"""
        from django.utils import timezone
        now = timezone.now()
        
        if obj.schedule_status == 'COMPLETED':
            return 100.0
        elif obj.schedule_status == 'ACTIVE' and obj.actual_start_utc:
            if obj.planned_end_utc <= now:
                return 100.0
            else:
                elapsed = (now - obj.actual_start_utc).total_seconds()
                total = (obj.planned_end_utc - obj.actual_start_utc).total_seconds()
                return min(100.0, (elapsed / total) * 100 if total > 0 else 0)
        return 0.0
    
    def get_production_progress_percent(self, obj):
        """Calculate production quantity progress"""
        if obj.planned_quantity > 0 and obj.actual_quantity:
            return min(100.0, (obj.actual_quantity / obj.planned_quantity) * 100)
        return 0.0
    
    def get_start_variance_minutes(self, obj):
        """Calculate start time variance"""
        if obj.actual_start_utc:
            delta = obj.actual_start_utc - obj.planned_start_utc
            return int(delta.total_seconds() / 60)
        return None
    
    def get_end_variance_minutes(self, obj):
        """Calculate end time variance"""
        if obj.actual_end_utc:
            delta = obj.actual_end_utc - obj.planned_end_utc
            return int(delta.total_seconds() / 60)
        return None


# =============================================
# 6. AGGREGATION AND ANALYTICS SERIALIZERS
# =============================================

class OEETrendDataSerializer(serializers.Serializer):
    """OEE trend data for charts and analysis"""
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField(required=False)
    machine_id = serializers.CharField()
    machine_name = serializers.CharField()
    line_name = serializers.CharField()
    
    availability_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    performance_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    quality_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    oee_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    throughput_units_per_hour = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cycles = serializers.IntegerField()
    good_cycles = serializers.IntegerField()
    downtime_minutes = serializers.DecimalField(max_digits=8, decimal_places=2)
    
    # Trend analysis fields
    availability_3hr_avg = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    availability_8hr_avg = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    availability_trend = serializers.CharField(required=False)
    shift_number = serializers.IntegerField(required=False)


class ParetoAnalysisSerializer(serializers.Serializer):
    """Pareto analysis data for various metrics"""
    category = serializers.CharField()
    description = serializers.CharField()
    value = serializers.DecimalField(max_digits=15, decimal_places=2)
    count = serializers.IntegerField()
    percent_of_total = serializers.DecimalField(max_digits=5, decimal_places=2)
    cumulative_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    rank = serializers.IntegerField()
    
    # Additional context
    affected_items = serializers.IntegerField(required=False)
    avg_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    category_type = serializers.CharField(required=False)  # DOWNTIME, QUALITY, etc.


class KPITileSerializer(serializers.Serializer):
    """KPI tile data for dashboard cards"""
    kpi_name = serializers.CharField()
    current_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    target_value = serializers.DecimalField(max_digits=15, decimal_places=2, allow_null=True)
    unit = serializers.CharField()
    format_type = serializers.CharField()  # PERCENTAGE, DECIMAL, INTEGER, CURRENCY
    
    # Trend and status
    trend_direction = serializers.CharField()  # UP, DOWN, FLAT
    percent_change = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    status = serializers.CharField()  # GOOD, WARNING, CRITICAL
    
    # Time context
    period_description = serializers.CharField()
    last_updated = serializers.DateTimeField()
    data_freshness = serializers.CharField()  # LIVE, RECENT, STALE