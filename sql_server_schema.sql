-- =============================================
-- OEE Dashboard - SQL Server Database Schema
-- Production-Ready Design for Manufacturing Analytics
-- Optimized for 50+ machines with second-level data ingestion
-- =============================================

-- Create database (run separately with appropriate permissions)
-- CREATE DATABASE OEE_Dashboard;
-- GO
-- USE OEE_Dashboard;
-- GO

-- =============================================
-- 1. MASTER DATA TABLES
-- =============================================

-- Plant hierarchy: Plant -> Area -> Line -> Machine
CREATE TABLE dbo.Plants (
    plant_id NVARCHAR(20) PRIMARY KEY,
    plant_name NVARCHAR(100) NOT NULL,
    location NVARCHAR(100),
    timezone NVARCHAR(50) DEFAULT 'UTC',
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    INDEX IX_Plants_Active (is_active) WHERE is_active = 1
);

CREATE TABLE dbo.Areas (
    area_id NVARCHAR(30) PRIMARY KEY,
    plant_id NVARCHAR(20) NOT NULL,
    area_name NVARCHAR(100) NOT NULL,
    description NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    CONSTRAINT FK_Areas_Plant FOREIGN KEY (plant_id) REFERENCES dbo.Plants(plant_id),
    INDEX IX_Areas_Plant (plant_id),
    INDEX IX_Areas_Active (is_active) WHERE is_active = 1
);

CREATE TABLE dbo.ProductionLines (
    line_id NVARCHAR(50) PRIMARY KEY,
    area_id NVARCHAR(30) NOT NULL,
    line_name NVARCHAR(100) NOT NULL,
    line_type NVARCHAR(50), -- Assembly, Packaging, etc.
    theoretical_cycle_time_seconds DECIMAL(10,3),
    target_availability_percent DECIMAL(5,2) DEFAULT 85.0,
    target_performance_percent DECIMAL(5,2) DEFAULT 95.0,
    target_quality_percent DECIMAL(5,2) DEFAULT 99.0,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    CONSTRAINT FK_Lines_Area FOREIGN KEY (area_id) REFERENCES dbo.Areas(area_id),
    INDEX IX_Lines_Area (area_id),
    INDEX IX_Lines_Active (is_active) WHERE is_active = 1
);

CREATE TABLE dbo.Machines (
    machine_id NVARCHAR(50) PRIMARY KEY,
    line_id NVARCHAR(50) NOT NULL,
    machine_name NVARCHAR(100) NOT NULL,
    machine_type NVARCHAR(50), -- Station, Robot, Conveyor, etc.
    asset_number NVARCHAR(50),
    manufacturer NVARCHAR(100),
    model NVARCHAR(100),
    serial_number NVARCHAR(100),
    installation_date DATE,
    theoretical_cycle_time_seconds DECIMAL(10,3),
    max_temperature DECIMAL(8,2),
    max_pressure DECIMAL(8,2),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    CONSTRAINT FK_Machines_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    INDEX IX_Machines_Line (line_id),
    INDEX IX_Machines_Active (is_active) WHERE is_active = 1
);

-- Products and Recipes
CREATE TABLE dbo.Products (
    product_id NVARCHAR(50) PRIMARY KEY,
    product_name NVARCHAR(200) NOT NULL,
    product_family NVARCHAR(100),
    sku NVARCHAR(100),
    standard_cycle_time_seconds DECIMAL(10,3),
    target_units_per_hour DECIMAL(10,2),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    INDEX IX_Products_Family (product_family),
    INDEX IX_Products_Active (is_active) WHERE is_active = 1
);

CREATE TABLE dbo.Recipes (
    recipe_id NVARCHAR(50) PRIMARY KEY,
    product_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    recipe_name NVARCHAR(200) NOT NULL,
    version NVARCHAR(20),
    target_cycle_time_seconds DECIMAL(10,3),
    setup_time_minutes DECIMAL(8,2),
    teardown_time_minutes DECIMAL(8,2),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    CONSTRAINT FK_Recipes_Product FOREIGN KEY (product_id) REFERENCES dbo.Products(product_id),
    CONSTRAINT FK_Recipes_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    INDEX IX_Recipes_Product (product_id),
    INDEX IX_Recipes_Line (line_id),
    INDEX IX_Recipes_Active (is_active) WHERE is_active = 1
);

