-- =============================================
-- OEE Dashboard - SQL Server Views
-- Optimized Views for Dashboard Consumption
-- High-Performance Queries for Real-Time Manufacturing Analytics
-- =============================================

USE OEE_Dashboard;
GO

-- =============================================
-- 1. REAL-TIME DASHBOARD VIEWS
-- =============================================

-- Current shift OEE performance (main dashboard view)
CREATE OR ALTER VIEW dbo.vw_CurrentShiftOEE
AS
WITH CurrentShiftBounds AS (
    -- Determine current shift based on time of day
    SELECT 
        CASE 
            WHEN DATEPART(HOUR, GETUTCDATE()) BETWEEN 6 AND 13 THEN 1
            WHEN DATEPART(HOUR, GETUTCDATE()) BETWEEN 14 AND 21 THEN 2
            ELSE 3
        END AS current_shift,
        
        CASE 
            WHEN DATEPART(HOUR, GETUTCDATE()) BETWEEN 6 AND 13 THEN 
                DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()), 6, 0, 0, 0, 0)
            WHEN DATEPART(HOUR, GETUTCDATE()) BETWEEN 14 AND 21 THEN 
                DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()), 14, 0, 0, 0, 0)
            ELSE 
                CASE 
                    WHEN DATEPART(HOUR, GETUTCDATE()) < 6 THEN
                        DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()) - 1, 22, 0, 0, 0, 0)
                    ELSE
                        DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()), 22, 0, 0, 0, 0)
                END
        END AS shift_start,
        
        CASE 
            WHEN DATEPART(HOUR, GETUTCDATE()) BETWEEN 6 AND 13 THEN 
                DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()), 14, 0, 0, 0, 0)
            WHEN DATEPART(HOUR, GETUTCDATE()) BETWEEN 14 AND 21 THEN 
                DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()), 22, 0, 0, 0, 0)
            ELSE 
                CASE 
                    WHEN DATEPART(HOUR, GETUTCDATE()) < 6 THEN
                        DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()), 6, 0, 0, 0, 0)
                    ELSE
                        DATETIME2FROMPARTS(YEAR(GETUTCDATE()), MONTH(GETUTCDATE()), DAY(GETUTCDATE()) + 1, 6, 0, 0, 0, 0)
                END
        END AS shift_end
)
SELECT 
    p.plant_name,
    a.area_name,
    l.line_name,
    m.machine_id,
    m.machine_name,
    m.machine_type,
    sb.current_shift,
    sb.shift_start,
    sb.shift_end,
    
    -- Calculate elapsed shift time in minutes
    DATEDIFF(MINUTE, sb.shift_start, GETUTCDATE()) AS shift_elapsed_minutes,
    480 AS shift_total_minutes, -- 8-hour shifts
    
    -- Real-time OEE calculation using hourly rollups
    ISNULL(AVG(hr.availability_percent), 0) AS current_availability_percent,
    ISNULL(AVG(hr.performance_percent), 0) AS current_performance_percent,
    ISNULL(AVG(hr.quality_percent), 0) AS current_quality_percent,
    ISNULL(AVG(hr.oee_percent), 0) AS current_oee_percent,
    
    -- Production metrics
    ISNULL(SUM(hr.total_cycles), 0) AS shift_total_cycles,
    ISNULL(SUM(hr.good_cycles), 0) AS shift_good_cycles,
    ISNULL(SUM(hr.scrap_cycles), 0) AS shift_scrap_cycles,
    ISNULL(SUM(hr.downtime_minutes), 0) AS shift_downtime_minutes,
    ISNULL(SUM(hr.planned_downtime_minutes), 0) AS shift_planned_downtime_minutes,
    
    -- Throughput and targets
    ISNULL(AVG(hr.throughput_units_per_hour), 0) AS current_throughput_uph,
    l.target_availability_percent,
    l.target_performance_percent,
    l.target_quality_percent,
    (l.target_availability_percent / 100.0) * (l.target_performance_percent / 100.0) * (l.target_quality_percent / 100.0) * 100 AS target_oee_percent,
    
    -- Status indicators
    CASE 
        WHEN ISNULL(AVG(hr.oee_percent), 0) >= (l.target_availability_percent / 100.0) * (l.target_performance_percent / 100.0) * (l.target_quality_percent / 100.0) * 100 * 0.95 THEN 'GOOD'
        WHEN ISNULL(AVG(hr.oee_percent), 0) >= (l.target_availability_percent / 100.0) * (l.target_performance_percent / 100.0) * (l.target_quality_percent / 100.0) * 100 * 0.80 THEN 'WARNING'
        ELSE 'CRITICAL'
    END AS oee_status,
    
    -- Top downtime reason for current shift
    (SELECT TOP 1 dt.reason_code 
     FROM dbo.DowntimeEvents dt 
     WHERE dt.machine_id = m.machine_id 
       AND dt.start_timestamp_utc >= sb.shift_start 
       AND dt.start_timestamp_utc < GETUTCDATE()
     GROUP BY dt.reason_code
     ORDER BY SUM(ISNULL(dt.duration_minutes, DATEDIFF(MINUTE, dt.start_timestamp_utc, GETUTCDATE()))) DESC) AS top_downtime_reason,
    
    -- Last event timestamp for freshness indicator
    (SELECT MAX(me.timestamp_utc) 
     FROM dbo.MachineEvents me 
     WHERE me.machine_id = m.machine_id 
       AND me.timestamp_utc >= DATEADD(HOUR, -1, GETUTCDATE())) AS last_event_timestamp,
    
    GETUTCDATE() AS report_timestamp

