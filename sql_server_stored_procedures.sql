-- =============================================
-- OEE Dashboard - SQL Server Stored Procedures
-- Production-Ready OEE Calculations and Data Processing
-- =============================================

USE OEE_Dashboard;
GO

-- =============================================
-- 1. REAL-TIME OEE CALCULATION PROCEDURES
-- =============================================

-- Calculate real-time OEE for a specific machine
CREATE OR ALTER PROCEDURE dbo.sp_CalculateRealTimeOEE
    @MachineId NVARCHAR(50),
    @StartTime DATETIME2 = NULL,
    @EndTime DATETIME2 = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Default to current shift if no time range specified
    IF @StartTime IS NULL
        SET @StartTime = DATEADD(HOUR, -8, GETUTCDATE()); -- Last 8 hours
    
    IF @EndTime IS NULL
        SET @EndTime = GETUTCDATE();
    
    DECLARE @PlannedProductionTime DECIMAL(10,2);
    DECLARE @DowntimeMinutes DECIMAL(10,2);
    DECLARE @PlannedDowntimeMinutes DECIMAL(10,2);
    DECLARE @TotalCycles INT;
    DECLARE @GoodCycles INT;
    DECLARE @AverageCycleTime DECIMAL(10,3);
    DECLARE @TargetCycleTime DECIMAL(10,3);
    
    -- Calculate planned production time (in minutes)
    SET @PlannedProductionTime = DATEDIFF(MINUTE, @StartTime, @EndTime);
    
    -- Get total downtime (planned and unplanned)
    SELECT 
        @DowntimeMinutes = ISNULL(SUM(DATEDIFF(MINUTE, start_timestamp_utc, ISNULL(end_timestamp_utc, @EndTime))), 0),
        @PlannedDowntimeMinutes = ISNULL(SUM(
            CASE WHEN is_planned = 1 
                 THEN DATEDIFF(MINUTE, start_timestamp_utc, ISNULL(end_timestamp_utc, @EndTime))
                 ELSE 0 
            END), 0)
    FROM dbo.DowntimeEvents
    WHERE machine_id = @MachineId
      AND start_timestamp_utc >= @StartTime
      AND start_timestamp_utc < @EndTime;
    
    -- Get production cycle data
    SELECT 
        @TotalCycles = COUNT(*),
        @GoodCycles = SUM(CASE WHEN scrap_parts_count = 0 THEN 1 ELSE 0 END),
        @AverageCycleTime = AVG(cycle_time_seconds),
        @TargetCycleTime = AVG(target_cycle_time_seconds)
    FROM dbo.ProductionCycles
    WHERE machine_id = @MachineId
      AND start_timestamp_utc >= @StartTime
      AND start_timestamp_utc < @EndTime
      AND cycle_status = 'COMPLETED';
    
    -- Calculate OEE components
    DECLARE @Availability DECIMAL(5,2) = 0;
    DECLARE @Performance DECIMAL(5,2) = 0;
    DECLARE @Quality DECIMAL(5,2) = 0;
    DECLARE @OEE DECIMAL(5,2) = 0;
    
    -- Availability = (Planned Production Time - Unplanned Downtime) / Planned Production Time
    IF @PlannedProductionTime > 0
        SET @Availability = ((@PlannedProductionTime - (@DowntimeMinutes - @PlannedDowntimeMinutes)) / @PlannedProductionTime) * 100;
    
    -- Performance = (Total Cycle Time / (Target Cycle Time * Total Cycles))
    IF @TotalCycles > 0 AND @TargetCycleTime > 0
        SET @Performance = ((@TotalCycles * @TargetCycleTime) / (@TotalCycles * @AverageCycleTime)) * 100;
    
    -- Quality = Good Cycles / Total Cycles
    IF @TotalCycles > 0
        SET @Quality = (@GoodCycles * 100.0) / @TotalCycles;
    
    -- OEE = Availability × Performance × Quality
    SET @OEE = (@Availability / 100) * (@Performance / 100) * (@Quality / 100) * 100;
    
    -- Return results
    SELECT 
        @MachineId AS machine_id,
        @StartTime AS start_time,
        @EndTime AS end_time,
        @PlannedProductionTime AS planned_production_time_minutes,
        @DowntimeMinutes AS total_downtime_minutes,
        @PlannedDowntimeMinutes AS planned_downtime_minutes,
        @TotalCycles AS total_cycles,
        @GoodCycles AS good_cycles,
        @AverageCycleTime AS average_cycle_time_seconds,
        @TargetCycleTime AS target_cycle_time_seconds,
        @Availability AS availability_percent,
        @Performance AS performance_percent,
        @Quality AS quality_percent,
        @OEE AS oee_percent;