-- Shift patterns and schedules
CREATE TABLE dbo.ShiftPatterns (
    shift_pattern_id INT IDENTITY(1,1) PRIMARY KEY,
    pattern_name NVARCHAR(100) NOT NULL,
    shift_1_start TIME NOT NULL,
    shift_1_end TIME NOT NULL,
    shift_2_start TIME,
    shift_2_end TIME,
    shift_3_start TIME,
    shift_3_end TIME,
    break_1_start TIME,
    break_1_duration_minutes INT,
    break_2_start TIME,
    break_2_duration_minutes INT,
    lunch_start TIME,
    lunch_duration_minutes INT,
    is_active BIT DEFAULT 1,
    INDEX IX_ShiftPatterns_Active (is_active) WHERE is_active = 1
);

-- Downtime reason codes
CREATE TABLE dbo.DowntimeReasons (
    reason_code NVARCHAR(20) PRIMARY KEY,
    reason_category NVARCHAR(50) NOT NULL, -- PLANNED, UNPLANNED
    reason_subcategory NVARCHAR(50), -- MAINTENANCE, SETUP, BREAKDOWN, etc.
    reason_description NVARCHAR(200) NOT NULL,
    mttr_target_minutes DECIMAL(8,2), -- Mean Time To Repair target
    is_planned BIT DEFAULT 0,
    severity_level INT DEFAULT 1, -- 1=Low, 2=Medium, 3=High, 4=Critical
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    INDEX IX_DowntimeReasons_Category (reason_category),
    INDEX IX_DowntimeReasons_Planned (is_planned),
    INDEX IX_DowntimeReasons_Active (is_active) WHERE is_active = 1
);

-- Quality defect codes
CREATE TABLE dbo.QualityDefects (
    defect_code NVARCHAR(20) PRIMARY KEY,
    defect_category NVARCHAR(50) NOT NULL, -- DIMENSIONAL, COSMETIC, FUNCTIONAL, etc.
    defect_description NVARCHAR(200) NOT NULL,
    severity_level INT DEFAULT 1, -- 1=Minor, 2=Major, 3=Critical
    rework_possible BIT DEFAULT 0,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    INDEX IX_QualityDefects_Category (defect_category),
    INDEX IX_QualityDefects_Severity (severity_level),
    INDEX IX_QualityDefects_Active (is_active) WHERE is_active = 1
);

-- =============================================
-- 2. TIME-SERIES DATA TABLES (PARTITIONED)
-- =============================================

-- Raw machine events (high-frequency telemetry)
-- Partitioned by month for optimal performance
CREATE TABLE dbo.MachineEvents (
    event_id BIGINT IDENTITY(1,1),
    machine_id NVARCHAR(50) NOT NULL,
    timestamp_utc DATETIME2 NOT NULL,
    event_type NVARCHAR(50) NOT NULL, -- CYCLE_START, CYCLE_END, ALARM, SENSOR_DATA, etc.
    event_value DECIMAL(18,6),
    event_text NVARCHAR(500),
    payload_json NVARCHAR(MAX), -- Additional flexible data
    source_system NVARCHAR(50) DEFAULT 'PLC', -- PLC, SCADA, MES, etc.
    quality_score TINYINT DEFAULT 100, -- Data quality indicator 0-100
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Clustered index optimized for time-series queries
    INDEX CIX_MachineEvents_Machine_Time CLUSTERED (machine_id, timestamp_utc),
    
    -- Non-clustered indexes for different query patterns
    INDEX IX_MachineEvents_Time (timestamp_utc),
    INDEX IX_MachineEvents_Type (event_type),
    INDEX IX_MachineEvents_Source (source_system),
    
    -- Filtered index for recent hot data (last 72 hours)
    INDEX IX_MachineEvents_Recent (machine_id, timestamp_utc, event_type) 
        WHERE timestamp_utc >= DATEADD(HOUR, -72, GETUTCDATE())
) 
ON PartitionScheme_Monthly(timestamp_utc); -- Partition by month