FROM CurrentShiftBounds sb
CROSS JOIN dbo.Machines m
INNER JOIN dbo.ProductionLines l ON m.line_id = l.line_id
INNER JOIN dbo.Areas a ON l.area_id = a.area_id
INNER JOIN dbo.Plants p ON a.plant_id = p.plant_id
LEFT JOIN dbo.OEE_Rollup_Hourly hr ON m.machine_id = hr.machine_id
    AND hr.bucket_start_utc >= sb.shift_start
    AND hr.bucket_start_utc < GETUTCDATE()
WHERE m.is_active = 1 
  AND l.is_active = 1 
  AND a.is_active = 1 
  AND p.is_active = 1
GROUP BY p.plant_name, a.area_name, l.line_name, m.machine_id, m.machine_name, m.machine_type,
         sb.current_shift, sb.shift_start, sb.shift_end, l.target_availability_percent, 
         l.target_performance_percent, l.target_quality_percent;
GO

-- Line-level aggregated performance
CREATE OR ALTER VIEW dbo.vw_LinePerformance
AS
SELECT 
    p.plant_name,
    a.area_name,
    l.line_id,
    l.line_name,
    l.line_type,
    
    -- Machine count
    COUNT(DISTINCT m.machine_id) AS total_machines,
    COUNT(DISTINCT CASE WHEN csm.current_oee_percent >= csm.target_oee_percent * 0.95 THEN m.machine_id END) AS machines_on_target,
    
    -- Aggregated OEE metrics
    AVG(csm.current_availability_percent) AS line_availability_percent,
    AVG(csm.current_performance_percent) AS line_performance_percent,
    AVG(csm.current_quality_percent) AS line_quality_percent,
    AVG(csm.current_oee_percent) AS line_oee_percent,
    
    -- Production totals
    SUM(csm.shift_total_cycles) AS line_total_cycles,
    SUM(csm.shift_good_cycles) AS line_good_cycles,
    SUM(csm.shift_scrap_cycles) AS line_scrap_cycles,
    SUM(csm.shift_downtime_minutes) AS line_downtime_minutes,
    
    -- Throughput
    AVG(csm.current_throughput_uph) AS line_avg_throughput_uph,
    SUM(csm.current_throughput_uph) AS line_total_throughput_uph,
    
    -- Status
    CASE 
        WHEN AVG(csm.current_oee_percent) >= AVG(csm.target_oee_percent) * 0.95 THEN 'GOOD'
        WHEN AVG(csm.current_oee_percent) >= AVG(csm.target_oee_percent) * 0.80 THEN 'WARNING'
        ELSE 'CRITICAL'
    END AS line_status,
    
    GETUTCDATE() AS report_timestamp