END;
GO

-- =============================================
-- 2. HOURLY ROLLUP CALCULATION
-- =============================================

CREATE OR ALTER PROCEDURE dbo.sp_CalculateHourlyRollups
    @StartHour DATETIME2 = NULL,
    @EndHour DATETIME2 = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Default to last hour if not specified
    IF @StartHour IS NULL
        SET @StartHour = DATEADD(HOUR, DATEDIFF(HOUR, 0, GETUTCDATE()) - 1, 0);
    
    IF @EndHour IS NULL
        SET @EndHour = DATEADD(HOUR, 1, @StartHour);
    
    -- Calculate hourly rollups for each active machine
    WITH HourlyCalculations AS (
        SELECT 
            m.machine_id,
            m.line_id,
            @StartHour AS bucket_start_utc,
            @EndHour AS bucket_end_utc,
            
            -- Production time calculation
            60.0 AS planned_production_time_minutes, -- 1 hour = 60 minutes
            
            -- Downtime calculations
            ISNULL(SUM(
                CASE WHEN dt.start_timestamp_utc < @EndHour AND ISNULL(dt.end_timestamp_utc, @EndHour) > @StartHour
                     THEN DATEDIFF(MINUTE, 
                                   CASE WHEN dt.start_timestamp_utc > @StartHour THEN dt.start_timestamp_utc ELSE @StartHour END,
                                   CASE WHEN ISNULL(dt.end_timestamp_utc, @EndHour) < @EndHour THEN ISNULL(dt.end_timestamp_utc, @EndHour) ELSE @EndHour END)
                     ELSE 0 
                END), 0) AS downtime_minutes,
                
            ISNULL(SUM(
                CASE WHEN dt.is_planned = 1 AND dt.start_timestamp_utc < @EndHour AND ISNULL(dt.end_timestamp_utc, @EndHour) > @StartHour
                     THEN DATEDIFF(MINUTE, 
                                   CASE WHEN dt.start_timestamp_utc > @StartHour THEN dt.start_timestamp_utc ELSE @StartHour END,
                                   CASE WHEN ISNULL(dt.end_timestamp_utc, @EndHour) < @EndHour THEN ISNULL(dt.end_timestamp_utc, @EndHour) ELSE @EndHour END)
                     ELSE 0 
                END), 0) AS planned_downtime_minutes,
            
            -- Cycle calculations
            ISNULL(COUNT(pc.cycle_id), 0) AS total_cycles,
            ISNULL(SUM(CASE WHEN pc.scrap_parts_count = 0 THEN 1 ELSE 0 END), 0) AS good_cycles,
            ISNULL(SUM(pc.scrap_parts_count), 0) AS scrap_cycles,
            ISNULL(SUM(pc.rework_parts_count), 0) AS rework_cycles,
            ISNULL(AVG(pc.cycle_time_seconds), 0) AS average_cycle_time_seconds,
            ISNULL(AVG(pc.target_cycle_time_seconds), 0) AS target_cycle_time_seconds,
            
            -- Top downtime reason
            (SELECT TOP 1 dt2.reason_code 
             FROM dbo.DowntimeEvents dt2 
             WHERE dt2.machine_id = m.machine_id 
               AND dt2.start_timestamp_utc >= @StartHour 
               AND dt2.start_timestamp_utc < @EndHour
             GROUP BY dt2.reason_code
             ORDER BY SUM(ISNULL(dt2.duration_minutes, DATEDIFF(MINUTE, dt2.start_timestamp_utc, @EndHour))) DESC) AS top_downtime_reason,
               
            (SELECT TOP 1 SUM(ISNULL(dt2.duration_minutes, DATEDIFF(MINUTE, dt2.start_timestamp_utc, @EndHour)))
             FROM dbo.DowntimeEvents dt2 
             WHERE dt2.machine_id = m.machine_id 
               AND dt2.start_timestamp_utc >= @StartHour 
               AND dt2.start_timestamp_utc < @EndHour
             GROUP BY dt2.reason_code
             ORDER BY SUM(ISNULL(dt2.duration_minutes, DATEDIFF(MINUTE, dt2.start_timestamp_utc, @EndHour))) DESC) AS top_downtime_minutes
            
        FROM dbo.Machines m
        LEFT JOIN dbo.DowntimeEvents dt ON m.machine_id = dt.machine_id 
            AND dt.start_timestamp_utc >= @StartHour 
            AND dt.start_timestamp_utc < @EndHour
        LEFT JOIN dbo.ProductionCycles pc ON m.machine_id = pc.machine_id 
            AND pc.start_timestamp_utc >= @StartHour 
            AND pc.start_timestamp_utc < @EndHour
            AND pc.cycle_status = 'COMPLETED'
        WHERE m.is_active = 1
        GROUP BY m.machine_id, m.line_id
    )
    
    -- Insert/Update hourly rollups
    MERGE dbo.OEE_Rollup_Hourly AS target
    USING (
        SELECT 
            machine_id,
            line_id,
            bucket_start_utc,
            bucket_end_utc,
            planned_production_time_minutes,
            
            -- Calculate actual production time
            planned_production_time_minutes - downtime_minutes AS actual_production_time_minutes,
            downtime_minutes,
            planned_downtime_minutes,
            downtime_minutes - planned_downtime_minutes AS unplanned_downtime_minutes,
            
            total_cycles,
            good_cycles,
            scrap_cycles,
            rework_cycles,
            average_cycle_time_seconds,
            target_cycle_time_seconds,
            
            -- Calculate OEE components
            CASE WHEN planned_production_time_minutes > 0 
                 THEN ((planned_production_time_minutes - (downtime_minutes - planned_downtime_minutes)) / planned_production_time_minutes) * 100
                 ELSE 0 
            END AS availability_percent,
            
            CASE WHEN total_cycles > 0 AND target_cycle_time_seconds > 0 AND average_cycle_time_seconds > 0
                 THEN (target_cycle_time_seconds / average_cycle_time_seconds) * 100
                 ELSE 0 
            END AS performance_percent,
            
            CASE WHEN total_cycles > 0 
                 THEN (good_cycles * 100.0) / total_cycles
                 ELSE 0 
            END AS quality_percent,
            
            -- Calculate throughput
            CASE WHEN planned_production_time_minutes > 0 
                 THEN (good_cycles * 60.0) / planned_production_time_minutes
                 ELSE 0 
            END AS throughput_units_per_hour,
            
            top_downtime_reason,
            top_downtime_minutes
            
        FROM HourlyCalculations
    ) AS source ON target.machine_id = source.machine_id AND target.bucket_start_utc = source.bucket_start_utc
    
    WHEN MATCHED THEN
        UPDATE SET
            actual_production_time_minutes = source.actual_production_time_minutes,
            downtime_minutes = source.downtime_minutes,
            planned_downtime_minutes = source.planned_downtime_minutes,
            unplanned_downtime_minutes = source.unplanned_downtime_minutes,
            total_cycles = source.total_cycles,
            good_cycles = source.good_cycles,
            scrap_cycles = source.scrap_cycles,
            rework_cycles = source.rework_cycles,
            average_cycle_time_seconds = source.average_cycle_time_seconds,
            target_cycle_time_seconds = source.target_cycle_time_seconds,
            availability_percent = source.availability_percent,
            performance_percent = source.performance_percent,
            quality_percent = source.quality_percent,
            oee_percent = (source.availability_percent / 100) * (source.performance_percent / 100) * (source.quality_percent / 100) * 100,
            throughput_units_per_hour = source.throughput_units_per_hour,
            top_downtime_reason = source.top_downtime_reason,
            top_downtime_minutes = source.top_downtime_minutes
    
    WHEN NOT MATCHED THEN
        INSERT (machine_id, line_id, bucket_start_utc, bucket_end_utc, planned_production_time_minutes,
                actual_production_time_minutes, downtime_minutes, planned_downtime_minutes, unplanned_downtime_minutes,
                total_cycles, good_cycles, scrap_cycles, rework_cycles, average_cycle_time_seconds, target_cycle_time_seconds,
                availability_percent, performance_percent, quality_percent, oee_percent, throughput_units_per_hour,
                top_downtime_reason, top_downtime_minutes)
        VALUES (source.machine_id, source.line_id, source.bucket_start_utc, source.bucket_end_utc, source.planned_production_time_minutes,
                source.actual_production_time_minutes, source.downtime_minutes, source.planned_downtime_minutes, source.unplanned_downtime_minutes,
                source.total_cycles, source.good_cycles, source.scrap_cycles, source.rework_cycles, source.average_cycle_time_seconds, source.target_cycle_time_seconds,
                source.availability_percent, source.performance_percent, source.quality_percent,
                (source.availability_percent / 100) * (source.performance_percent / 100) * (source.quality_percent / 100) * 100,
                source.throughput_units_per_hour, source.top_downtime_reason, source.top_downtime_minutes);
    
    SELECT @@ROWCOUNT AS rows_affected;