-- Production cycles (completed production units)
CREATE TABLE dbo.ProductionCycles (
    cycle_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    machine_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    recipe_id NVARCHAR(50),
    start_timestamp_utc DATETIME2 NOT NULL,
    end_timestamp_utc DATETIME2,
    cycle_time_seconds DECIMAL(10,3),
    target_cycle_time_seconds DECIMAL(10,3),
    good_parts_count INT DEFAULT 0,
    scrap_parts_count INT DEFAULT 0,
    rework_parts_count INT DEFAULT 0,
    cycle_status NVARCHAR(20) DEFAULT 'RUNNING', -- RUNNING, COMPLETED, ABORTED
    operator_id NVARCHAR(50),
    shift_id NVARCHAR(20),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Cycles_Machine FOREIGN KEY (machine_id) REFERENCES dbo.Machines(machine_id),
    CONSTRAINT FK_Cycles_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    CONSTRAINT FK_Cycles_Recipe FOREIGN KEY (recipe_id) REFERENCES dbo.Recipes(recipe_id),
    
    -- Clustered index for time-series locality
    INDEX CIX_ProductionCycles_Machine_Start CLUSTERED (machine_id, start_timestamp_utc),
    
    INDEX IX_ProductionCycles_Line_Start (line_id, start_timestamp_utc),
    INDEX IX_ProductionCycles_Recipe (recipe_id),
    INDEX IX_ProductionCycles_Status (cycle_status),
    INDEX IX_ProductionCycles_Shift (shift_id),
    
    -- Covering index for OEE calculations
    INDEX IX_ProductionCycles_OEE_Calc (machine_id, start_timestamp_utc) 
        INCLUDE (cycle_time_seconds, good_parts_count, scrap_parts_count, target_cycle_time_seconds)
)
ON PartitionScheme_Monthly(start_timestamp_utc);

-- Downtime events
CREATE TABLE dbo.DowntimeEvents (
    downtime_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    machine_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    start_timestamp_utc DATETIME2 NOT NULL,
    end_timestamp_utc DATETIME2,
    duration_minutes DECIMAL(10,2),
    reason_code NVARCHAR(20) NOT NULL,
    sub_reason NVARCHAR(100),
    description NVARCHAR(500),
    operator_id NVARCHAR(50),
    technician_id NVARCHAR(50),
    shift_id NVARCHAR(20),
    is_planned BIT DEFAULT 0,
    severity_level INT DEFAULT 1,
    repair_cost DECIMAL(10,2),
    parts_used NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Downtime_Machine FOREIGN KEY (machine_id) REFERENCES dbo.Machines(machine_id),
    CONSTRAINT FK_Downtime_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    CONSTRAINT FK_Downtime_Reason FOREIGN KEY (reason_code) REFERENCES dbo.DowntimeReasons(reason_code),
    
    -- Clustered index for time-series queries
    INDEX CIX_DowntimeEvents_Machine_Start CLUSTERED (machine_id, start_timestamp_utc),
    
    INDEX IX_DowntimeEvents_Line_Start (line_id, start_timestamp_utc),
    INDEX IX_DowntimeEvents_Reason (reason_code),
    INDEX IX_DowntimeEvents_Planned (is_planned),
    INDEX IX_DowntimeEvents_Shift (shift_id),
    
    -- Covering index for Pareto analysis
    INDEX IX_DowntimeEvents_Pareto (reason_code, start_timestamp_utc) 
        INCLUDE (duration_minutes, machine_id, line_id)
)
ON PartitionScheme_Monthly(start_timestamp_utc);