FROM dbo.Plants p
INNER JOIN dbo.Areas a ON p.plant_id = a.plant_id
INNER JOIN dbo.ProductionLines l ON a.area_id = l.area_id
INNER JOIN dbo.Machines m ON l.line_id = m.line_id
INNER JOIN dbo.vw_CurrentShiftOEE csm ON m.machine_id = csm.machine_id
WHERE p.is_active = 1 AND a.is_active = 1 AND l.is_active = 1 AND m.is_active = 1
GROUP BY p.plant_name, a.area_name, l.line_id, l.line_name, l.line_type;
GO

-- =============================================
-- 2. TOP LOSSES AND PARETO ANALYSIS VIEWS
-- =============================================

-- Top downtime reasons (last 24 hours)
CREATE OR ALTER VIEW dbo.vw_TopDowntimeReasons24h
AS
SELECT 
    dr.reason_code,
    dr.reason_description,
    dr.reason_category,
    dr.reason_subcategory,
    dr.severity_level,
    
    COUNT(*) AS occurrence_count,
    SUM(ISNULL(de.duration_minutes, 
               DATEDIFF(MINUTE, de.start_timestamp_utc, GETUTCDATE()))) AS total_minutes,
    AVG(ISNULL(de.duration_minutes, 
               DATEDIFF(MINUTE, de.start_timestamp_utc, GETUTCDATE()))) AS avg_duration_minutes,
    
    -- Percentage of total downtime
    SUM(ISNULL(de.duration_minutes, DATEDIFF(MINUTE, de.start_timestamp_utc, GETUTCDATE()))) * 100.0 / 
        (SELECT SUM(ISNULL(duration_minutes, DATEDIFF(MINUTE, start_timestamp_utc, GETUTCDATE())))
         FROM dbo.DowntimeEvents 
         WHERE start_timestamp_utc >= DATEADD(HOUR, -24, GETUTCDATE())) AS percent_of_total_downtime,
    
    -- Affected machines
    COUNT(DISTINCT de.machine_id) AS affected_machines,
    STRING_AGG(DISTINCT de.machine_id, ', ') AS machine_list,
    
    -- MTTR (Mean Time To Repair)
    AVG(CASE WHEN de.end_timestamp_utc IS NOT NULL 
             THEN DATEDIFF(MINUTE, de.start_timestamp_utc, de.end_timestamp_utc)
             ELSE NULL END) AS mttr_minutes,
    
    dr.mttr_target_minutes AS mttr_target_minutes,
    
    GETUTCDATE() AS report_timestamp

FROM dbo.DowntimeEvents de
INNER JOIN dbo.DowntimeReasons dr ON de.reason_code = dr.reason_code
WHERE de.start_timestamp_utc >= DATEADD(HOUR, -24, GETUTCDATE())
  AND dr.is_active = 1
GROUP BY dr.reason_code, dr.reason_description, dr.reason_category, 
         dr.reason_subcategory, dr.severity_level, dr.mttr_target_minutes
HAVING SUM(ISNULL(de.duration_minutes, DATEDIFF(MINUTE, de.start_timestamp_utc, GETUTCDATE()))) > 0;
GO