END;
GO

-- =============================================
-- 3. SHIFT ROLLUP CALCULATION
-- =============================================

CREATE OR ALTER PROCEDURE dbo.sp_CalculateShiftRollups
    @ShiftDate DATE = NULL,
    @LineId NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Default to yesterday if not specified
    IF @ShiftDate IS NULL
        SET @ShiftDate = CAST(DATEADD(DAY, -1, GETUTCDATE()) AS DATE);
    
    -- Calculate shift rollups by aggregating hourly data
    WITH ShiftTimes AS (
        SELECT 1 AS shift_number, 
               DATETIME2FROMPARTS(YEAR(@ShiftDate), MONTH(@ShiftDate), DAY(@ShiftDate), 6, 0, 0, 0, 0) AS shift_start,
               DATETIME2FROMPARTS(YEAR(@ShiftDate), MONTH(@ShiftDate), DAY(@ShiftDate), 14, 0, 0, 0, 0) AS shift_end
        UNION ALL
        SELECT 2 AS shift_number,
               DATETIME2FROMPARTS(YEAR(@ShiftDate), MONTH(@ShiftDate), DAY(@ShiftDate), 14, 0, 0, 0, 0) AS shift_start,
               DATETIME2FROMPARTS(YEAR(@ShiftDate), MONTH(@ShiftDate), DAY(@ShiftDate), 22, 0, 0, 0, 0) AS shift_end
        UNION ALL
        SELECT 3 AS shift_number,
               DATETIME2FROMPARTS(YEAR(@ShiftDate), MONTH(@ShiftDate), DAY(@ShiftDate), 22, 0, 0, 0, 0) AS shift_start,
               DATETIME2FROMPARTS(YEAR(@ShiftDate) + CASE WHEN MONTH(@ShiftDate) = 12 AND DAY(@ShiftDate) = 31 THEN 1 ELSE 0 END,
                                 CASE WHEN MONTH(@ShiftDate) = 12 AND DAY(@ShiftDate) = 31 THEN 1 
                                      WHEN DAY(@ShiftDate) = DAY(EOMONTH(@ShiftDate)) THEN 1 
                                      ELSE MONTH(@ShiftDate) END,
                                 CASE WHEN DAY(@ShiftDate) = DAY(EOMONTH(@ShiftDate)) THEN 1 ELSE DAY(@ShiftDate) + 1 END, 6, 0, 0, 0, 0) AS shift_end
    ),
    ShiftAggregates AS (
        SELECT 
            st.shift_number,
            st.shift_start AS shift_start_utc,
            st.shift_end AS shift_end_utc,
            hr.machine_id,
            hr.line_id,
            
            SUM(hr.planned_production_time_minutes) AS planned_production_time_minutes,
            SUM(hr.actual_production_time_minutes) AS actual_production_time_minutes,
            SUM(hr.downtime_minutes) AS downtime_minutes,
            SUM(hr.planned_downtime_minutes) AS planned_downtime_minutes,
            SUM(hr.unplanned_downtime_minutes) AS unplanned_downtime_minutes,
            
            SUM(hr.total_cycles) AS total_cycles,
            SUM(hr.good_cycles) AS good_cycles,
            SUM(hr.scrap_cycles) AS scrap_cycles,
            SUM(hr.rework_cycles) AS rework_cycles,
            
            CASE WHEN SUM(hr.total_cycles) > 0 
                 THEN SUM(hr.average_cycle_time_seconds * hr.total_cycles) / SUM(hr.total_cycles)
                 ELSE 0 
            END AS average_cycle_time_seconds,
            
            CASE WHEN SUM(hr.total_cycles) > 0 
                 THEN SUM(hr.target_cycle_time_seconds * hr.total_cycles) / SUM(hr.total_cycles)
                 ELSE 0 
            END AS target_cycle_time_seconds
            
        FROM ShiftTimes st
        CROSS JOIN dbo.Machines m
        LEFT JOIN dbo.OEE_Rollup_Hourly hr ON m.machine_id = hr.machine_id
            AND hr.bucket_start_utc >= st.shift_start
            AND hr.bucket_start_utc < st.shift_end
        WHERE m.is_active = 1
          AND (@LineId IS NULL OR m.line_id = @LineId)
        GROUP BY st.shift_number, st.shift_start, st.shift_end, hr.machine_id, hr.line_id
    )
    
    -- Insert/Update shift rollups
    MERGE dbo.OEE_Rollup_Shift AS target
    USING (
        SELECT 
            machine_id,
            line_id,
            @ShiftDate AS shift_date,
            shift_number,
            shift_start_utc,
            shift_end_utc,
            planned_production_time_minutes,
            actual_production_time_minutes,
            downtime_minutes,
            planned_downtime_minutes,
            unplanned_downtime_minutes,
            total_cycles,
            good_cycles,
            scrap_cycles,
            rework_cycles,
            average_cycle_time_seconds,
            target_cycle_time_seconds,
            
            -- Calculate OEE components
            CASE WHEN planned_production_time_minutes > 0 
                 THEN ((planned_production_time_minutes - unplanned_downtime_minutes) / planned_production_time_minutes) * 100
                 ELSE 0 
            END AS availability_percent,
            
            CASE WHEN total_cycles > 0 AND target_cycle_time_seconds > 0 AND average_cycle_time_seconds > 0
                 THEN (target_cycle_time_seconds / average_cycle_time_seconds) * 100
                 ELSE 0 
            END AS performance_percent,
            
            CASE WHEN total_cycles > 0 
                 THEN (good_cycles * 100.0) / total_cycles
                 ELSE 0 
            END AS quality_percent,
            
            CASE WHEN planned_production_time_minutes > 0 
                 THEN (good_cycles * 60.0) / planned_production_time_minutes
                 ELSE 0 
            END AS throughput_units_per_hour
            
        FROM ShiftAggregates
        WHERE machine_id IS NOT NULL
    ) AS source ON target.machine_id = source.machine_id 
                AND target.shift_date = source.shift_date 
                AND target.shift_number = source.shift_number
    
    WHEN MATCHED THEN
        UPDATE SET
            actual_production_time_minutes = source.actual_production_time_minutes,
            downtime_minutes = source.downtime_minutes,
            planned_downtime_minutes = source.planned_downtime_minutes,
            unplanned_downtime_minutes = source.unplanned_downtime_minutes,
            total_cycles = source.total_cycles,
            good_cycles = source.good_cycles,
            scrap_cycles = source.scrap_cycles,
            rework_cycles = source.rework_cycles,
            average_cycle_time_seconds = source.average_cycle_time_seconds,
            target_cycle_time_seconds = source.target_cycle_time_seconds,
            availability_percent = source.availability_percent,
            performance_percent = source.performance_percent,
            quality_percent = source.quality_percent,
            oee_percent = (source.availability_percent / 100) * (source.performance_percent / 100) * (source.quality_percent / 100) * 100,
            throughput_units_per_hour = source.throughput_units_per_hour
    
    WHEN NOT MATCHED THEN
        INSERT (machine_id, line_id, shift_date, shift_number, shift_start_utc, shift_end_utc, 
                planned_production_time_minutes, actual_production_time_minutes, downtime_minutes, 
                planned_downtime_minutes, unplanned_downtime_minutes, total_cycles, good_cycles, 
                scrap_cycles, rework_cycles, average_cycle_time_seconds, target_cycle_time_seconds,
                availability_percent, performance_percent, quality_percent, oee_percent, throughput_units_per_hour)
        VALUES (source.machine_id, source.line_id, source.shift_date, source.shift_number, 
                source.shift_start_utc, source.shift_end_utc, source.planned_production_time_minutes, 
                source.actual_production_time_minutes, source.downtime_minutes, source.planned_downtime_minutes, 
                source.unplanned_downtime_minutes, source.total_cycles, source.good_cycles, source.scrap_cycles, 
                source.rework_cycles, source.average_cycle_time_seconds, source.target_cycle_time_seconds,
                source.availability_percent, source.performance_percent, source.quality_percent,
                (source.availability_percent / 100) * (source.performance_percent / 100) * (source.quality_percent / 100) * 100,
                source.throughput_units_per_hour);
    
    SELECT @@ROWCOUNT AS rows_affected;