-- Quality events (defects and inspections)
CREATE TABLE dbo.QualityEvents (
    quality_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    machine_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    cycle_id BIGINT,
    timestamp_utc DATETIME2 NOT NULL,
    defect_code NVARCHAR(20),
    parts_inspected INT DEFAULT 1,
    parts_passed INT DEFAULT 0,
    parts_failed INT DEFAULT 0,
    parts_reworked INT DEFAULT 0,
    inspector_id NVARCHAR(50),
    inspection_method NVARCHAR(50), -- MANUAL, VISION, CMM, etc.
    shift_id NVARCHAR(20),
    notes NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Quality_Machine FOREIGN KEY (machine_id) REFERENCES dbo.Machines(machine_id),
    CONSTRAINT FK_Quality_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    CONSTRAINT FK_Quality_Cycle FOREIGN KEY (cycle_id) REFERENCES dbo.ProductionCycles(cycle_id),
    CONSTRAINT FK_Quality_Defect FOREIGN KEY (defect_code) REFERENCES dbo.QualityDefects(defect_code),
    
    -- Clustered index for time-series queries
    INDEX CIX_QualityEvents_Machine_Time CLUSTERED (machine_id, timestamp_utc),
    
    INDEX IX_QualityEvents_Line_Time (line_id, timestamp_utc),
    INDEX IX_QualityEvents_Defect (defect_code),
    INDEX IX_QualityEvents_Cycle (cycle_id),
    INDEX IX_QualityEvents_Shift (shift_id)
)
ON PartitionScheme_Monthly(timestamp_utc);

-- =============================================
-- 3. PRE-AGGREGATED ROLLUP TABLES
-- =============================================

-- Hourly rollups for fast dashboard queries
CREATE TABLE dbo.OEE_Rollup_Hourly (
    rollup_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    machine_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    bucket_start_utc DATETIME2 NOT NULL,
    bucket_end_utc DATETIME2 NOT NULL,
    shift_id NVARCHAR(20),
    
    -- Production metrics
    planned_production_time_minutes DECIMAL(8,2),
    actual_production_time_minutes DECIMAL(8,2),
    downtime_minutes DECIMAL(8,2),
    planned_downtime_minutes DECIMAL(8,2),
    unplanned_downtime_minutes DECIMAL(8,2),
    
    -- Cycle metrics
    total_cycles INT DEFAULT 0,
    good_cycles INT DEFAULT 0,
    scrap_cycles INT DEFAULT 0,
    rework_cycles INT DEFAULT 0,
    average_cycle_time_seconds DECIMAL(10,3),
    target_cycle_time_seconds DECIMAL(10,3),
    
    -- OEE Components (as percentages)
    availability_percent DECIMAL(5,2),
    performance_percent DECIMAL(5,2),
    quality_percent DECIMAL(5,2),
    oee_percent DECIMAL(5,2),
    
    -- Additional metrics
    throughput_units_per_hour DECIMAL(10,2),
    efficiency_percent DECIMAL(5,2),
    utilization_percent DECIMAL(5,2),
    
    -- Top downtime reason
    top_downtime_reason NVARCHAR(20),
    top_downtime_minutes DECIMAL(8,2),
    
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Rollup_Hourly_Machine FOREIGN KEY (machine_id) REFERENCES dbo.Machines(machine_id),
    CONSTRAINT FK_Rollup_Hourly_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    
    -- Columnstore index for analytical queries
    INDEX CCIX_OEE_Rollup_Hourly CLUSTERED COLUMNSTORE,
    
    -- B-tree indexes for point lookups
    INDEX IX_Rollup_Hourly_Machine_Time (machine_id, bucket_start_utc),
    INDEX IX_Rollup_Hourly_Line_Time (line_id, bucket_start_utc),
    INDEX IX_Rollup_Hourly_Shift (shift_id),
    
    CONSTRAINT UQ_Rollup_Hourly_Machine_Bucket UNIQUE (machine_id, bucket_start_utc)
)
ON PartitionScheme_Monthly(bucket_start_utc);

-- Shift rollups
CREATE TABLE dbo.OEE_Rollup_Shift (
    rollup_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    machine_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    shift_date DATE NOT NULL,
    shift_number INT NOT NULL, -- 1, 2, 3
    shift_start_utc DATETIME2 NOT NULL,
    shift_end_utc DATETIME2 NOT NULL,
    
    -- Production metrics
    planned_production_time_minutes DECIMAL(8,2),
    actual_production_time_minutes DECIMAL(8,2),
    downtime_minutes DECIMAL(8,2),
    planned_downtime_minutes DECIMAL(8,2),
    unplanned_downtime_minutes DECIMAL(8,2),
    
    -- Cycle metrics
    total_cycles INT DEFAULT 0,
    good_cycles INT DEFAULT 0,
    scrap_cycles INT DEFAULT 0,
    rework_cycles INT DEFAULT 0,
    average_cycle_time_seconds DECIMAL(10,3),
    target_cycle_time_seconds DECIMAL(10,3),
    
    -- OEE Components
    availability_percent DECIMAL(5,2),
    performance_percent DECIMAL(5,2),
    quality_percent DECIMAL(5,2),
    oee_percent DECIMAL(5,2),
    
    throughput_units_per_hour DECIMAL(10,2),
    
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Rollup_Shift_Machine FOREIGN KEY (machine_id) REFERENCES dbo.Machines(machine_id),
    CONSTRAINT FK_Rollup_Shift_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    
    INDEX CCIX_OEE_Rollup_Shift CLUSTERED COLUMNSTORE,
    INDEX IX_Rollup_Shift_Machine_Date (machine_id, shift_date),
    INDEX IX_Rollup_Shift_Line_Date (line_id, shift_date),
    
    CONSTRAINT UQ_Rollup_Shift_Machine_Date_Number UNIQUE (machine_id, shift_date, shift_number)
);