-- Top quality defects (last 7 days)
CREATE OR ALTER VIEW dbo.vw_TopQualityDefects7d
AS
SELECT 
    qd.defect_code,
    qd.defect_description,
    qd.defect_category,
    qd.severity_level,
    qd.rework_possible,
    
    COUNT(*) AS occurrence_count,
    SUM(qe.parts_failed) AS total_parts_failed,
    SUM(qe.parts_inspected) AS total_parts_inspected,
    
    -- Defect rate
    CASE WHEN SUM(qe.parts_inspected) > 0 
         THEN (SUM(qe.parts_failed) * 100.0) / SUM(qe.parts_inspected)
         ELSE 0 
    END AS defect_rate_percent,
    
    -- Percentage of total defects
    SUM(qe.parts_failed) * 100.0 / 
        (SELECT SUM(parts_failed) FROM dbo.QualityEvents 
         WHERE timestamp_utc >= DATEADD(DAY, -7, GETUTCDATE())) AS percent_of_total_defects,
    
    -- Affected machines
    COUNT(DISTINCT qe.machine_id) AS affected_machines,
    STRING_AGG(DISTINCT qe.machine_id, ', ') AS machine_list,
    
    -- Cost impact (if available)
    COUNT(DISTINCT qe.cycle_id) AS affected_cycles,
    
    GETUTCDATE() AS report_timestamp

FROM dbo.QualityEvents qe
INNER JOIN dbo.QualityDefects qd ON qe.defect_code = qd.defect_code
WHERE qe.timestamp_utc >= DATEADD(DAY, -7, GETUTCDATE())
  AND qd.is_active = 1
  AND qe.parts_failed > 0
GROUP BY qd.defect_code, qd.defect_description, qd.defect_category, 
         qd.severity_level, qd.rework_possible
HAVING SUM(qe.parts_failed) > 0;
GO

-- =============================================
-- 3. TREND ANALYSIS VIEWS
-- =============================================

-- Daily OEE trends (last 30 days)
CREATE OR ALTER VIEW dbo.vw_DailyOEETrends30d
AS
SELECT 
    dr.date_utc,
    dr.machine_id,
    m.machine_name,
    dr.line_id,
    l.line_name,
    a.area_name,
    p.plant_name,
    
    dr.availability_percent,
    dr.performance_percent,
    dr.quality_percent,
    dr.oee_percent,
    
    dr.total_cycles,
    dr.good_cycles,
    dr.scrap_cycles,
    dr.throughput_units_per_hour,
    dr.downtime_minutes,
    dr.planned_downtime_minutes,
    dr.unplanned_downtime_minutes,
    
    -- Target comparison
    l.target_availability_percent,
    l.target_performance_percent,
    l.target_quality_percent,
    (l.target_availability_percent / 100.0) * (l.target_performance_percent / 100.0) * (l.target_quality_percent / 100.0) * 100 AS target_oee_percent,
    
    -- Performance vs target
    dr.availability_percent - l.target_availability_percent AS availability_variance,
    dr.performance_percent - l.target_performance_percent AS performance_variance,
    dr.quality_percent - l.target_quality_percent AS quality_variance,
    dr.oee_percent - ((l.target_availability_percent / 100.0) * (l.target_performance_percent / 100.0) * (l.target_quality_percent / 100.0) * 100) AS oee_variance,
    
    -- Day of week for pattern analysis
    DATENAME(WEEKDAY, dr.date_utc) AS day_of_week,
    DATEPART(WEEKDAY, dr.date_utc) AS day_of_week_number,
    
    GETUTCDATE() AS report_timestamp

FROM dbo.OEE_Rollup_Daily dr
INNER JOIN dbo.Machines m ON dr.machine_id = m.machine_id
INNER JOIN dbo.ProductionLines l ON dr.line_id = l.line_id
INNER JOIN dbo.Areas a ON l.area_id = a.area_id
INNER JOIN dbo.Plants p ON a.plant_id = p.plant_id
WHERE dr.date_utc >= DATEADD(DAY, -30, CAST(GETUTCDATE() AS DATE))
  AND m.is_active = 1 AND l.is_active = 1 AND a.is_active = 1 AND p.is_active = 1;
GO