END;
GO

-- =============================================
-- 4. DATA INGESTION PROCEDURES
-- =============================================

-- High-speed machine event ingestion
CREATE OR ALTER PROCEDURE dbo.sp_InsertMachineEvent
    @MachineId NVARCHAR(50),
    @Timestamp DATETIME2,
    @EventType NVARCHAR(50),
    @EventValue DECIMAL(18,6) = NULL,
    @EventText NVARCHAR(500) = NULL,
    @PayloadJson NVARCHAR(MAX) = NULL,
    @SourceSystem NVARCHAR(50) = 'PLC'
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Validate machine exists
    IF NOT EXISTS (SELECT 1 FROM dbo.Machines WHERE machine_id = @MachineId AND is_active = 1)
    BEGIN
        RAISERROR('Machine %s not found or inactive', 16, 1, @MachineId);
        RETURN;
    END
    
    -- Insert event with minimal locking
    INSERT INTO dbo.MachineEvents (machine_id, timestamp_utc, event_type, event_value, event_text, payload_json, source_system)
    VALUES (@MachineId, @Timestamp, @EventType, @EventValue, @EventText, @PayloadJson, @SourceSystem);
    
    -- Return event ID for reference
    SELECT SCOPE_IDENTITY() AS event_id;
END;
GO