-- Daily rollups
CREATE TABLE dbo.OEE_Rollup_Daily (
    rollup_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    machine_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    date_utc DATE NOT NULL,
    
    -- Production metrics
    planned_production_time_minutes DECIMAL(10,2),
    actual_production_time_minutes DECIMAL(10,2),
    downtime_minutes DECIMAL(10,2),
    planned_downtime_minutes DECIMAL(10,2),
    unplanned_downtime_minutes DECIMAL(10,2),
    
    -- Cycle metrics
    total_cycles INT DEFAULT 0,
    good_cycles INT DEFAULT 0,
    scrap_cycles INT DEFAULT 0,
    rework_cycles INT DEFAULT 0,
    average_cycle_time_seconds DECIMAL(10,3),
    target_cycle_time_seconds DECIMAL(10,3),
    
    -- OEE Components
    availability_percent DECIMAL(5,2),
    performance_percent DECIMAL(5,2),
    quality_percent DECIMAL(5,2),
    oee_percent DECIMAL(5,2),
    
    throughput_units_per_hour DECIMAL(10,2),
    
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Rollup_Daily_Machine FOREIGN KEY (machine_id) REFERENCES dbo.Machines(machine_id),
    CONSTRAINT FK_Rollup_Daily_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    
    INDEX CCIX_OEE_Rollup_Daily CLUSTERED COLUMNSTORE,
    INDEX IX_Rollup_Daily_Machine_Date (machine_id, date_utc),
    INDEX IX_Rollup_Daily_Line_Date (line_id, date_utc),
    
    CONSTRAINT UQ_Rollup_Daily_Machine_Date UNIQUE (machine_id, date_utc)
);

-- =============================================
-- 4. SCHEDULE AND OPERATIONS TABLES
-- =============================================

-- Production schedules
CREATE TABLE dbo.ProductionSchedule (
    schedule_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    line_id NVARCHAR(50) NOT NULL,
    recipe_id NVARCHAR(50) NOT NULL,
    planned_start_utc DATETIME2 NOT NULL,
    planned_end_utc DATETIME2 NOT NULL,
    planned_quantity INT NOT NULL,
    actual_start_utc DATETIME2,
    actual_end_utc DATETIME2,
    actual_quantity INT,
    schedule_status NVARCHAR(20) DEFAULT 'PLANNED', -- PLANNED, ACTIVE, COMPLETED, CANCELLED
    priority_level INT DEFAULT 5, -- 1=Highest, 10=Lowest
    work_order_number NVARCHAR(50),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Schedule_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    CONSTRAINT FK_Schedule_Recipe FOREIGN KEY (recipe_id) REFERENCES dbo.Recipes(recipe_id),
    
    INDEX IX_Schedule_Line_Start (line_id, planned_start_utc),
    INDEX IX_Schedule_Status (schedule_status),
    INDEX IX_Schedule_WorkOrder (work_order_number)
);

-- Operator assignments and shifts
CREATE TABLE dbo.OperatorShifts (
    shift_assignment_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    operator_id NVARCHAR(50) NOT NULL,
    line_id NVARCHAR(50) NOT NULL,
    shift_date DATE NOT NULL,
    shift_number INT NOT NULL,
    start_time_utc DATETIME2 NOT NULL,
    end_time_utc DATETIME2,
    role NVARCHAR(50), -- OPERATOR, LEAD, TECHNICIAN, etc.
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_OperatorShifts_Line FOREIGN KEY (line_id) REFERENCES dbo.ProductionLines(line_id),
    
    INDEX IX_OperatorShifts_Operator_Date (operator_id, shift_date),
    INDEX IX_OperatorShifts_Line_Date (line_id, shift_date)
);