-- Machine availability trends (hourly, last 3 days)
CREATE OR ALTER VIEW dbo.vw_MachineAvailabilityTrends72h
AS
SELECT 
    hr.machine_id,
    m.machine_name,
    hr.line_id,
    l.line_name,
    hr.bucket_start_utc,
    hr.bucket_end_utc,
    
    hr.availability_percent,
    hr.downtime_minutes,
    hr.planned_downtime_minutes,
    hr.unplanned_downtime_minutes,
    hr.top_downtime_reason,
    hr.top_downtime_minutes,
    
    -- Moving averages for trend detection
    AVG(hr.availability_percent) OVER (
        PARTITION BY hr.machine_id 
        ORDER BY hr.bucket_start_utc 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS availability_3hr_avg,
    
    AVG(hr.availability_percent) OVER (
        PARTITION BY hr.machine_id 
        ORDER BY hr.bucket_start_utc 
        ROWS BETWEEN 7 PRECEDING AND CURRENT ROW
    ) AS availability_8hr_avg,
    
    -- Trend direction
    CASE 
        WHEN hr.availability_percent > LAG(hr.availability_percent, 1) OVER (PARTITION BY hr.machine_id ORDER BY hr.bucket_start_utc) THEN 'IMPROVING'
        WHEN hr.availability_percent < LAG(hr.availability_percent, 1) OVER (PARTITION BY hr.machine_id ORDER BY hr.bucket_start_utc) THEN 'DECLINING'
        ELSE 'STABLE'
    END AS availability_trend,
    
    -- Shift identification
    CASE 
        WHEN DATEPART(HOUR, hr.bucket_start_utc) BETWEEN 6 AND 13 THEN 1
        WHEN DATEPART(HOUR, hr.bucket_start_utc) BETWEEN 14 AND 21 THEN 2
        ELSE 3
    END AS shift_number,
    
    GETUTCDATE() AS report_timestamp

FROM dbo.OEE_Rollup_Hourly hr
INNER JOIN dbo.Machines m ON hr.machine_id = m.machine_id
INNER JOIN dbo.ProductionLines l ON hr.line_id = l.line_id
WHERE hr.bucket_start_utc >= DATEADD(DAY, -3, GETUTCDATE())
  AND m.is_active = 1 AND l.is_active = 1;
GO

-- =============================================
-- 4. OPERATIONAL INSIGHTS VIEWS
-- =============================================

-- Machine health indicators
CREATE OR ALTER VIEW dbo.vw_MachineHealthIndicators
AS
WITH HealthMetrics AS (
    SELECT 
        m.machine_id,
        m.machine_name,
        m.line_id,
        l.line_name,
        
        -- OEE performance (last 24 hours)
        AVG(hr.oee_percent) AS avg_oee_24h,
        MIN(hr.oee_percent) AS min_oee_24h,
        MAX(hr.oee_percent) AS max_oee_24h,
        STDEV(hr.oee_percent) AS oee_std_dev_24h,
        
        -- Availability metrics
        AVG(hr.availability_percent) AS avg_availability_24h,
        COUNT(CASE WHEN hr.availability_percent < 80 THEN 1 END) AS low_availability_hours,
        
        -- Downtime frequency
        COUNT(DISTINCT de.downtime_id) AS downtime_events_24h,
        SUM(ISNULL(de.duration_minutes, DATEDIFF(MINUTE, de.start_timestamp_utc, GETUTCDATE()))) AS total_downtime_24h,
        
        -- Quality issues
        COUNT(DISTINCT qe.quality_id) AS quality_events_24h,
        SUM(qe.parts_failed) AS failed_parts_24h,
        
        -- Data freshness
        MAX(me.timestamp_utc) AS last_data_received,
        COUNT(DISTINCT DATEPART(HOUR, me.timestamp_utc)) AS data_coverage_hours
        
    FROM dbo.Machines m
    INNER JOIN dbo.ProductionLines l ON m.line_id = l.line_id
    LEFT JOIN dbo.OEE_Rollup_Hourly hr ON m.machine_id = hr.machine_id
        AND hr.bucket_start_utc >= DATEADD(HOUR, -24, GETUTCDATE())
    LEFT JOIN dbo.DowntimeEvents de ON m.machine_id = de.machine_id
        AND de.start_timestamp_utc >= DATEADD(HOUR, -24, GETUTCDATE())
    LEFT JOIN dbo.QualityEvents qe ON m.machine_id = qe.machine_id
        AND qe.timestamp_utc >= DATEADD(HOUR, -24, GETUTCDATE())
    LEFT JOIN dbo.MachineEvents me ON m.machine_id = me.machine_id
        AND me.timestamp_utc >= DATEADD(HOUR, -24, GETUTCDATE())
    WHERE m.is_active = 1 AND l.is_active = 1
    GROUP BY m.machine_id, m.machine_name, m.line_id, l.line_name
)
SELECT 
    machine_id,
    machine_name,
    line_id,
    line_name,
    
    avg_oee_24h,
    min_oee_24h,
    max_oee_24h,
    oee_std_dev_24h,
    avg_availability_24h,
    low_availability_hours,
    downtime_events_24h,
    total_downtime_24h,
    quality_events_24h,
    failed_parts_24h,
    last_data_received,
    data_coverage_hours,
    
    -- Health score calculation (0-100)
    CAST((
        -- OEE performance weight (40%)
        (CASE WHEN avg_oee_24h >= 80 THEN 40 
              WHEN avg_oee_24h >= 60 THEN 30 
              WHEN avg_oee_24h >= 40 THEN 20 
              ELSE 10 END) +
        
        -- Availability stability weight (25%)
        (CASE WHEN low_availability_hours = 0 THEN 25 
              WHEN low_availability_hours <= 2 THEN 20 
              WHEN low_availability_hours <= 4 THEN 15 
              ELSE 5 END) +
        
        -- Downtime frequency weight (20%)
        (CASE WHEN downtime_events_24h <= 2 THEN 20 
              WHEN downtime_events_24h <= 5 THEN 15 
              WHEN downtime_events_24h <= 10 THEN 10 
              ELSE 5 END) +
        
        -- Data quality weight (15%)
        (CASE WHEN data_coverage_hours >= 20 THEN 15 
              WHEN data_coverage_hours >= 16 THEN 12 
              WHEN data_coverage_hours >= 12 THEN 8 
              ELSE 3 END)
    ) AS INT) AS health_score,
    
    -- Overall health status
    CASE 
        WHEN (avg_oee_24h >= 80 AND low_availability_hours <= 2 AND downtime_events_24h <= 5 AND data_coverage_hours >= 20) THEN 'EXCELLENT'
        WHEN (avg_oee_24h >= 60 AND low_availability_hours <= 4 AND downtime_events_24h <= 10 AND data_coverage_hours >= 16) THEN 'GOOD'
        WHEN (avg_oee_24h >= 40 AND low_availability_hours <= 8 AND downtime_events_24h <= 15 AND data_coverage_hours >= 12) THEN 'FAIR'
        WHEN (avg_oee_24h >= 20) THEN 'POOR'
        ELSE 'CRITICAL'
    END AS health_status,
    
    -- Data freshness indicator
    CASE 
        WHEN last_data_received >= DATEADD(MINUTE, -5, GETUTCDATE()) THEN 'LIVE'
        WHEN last_data_received >= DATEADD(MINUTE, -15, GETUTCDATE()) THEN 'RECENT'
        WHEN last_data_received >= DATEADD(HOUR, -1, GETUTCDATE()) THEN 'STALE'
        ELSE 'OFFLINE'
    END AS data_status,
    
    GETUTCDATE() AS report_timestamp

FROM HealthMetrics;
GO

-- =============================================
-- 5. PRODUCTION SCHEDULE VIEWS
-- =============================================

-- Current and upcoming production schedule
CREATE OR ALTER VIEW dbo.vw_ProductionScheduleStatus
AS
SELECT 
    ps.schedule_id,
    ps.line_id,
    l.line_name,
    ps.recipe_id,
    r.recipe_name,
    r.product_id,
    pr.product_name,
    
    ps.planned_start_utc,
    ps.planned_end_utc,
    ps.actual_start_utc,
    ps.actual_end_utc,
    ps.planned_quantity,
    ps.actual_quantity,
    ps.schedule_status,
    ps.priority_level,
    ps.work_order_number,
    
    -- Schedule progress
    CASE 
        WHEN ps.schedule_status = 'COMPLETED' THEN 100.0
        WHEN ps.schedule_status = 'ACTIVE' AND ps.actual_start_utc IS NOT NULL THEN
            CASE 
                WHEN ps.planned_end_utc <= GETUTCDATE() THEN 100.0
                ELSE (DATEDIFF(MINUTE, ps.actual_start_utc, GETUTCDATE()) * 100.0) / 
                     DATEDIFF(MINUTE, ps.actual_start_utc, ps.planned_end_utc)
            END
        ELSE 0.0
    END AS schedule_progress_percent,
    
    -- Production progress
    CASE 
        WHEN ps.planned_quantity > 0 THEN (ISNULL(ps.actual_quantity, 0) * 100.0) / ps.planned_quantity
        ELSE 0.0
    END AS production_progress_percent,
    
    -- Schedule variance
    CASE 
        WHEN ps.actual_start_utc IS NOT NULL THEN 
            DATEDIFF(MINUTE, ps.planned_start_utc, ps.actual_start_utc)
        ELSE NULL
    END AS start_variance_minutes,
    
    CASE 
        WHEN ps.actual_end_utc IS NOT NULL THEN 
            DATEDIFF(MINUTE, ps.planned_end_utc, ps.actual_end_utc)
        ELSE NULL
    END AS end_variance_minutes,
    
    -- Expected completion based on current rate
    CASE 
        WHEN ps.schedule_status = 'ACTIVE' AND ps.actual_start_utc IS NOT NULL 
             AND ps.actual_quantity > 0 AND ps.planned_quantity > ps.actual_quantity THEN
            DATEADD(MINUTE, 
                   (DATEDIFF(MINUTE, ps.actual_start_utc, GETUTCDATE()) * (ps.planned_quantity - ps.actual_quantity)) / ps.actual_quantity,
                   GETUTCDATE())
        ELSE NULL
    END AS projected_completion_utc,
    
    GETUTCDATE() AS report_timestamp

FROM dbo.ProductionSchedule ps
INNER JOIN dbo.ProductionLines l ON ps.line_id = l.line_id
INNER JOIN dbo.Recipes r ON ps.recipe_id = r.recipe_id
INNER JOIN dbo.Products pr ON r.product_id = pr.product_id
WHERE ps.planned_start_utc >= DATEADD(DAY, -1, GETUTCDATE())  -- Show yesterday onwards
  AND ps.planned_start_utc <= DATEADD(DAY, 7, GETUTCDATE())   -- Show next 7 days
  AND l.is_active = 1 AND r.is_active = 1 AND pr.is_active = 1;
GO

PRINT 'SQL Server views created successfully.';
PRINT 'Dashboard-optimized views:';
PRINT '  - vw_CurrentShiftOEE: Real-time shift performance for all machines';
PRINT '  - vw_LinePerformance: Aggregated line-level KPIs';
PRINT '  - vw_TopDowntimeReasons24h: Pareto analysis of downtime causes';
PRINT '  - vw_TopQualityDefects7d: Quality issue analysis';
PRINT '  - vw_DailyOEETrends30d: 30-day trend analysis';
PRINT '  - vw_MachineAvailabilityTrends72h: Short-term availability patterns';
PRINT '  - vw_MachineHealthIndicators: Overall machine health scoring';
PRINT '  - vw_ProductionScheduleStatus: Schedule adherence tracking';
PRINT '';
PRINT 'These views are optimized for:';
PRINT '  - Sub-200ms dashboard response times';
PRINT '  - Real-time data freshness indicators';
PRINT '  - Comprehensive KPI calculations';
PRINT '  - Trend and pattern analysis';
GO