-- Batch machine event insertion for high throughput
CREATE OR ALTER PROCEDURE dbo.sp_InsertMachineEventsBatch
    @EventsJson NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Parse JSON input
    WITH EventData AS (
        SELECT 
            JSON_VALUE(value, '$.machine_id') AS machine_id,
            CAST(JSON_VALUE(value, '$.timestamp') AS DATETIME2) AS timestamp_utc,
            JSON_VALUE(value, '$.event_type') AS event_type,
            CAST(JSON_VALUE(value, '$.event_value') AS DECIMAL(18,6)) AS event_value,
            JSON_VALUE(value, '$.event_text') AS event_text,
            JSON_VALUE(value, '$.payload_json') AS payload_json,
            ISNULL(JSON_VALUE(value, '$.source_system'), 'PLC') AS source_system
        FROM OPENJSON(@EventsJson)
    )
    
    INSERT INTO dbo.MachineEvents (machine_id, timestamp_utc, event_type, event_value, event_text, payload_json, source_system)
    SELECT machine_id, timestamp_utc, event_type, event_value, event_text, payload_json, source_system
    FROM EventData e
    WHERE EXISTS (SELECT 1 FROM dbo.Machines m WHERE m.machine_id = e.machine_id AND m.is_active = 1);
    
    SELECT @@ROWCOUNT AS events_inserted;