-- =============================================
-- 5. DATA RETENTION AND ARCHIVAL
-- =============================================

-- Data retention policies table
CREATE TABLE dbo.DataRetentionPolicies (
    policy_id INT IDENTITY(1,1) PRIMARY KEY,
    table_name NVARCHAR(128) NOT NULL,
    retention_days INT NOT NULL,
    archive_after_days INT,
    compression_enabled BIT DEFAULT 1,
    policy_description NVARCHAR(500),
    last_cleanup_utc DATETIME2,
    is_active BIT DEFAULT 1,
    
    INDEX IX_DataRetention_Table (table_name)
);

-- Insert default retention policies
INSERT INTO dbo.DataRetentionPolicies (table_name, retention_days, archive_after_days, policy_description)
VALUES 
    ('MachineEvents', 90, 30, 'High-frequency telemetry data'),
    ('ProductionCycles', 1095, 365, 'Production cycle history - 3 years'),
    ('DowntimeEvents', 1095, 365, 'Downtime analysis - 3 years'),
    ('QualityEvents', 1095, 365, 'Quality tracking - 3 years'),
    ('OEE_Rollup_Hourly', 365, 90, 'Hourly aggregates - 1 year'),
    ('OEE_Rollup_Shift', 1095, 365, 'Shift aggregates - 3 years'),
    ('OEE_Rollup_Daily', 2190, 730, 'Daily aggregates - 6 years');

-- =============================================
-- 6. SECURITY AND AUDIT
-- =============================================

-- Audit trail for configuration changes
CREATE TABLE dbo.ConfigurationAudit (
    audit_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    table_name NVARCHAR(128) NOT NULL,
    record_id NVARCHAR(100) NOT NULL,
    operation_type NVARCHAR(20) NOT NULL, -- INSERT, UPDATE, DELETE
    old_values NVARCHAR(MAX),
    new_values NVARCHAR(MAX),
    changed_by NVARCHAR(100) NOT NULL,
    changed_at DATETIME2 DEFAULT GETUTCDATE(),
    client_ip NVARCHAR(45),
    
    INDEX IX_ConfigAudit_Table_Time (table_name, changed_at),
    INDEX IX_ConfigAudit_User_Time (changed_by, changed_at)
);

-- Performance monitoring
CREATE TABLE dbo.QueryPerformanceLog (
    log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    query_type NVARCHAR(100) NOT NULL,
    execution_time_ms INT NOT NULL,
    cpu_time_ms INT,
    logical_reads BIGINT,
    physical_reads BIGINT,
    row_count BIGINT,
    query_hash BINARY(8),
    plan_hash BINARY(8),
    execution_timestamp DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_QueryPerf_Type_Time (query_type, execution_timestamp),
    INDEX IX_QueryPerf_Performance (execution_time_ms, execution_timestamp)
);

-- =============================================
-- 7. PARTITION SCHEME SETUP
-- Note: Requires manual setup of partition functions and schemes
-- =============================================

/*
-- Example partition function for monthly partitioning
CREATE PARTITION FUNCTION PF_Monthly(DATETIME2)
AS RANGE RIGHT FOR VALUES (
    '2024-01-01', '2024-02-01', '2024-03-01', '2024-04-01',
    '2024-05-01', '2024-06-01', '2024-07-01', '2024-08-01',
    '2024-09-01', '2024-10-01', '2024-11-01', '2024-12-01',
    '2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01',
    '2025-05-01', '2025-06-01', '2025-07-01', '2025-08-01',
    '2025-09-01', '2025-10-01', '2025-11-01', '2025-12-01'
);

-- Create partition scheme
CREATE PARTITION SCHEME PartitionScheme_Monthly
AS PARTITION PF_Monthly
ALL TO ([PRIMARY]); -- In production, map to multiple filegroups
*/

GO

-- =============================================
-- INITIAL SAMPLE DATA
-- =============================================