END;
GO

-- Production cycle completion
CREATE OR ALTER PROCEDURE dbo.sp_CompleteCycle
    @CycleId BIGINT,
    @EndTimestamp DATETIME2,
    @GoodPartsCount INT = 0,
    @ScrapPartsCount INT = 0,
    @ReworkPartsCount INT = 0
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @StartTimestamp DATETIME2;
    DECLARE @CycleTime DECIMAL(10,3);
    
    -- Get start timestamp and calculate cycle time
    SELECT @StartTimestamp = start_timestamp_utc
    FROM dbo.ProductionCycles
    WHERE cycle_id = @CycleId;
    
    IF @StartTimestamp IS NULL
    BEGIN
        RAISERROR('Cycle %d not found', 16, 1, @CycleId);
        RETURN;
    END
    
    SET @CycleTime = DATEDIFF_BIG(MILLISECOND, @StartTimestamp, @EndTimestamp) / 1000.0;
    
    -- Update cycle
    UPDATE dbo.ProductionCycles
    SET 
        end_timestamp_utc = @EndTimestamp,
        cycle_time_seconds = @CycleTime,
        good_parts_count = @GoodPartsCount,
        scrap_parts_count = @ScrapPartsCount,
        rework_parts_count = @ReworkPartsCount,
        cycle_status = 'COMPLETED'
    WHERE cycle_id = @CycleId;
    
    SELECT @CycleTime AS cycle_time_seconds;
END;
GO

-- =============================================
-- 5. MAINTENANCE AND CLEANUP PROCEDURES
-- =============================================

-- Data retention cleanup
CREATE OR ALTER PROCEDURE dbo.sp_CleanupOldData
    @TableName NVARCHAR(128) = NULL,
    @DryRun BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @sql NVARCHAR(MAX);
    DECLARE @cutoff_date DATETIME2;
    DECLARE @retention_days INT;
    DECLARE @rows_deleted BIGINT = 0;
    
    -- Process all tables if none specified
    DECLARE cleanup_cursor CURSOR FOR
    SELECT table_name, retention_days
    FROM dbo.DataRetentionPolicies
    WHERE is_active = 1
      AND (@TableName IS NULL OR table_name = @TableName);
    
    OPEN cleanup_cursor;
    FETCH NEXT FROM cleanup_cursor INTO @TableName, @retention_days;
    
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @cutoff_date = DATEADD(DAY, -@retention_days, GETUTCDATE());
        
        -- Build dynamic SQL based on table
        IF @TableName = 'MachineEvents'
            SET @sql = 'DELETE FROM dbo.MachineEvents WHERE timestamp_utc < @cutoff_date';
        ELSE IF @TableName = 'ProductionCycles'
            SET @sql = 'DELETE FROM dbo.ProductionCycles WHERE start_timestamp_utc < @cutoff_date';
        ELSE IF @TableName = 'DowntimeEvents'
            SET @sql = 'DELETE FROM dbo.DowntimeEvents WHERE start_timestamp_utc < @cutoff_date';
        ELSE IF @TableName = 'QualityEvents'
            SET @sql = 'DELETE FROM dbo.QualityEvents WHERE timestamp_utc < @cutoff_date';
        ELSE IF @TableName LIKE 'OEE_Rollup_%'
            SET @sql = 'DELETE FROM dbo.' + QUOTENAME(@TableName) + ' WHERE bucket_start_utc < @cutoff_date OR shift_date < CAST(@cutoff_date AS DATE)';
        
        IF @sql IS NOT NULL
        BEGIN
            IF @DryRun = 1
            BEGIN
                -- Count rows that would be deleted
                SET @sql = REPLACE(@sql, 'DELETE FROM', 'SELECT COUNT(*) FROM');
                EXEC sp_executesql @sql, N'@cutoff_date DATETIME2', @cutoff_date;
                PRINT 'Table: ' + @TableName + ', Cutoff: ' + CAST(@cutoff_date AS NVARCHAR(30));
            END
            ELSE
            BEGIN
                -- Actually delete the data
                EXEC sp_executesql @sql, N'@cutoff_date DATETIME2', @cutoff_date;
                SET @rows_deleted = @rows_deleted + @@ROWCOUNT;
            END
        END
        
        -- Update last cleanup time
        IF @DryRun = 0
        BEGIN
            UPDATE dbo.DataRetentionPolicies
            SET last_cleanup_utc = GETUTCDATE()
            WHERE table_name = @TableName;
        END
        
        FETCH NEXT FROM cleanup_cursor INTO @TableName, @retention_days;
    END
    
    CLOSE cleanup_cursor;
    DEALLOCATE cleanup_cursor;
    
    IF @DryRun = 0
        SELECT @rows_deleted AS total_rows_deleted;
END;
GO

-- Performance monitoring
CREATE OR ALTER PROCEDURE dbo.sp_LogQueryPerformance
    @QueryType NVARCHAR(100),
    @ExecutionTimeMs INT,
    @CpuTimeMs INT = NULL,
    @LogicalReads BIGINT = NULL,
    @PhysicalReads BIGINT = NULL,
    @RowCount BIGINT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    INSERT INTO dbo.QueryPerformanceLog (query_type, execution_time_ms, cpu_time_ms, logical_reads, physical_reads, row_count)
    VALUES (@QueryType, @ExecutionTimeMs, @CpuTimeMs, @LogicalReads, @PhysicalReads, @RowCount);
END;
GO

-- =============================================
-- 6. PARETO ANALYSIS PROCEDURES
-- =============================================

-- Get top downtime reasons (Pareto analysis)
CREATE OR ALTER PROCEDURE dbo.sp_GetDowntimePareto
    @StartDate DATETIME2,
    @EndDate DATETIME2,
    @LineId NVARCHAR(50) = NULL,
    @MachineId NVARCHAR(50) = NULL,
    @TopN INT = 10
AS
BEGIN
    SET NOCOUNT ON;
    
    WITH DowntimeAnalysis AS (
        SELECT 
            dr.reason_code,
            dr.reason_description,
            dr.reason_category,
            dr.reason_subcategory,
            COUNT(*) AS occurrence_count,
            SUM(ISNULL(de.duration_minutes, DATEDIFF(MINUTE, de.start_timestamp_utc, @EndDate))) AS total_minutes,
            AVG(ISNULL(de.duration_minutes, DATEDIFF(MINUTE, de.start_timestamp_utc, @EndDate))) AS avg_duration_minutes
        FROM dbo.DowntimeEvents de
        INNER JOIN dbo.DowntimeReasons dr ON de.reason_code = dr.reason_code
        WHERE de.start_timestamp_utc >= @StartDate
          AND de.start_timestamp_utc < @EndDate
          AND (@LineId IS NULL OR de.line_id = @LineId)
          AND (@MachineId IS NULL OR de.machine_id = @MachineId)
          AND dr.is_active = 1
        GROUP BY dr.reason_code, dr.reason_description, dr.reason_category, dr.reason_subcategory
    ),
    RankedReasons AS (
        SELECT *,
               ROW_NUMBER() OVER (ORDER BY total_minutes DESC) AS rank_by_duration,
               SUM(total_minutes) OVER () AS grand_total_minutes,
               SUM(total_minutes) OVER (ORDER BY total_minutes DESC ROWS UNBOUNDED PRECEDING) AS cumulative_minutes
        FROM DowntimeAnalysis
    )
    
    SELECT TOP (@TopN)
        reason_code,
        reason_description,
        reason_category,
        reason_subcategory,
        occurrence_count,
        total_minutes,
        avg_duration_minutes,
        rank_by_duration,
        (total_minutes * 100.0) / grand_total_minutes AS percent_of_total,
        (cumulative_minutes * 100.0) / grand_total_minutes AS cumulative_percent
    FROM RankedReasons
    ORDER BY total_minutes DESC;