-- Sample plant hierarchy
INSERT INTO dbo.Plants (plant_id, plant_name, location, timezone)
VALUES ('PLANT001', 'Main Manufacturing Plant', 'Detroit, MI', 'America/Detroit');

INSERT INTO dbo.Areas (area_id, plant_id, area_name, description)
VALUES 
    ('AREA001', 'PLANT001', 'Assembly Area 1', 'Primary assembly operations'),
    ('AREA002', 'PLANT001', 'Packaging Area', 'Final packaging and shipping prep');

INSERT INTO dbo.ProductionLines (line_id, area_id, line_name, line_type, theoretical_cycle_time_seconds)
VALUES 
    ('LINE001', 'AREA001', 'Assembly Line 1', 'Assembly', 45.0),
    ('LINE002', 'AREA001', 'Assembly Line 2', 'Assembly', 52.0),
    ('LINE003', 'AREA002', 'Packaging Line 1', 'Packaging', 28.0);

INSERT INTO dbo.Machines (machine_id, line_id, machine_name, machine_type, theoretical_cycle_time_seconds)
VALUES 
    ('M001', 'LINE001', 'Station 1 - Component Insert', 'Assembly Station', 15.0),
    ('M002', 'LINE001', 'Station 2 - Torque Apply', 'Assembly Station', 12.0),
    ('M003', 'LINE001', 'Station 3 - Vision Inspect', 'Inspection Station', 8.0),
    ('M004', 'LINE002', 'Robot 1 - Pick & Place', 'Industrial Robot', 18.0),
    ('M005', 'LINE002', 'Station 4 - Final Assembly', 'Assembly Station', 22.0),
    ('M006', 'LINE003', 'Packaging Robot', 'Packaging Robot', 14.0);

-- Sample products and recipes
INSERT INTO dbo.Products (product_id, product_name, product_family, target_units_per_hour)
VALUES 
    ('PROD001', 'Widget Model A', 'Widgets', 120.0),
    ('PROD002', 'Widget Model B', 'Widgets', 95.0);

INSERT INTO dbo.Recipes (recipe_id, product_id, line_id, recipe_name, target_cycle_time_seconds)
VALUES 
    ('RCP001', 'PROD001', 'LINE001', 'Widget A - Standard Recipe', 45.0),
    ('RCP002', 'PROD002', 'LINE002', 'Widget B - Standard Recipe', 52.0);

-- Sample downtime reasons
INSERT INTO dbo.DowntimeReasons (reason_code, reason_category, reason_subcategory, reason_description, is_planned, severity_level)
VALUES 
    ('PM001', 'PLANNED', 'MAINTENANCE', 'Planned Preventive Maintenance', 1, 2),
    ('SETUP', 'PLANNED', 'CHANGEOVER', 'Product Changeover Setup', 1, 1),
    ('BREAK', 'PLANNED', 'BREAK', 'Scheduled Break', 1, 1),
    ('MECH', 'UNPLANNED', 'BREAKDOWN', 'Mechanical Failure', 0, 3),
    ('ELEC', 'UNPLANNED', 'BREAKDOWN', 'Electrical Failure', 0, 3),
    ('MATERIAL', 'UNPLANNED', 'SUPPLY', 'Material Shortage', 0, 2),
    ('QUALITY', 'UNPLANNED', 'QUALITY', 'Quality Hold', 0, 2),
    ('OPERATOR', 'UNPLANNED', 'OPERATOR', 'Operator Absence', 0, 1);

-- Sample quality defects
INSERT INTO dbo.QualityDefects (defect_code, defect_category, defect_description, severity_level, rework_possible)
VALUES 
    ('DIM001', 'DIMENSIONAL', 'Out of Tolerance - Length', 2, 0),
    ('DIM002', 'DIMENSIONAL', 'Out of Tolerance - Width', 2, 0),
    ('COS001', 'COSMETIC', 'Surface Scratch', 1, 1),
    ('COS002', 'COSMETIC', 'Color Variation', 1, 1),
    ('FUNC001', 'FUNCTIONAL', 'Performance Failure', 3, 0),
    ('FUNC002', 'FUNCTIONAL', 'Intermittent Operation', 2, 1);

GO