END;
GO

-- =============================================
-- 7. TREND ANALYSIS PROCEDURES
-- =============================================

-- Get OEE trends over time
CREATE OR ALTER PROCEDURE dbo.sp_GetOEETrends
    @StartDate DATETIME2,
    @EndDate DATETIME2,
    @LineId NVARCHAR(50) = NULL,
    @MachineId NVARCHAR(50) = NULL,
    @Granularity NVARCHAR(10) = 'HOURLY' -- HOURLY, SHIFT, DAILY
AS
BEGIN
    SET NOCOUNT ON;
    
    IF @Granularity = 'HOURLY'
    BEGIN
        SELECT 
            machine_id,
            line_id,
            bucket_start_utc AS period_start,
            bucket_end_utc AS period_end,
            availability_percent,
            performance_percent,
            quality_percent,
            oee_percent,
            throughput_units_per_hour,
            total_cycles,
            good_cycles,
            downtime_minutes,
            top_downtime_reason
        FROM dbo.OEE_Rollup_Hourly
        WHERE bucket_start_utc >= @StartDate
          AND bucket_start_utc < @EndDate
          AND (@LineId IS NULL OR line_id = @LineId)
          AND (@MachineId IS NULL OR machine_id = @MachineId)
        ORDER BY machine_id, bucket_start_utc;
    END
    ELSE IF @Granularity = 'SHIFT'
    BEGIN
        SELECT 
            machine_id,
            line_id,
            shift_date,
            shift_number,
            shift_start_utc AS period_start,
            shift_end_utc AS period_end,
            availability_percent,
            performance_percent,
            quality_percent,
            oee_percent,
            throughput_units_per_hour,
            total_cycles,
            good_cycles,
            downtime_minutes
        FROM dbo.OEE_Rollup_Shift
        WHERE shift_start_utc >= @StartDate
          AND shift_start_utc < @EndDate
          AND (@LineId IS NULL OR line_id = @LineId)
          AND (@MachineId IS NULL OR machine_id = @MachineId)
        ORDER BY machine_id, shift_date, shift_number;
    END
    ELSE IF @Granularity = 'DAILY'
    BEGIN
        SELECT 
            machine_id,
            line_id,
            date_utc AS period_date,
            availability_percent,
            performance_percent,
            quality_percent,
            oee_percent,
            throughput_units_per_hour,
            total_cycles,
            good_cycles,
            downtime_minutes
        FROM dbo.OEE_Rollup_Daily
        WHERE date_utc >= CAST(@StartDate AS DATE)
          AND date_utc < CAST(@EndDate AS DATE)
          AND (@LineId IS NULL OR line_id = @LineId)
          AND (@MachineId IS NULL OR machine_id = @MachineId)
        ORDER BY machine_id, date_utc;
    END
END;
GO

PRINT 'SQL Server stored procedures created successfully.';
PRINT 'Key procedures:';
PRINT '  - sp_CalculateRealTimeOEE: Real-time OEE calculation for any machine/timeframe';
PRINT '  - sp_CalculateHourlyRollups: Automated hourly aggregation';
PRINT '  - sp_CalculateShiftRollups: Shift-level rollups';
PRINT '  - sp_InsertMachineEvent: High-speed event ingestion';
PRINT '  - sp_InsertMachineEventsBatch: Batch event processing';
PRINT '  - sp_GetDowntimePareto: Pareto analysis for downtime';
PRINT '  - sp_GetOEETrends: Trend analysis at multiple granularities';
PRINT '  - sp_CleanupOldData: Automated data retention management';
GO