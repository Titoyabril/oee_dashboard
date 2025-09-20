-- =============================================
-- OEE Dashboard - SQL Server Database Setup
-- Complete Database Initialization and Configuration
-- Production-Ready Setup for Manufacturing Analytics
-- =============================================

-- =============================================
-- 1. DATABASE CREATION AND CONFIGURATION
-- =============================================

-- Create database (run with appropriate permissions)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'OEE_Dashboard')
BEGIN
    CREATE DATABASE OEE_Dashboard
    COLLATE SQL_Latin1_General_CP1_CI_AS;
END
GO

USE OEE_Dashboard;
GO

-- Configure database settings for performance
ALTER DATABASE OEE_Dashboard SET RECOVERY FULL;
ALTER DATABASE OEE_Dashboard SET AUTO_CREATE_STATISTICS ON;
ALTER DATABASE OEE_Dashboard SET AUTO_UPDATE_STATISTICS ON;
ALTER DATABASE OEE_Dashboard SET AUTO_UPDATE_STATISTICS_ASYNC ON;
ALTER DATABASE OEE_Dashboard SET PARAMETERIZATION FORCED;
ALTER DATABASE OEE_Dashboard SET READ_COMMITTED_SNAPSHOT ON;
GO

-- =============================================
-- 2. FILEGROUP CONFIGURATION FOR PARTITIONING
-- =============================================

-- Create filegroups for different data types
ALTER DATABASE OEE_Dashboard ADD FILEGROUP [FG_Current];
ALTER DATABASE OEE_Dashboard ADD FILEGROUP [FG_Historical];
ALTER DATABASE OEE_Dashboard ADD FILEGROUP [FG_Archive];
GO

-- Add data files (adjust paths for your environment)
-- Current data (last 3 months)
ALTER DATABASE OEE_Dashboard 
ADD FILE (
    NAME = 'OEE_Current_Data',
    FILENAME = 'C:\SQLData\OEE_Dashboard_Current.mdf',
    SIZE = 1GB,
    MAXSIZE = 50GB,
    FILEGROWTH = 100MB
) TO FILEGROUP [FG_Current];

-- Historical data (older than 3 months)
ALTER DATABASE OEE_Dashboard 
ADD FILE (
    NAME = 'OEE_Historical_Data',
    FILENAME = 'C:\SQLData\OEE_Dashboard_Historical.mdf',
    SIZE = 2GB,
    MAXSIZE = 100GB,
    FILEGROWTH = 500MB
) TO FILEGROUP [FG_Historical];

-- Archive data (compressed, read-only)
ALTER DATABASE OEE_Dashboard 
ADD FILE (
    NAME = 'OEE_Archive_Data',
    FILENAME = 'C:\SQLData\OEE_Dashboard_Archive.mdf',
    SIZE = 1GB,
    MAXSIZE = 200GB,
    FILEGROWTH = 1GB
) TO FILEGROUP [FG_Archive];
GO

-- =============================================
-- 3. PARTITION FUNCTION AND SCHEME SETUP
-- =============================================

-- Create partition function for monthly partitioning
CREATE PARTITION FUNCTION PF_Monthly(DATETIME2)
AS RANGE RIGHT FOR VALUES (
    '2024-01-01', '2024-02-01', '2024-03-01', '2024-04-01',
    '2024-05-01', '2024-06-01', '2024-07-01', '2024-08-01',
    '2024-09-01', '2024-10-01', '2024-11-01', '2024-12-01',
    '2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01',
    '2025-05-01', '2025-06-01', '2025-07-01', '2025-08-01',
    '2025-09-01', '2025-10-01', '2025-11-01', '2025-12-01',
    '2026-01-01', '2026-02-01', '2026-03-01', '2026-04-01',
    '2026-05-01', '2026-06-01', '2026-07-01', '2026-08-01',
    '2026-09-01', '2026-10-01', '2026-11-01', '2026-12-01'
);
GO

-- Create partition scheme
CREATE PARTITION SCHEME PartitionScheme_Monthly
AS PARTITION PF_Monthly
TO ([FG_Current], [FG_Current], [FG_Current], [FG_Current],
    [FG_Current], [FG_Current], [FG_Current], [FG_Current],
    [FG_Current], [FG_Current], [FG_Current], [FG_Current],
    [FG_Historical], [FG_Historical], [FG_Historical], [FG_Historical],
    [FG_Historical], [FG_Historical], [FG_Historical], [FG_Historical],
    [FG_Historical], [FG_Historical], [FG_Historical], [FG_Historical],
    [FG_Archive], [FG_Archive], [FG_Archive], [FG_Archive],
    [FG_Archive], [FG_Archive], [FG_Archive], [FG_Archive],
    [FG_Archive], [FG_Archive], [FG_Archive], [FG_Archive]);
GO

-- =============================================
-- 4. SECURITY SETUP
-- =============================================

-- Create application user for Django
IF NOT EXISTS (SELECT name FROM sys.server_principals WHERE name = 'oee_app_user')
BEGIN
    CREATE LOGIN oee_app_user WITH PASSWORD = 'OEE_App_P@ssw0rd_2024!', CHECK_POLICY = ON;
END
GO

CREATE USER oee_app_user FOR LOGIN oee_app_user;
GO

-- Grant necessary permissions for application user
ALTER ROLE db_datareader ADD MEMBER oee_app_user;
ALTER ROLE db_datawriter ADD MEMBER oee_app_user;
ALTER ROLE db_ddladmin ADD MEMBER oee_app_user;  -- For migrations
GRANT EXECUTE ON SCHEMA::dbo TO oee_app_user;
GO

-- Create read-only user for dashboard queries
IF NOT EXISTS (SELECT name FROM sys.server_principals WHERE name = 'oee_readonly_user')
BEGIN
    CREATE LOGIN oee_readonly_user WITH PASSWORD = 'OEE_ReadOnly_P@ssw0rd_2024!', CHECK_POLICY = ON;
END
GO

CREATE USER oee_readonly_user FOR LOGIN oee_readonly_user;
GO

ALTER ROLE db_datareader ADD MEMBER oee_readonly_user;
GRANT EXECUTE ON SCHEMA::dbo TO oee_readonly_user;
GO

-- Create service account for automated tasks
IF NOT EXISTS (SELECT name FROM sys.server_principals WHERE name = 'oee_service_user')
BEGIN
    CREATE LOGIN oee_service_user WITH PASSWORD = 'OEE_Service_P@ssw0rd_2024!', CHECK_POLICY = ON;
END
GO

CREATE USER oee_service_user FOR LOGIN oee_service_user;
GO

ALTER ROLE db_datareader ADD MEMBER oee_service_user;
ALTER ROLE db_datawriter ADD MEMBER oee_service_user;
GRANT EXECUTE ON SCHEMA::dbo TO oee_service_user;
GO

-- =============================================
-- 5. PERFORMANCE MONITORING SETUP
-- =============================================

-- Enable Query Store for performance monitoring
ALTER DATABASE OEE_Dashboard SET QUERY_STORE = ON;
ALTER DATABASE OEE_Dashboard SET QUERY_STORE (
    OPERATION_MODE = READ_WRITE,
    CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = 30),
    DATA_FLUSH_INTERVAL_SECONDS = 900,
    INTERVAL_LENGTH_MINUTES = 60,
    MAX_STORAGE_SIZE_MB = 1000,
    QUERY_CAPTURE_MODE = AUTO,
    SIZE_BASED_CLEANUP_MODE = AUTO
);
GO

-- Create extended events session for monitoring
IF NOT EXISTS (SELECT name FROM sys.server_event_sessions WHERE name = 'OEE_Performance_Monitor')
BEGIN
    CREATE EVENT SESSION [OEE_Performance_Monitor] ON SERVER 
    ADD EVENT sqlserver.sql_statement_completed(
        ACTION(sqlserver.client_app_name,sqlserver.database_name,sqlserver.username)
        WHERE ([duration]>(1000000) AND [sqlserver].[database_name]=N'OEE_Dashboard')
    ),
    ADD EVENT sqlserver.rpc_completed(
        ACTION(sqlserver.client_app_name,sqlserver.database_name,sqlserver.username)
        WHERE ([duration]>(1000000) AND [sqlserver].[database_name]=N'OEE_Dashboard')
    )
    ADD TARGET package0.event_file(SET filename=N'C:\SQLLogs\OEE_Performance_Monitor.xel')
    WITH (MAX_MEMORY=4096 KB,EVENT_RETENTION_MODE=ALLOW_SINGLE_EVENT_LOSS,MAX_DISPATCH_LATENCY=30 SECONDS,MAX_EVENT_SIZE=0 KB,MEMORY_PARTITION_MODE=NONE,TRACK_CAUSALITY=OFF,STARTUP_STATE=ON);
END
GO

-- Start the monitoring session
ALTER EVENT SESSION [OEE_Performance_Monitor] ON SERVER STATE = START;
GO

-- =============================================
-- 6. MAINTENANCE JOBS SETUP
-- =============================================

-- Job to calculate hourly rollups
EXEC msdb.dbo.sp_add_job
    @job_name = N'OEE_Calculate_Hourly_Rollups',
    @enabled = 1,
    @description = N'Calculate OEE hourly rollups for dashboard',
    @category_name = N'Data Collector';
GO

EXEC msdb.dbo.sp_add_jobstep
    @job_name = N'OEE_Calculate_Hourly_Rollups',
    @step_name = N'Execute_Hourly_Calculation',
    @command = N'EXEC dbo.sp_CalculateHourlyRollups;',
    @database_name = N'OEE_Dashboard';
GO

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'Every_5_Minutes',
    @freq_type = 4,
    @freq_interval = 1,
    @freq_subday_type = 4,
    @freq_subday_interval = 5;
GO

EXEC msdb.dbo.sp_attach_schedule
    @job_name = N'OEE_Calculate_Hourly_Rollups',
    @schedule_name = N'Every_5_Minutes';
GO

EXEC msdb.dbo.sp_add_jobserver
    @job_name = N'OEE_Calculate_Hourly_Rollups';
GO

-- Job to calculate shift rollups
EXEC msdb.dbo.sp_add_job
    @job_name = N'OEE_Calculate_Shift_Rollups',
    @enabled = 1,
    @description = N'Calculate OEE shift rollups',
    @category_name = N'Data Collector';
GO

EXEC msdb.dbo.sp_add_jobstep
    @job_name = N'OEE_Calculate_Shift_Rollups',
    @step_name = N'Execute_Shift_Calculation',
    @command = N'EXEC dbo.sp_CalculateShiftRollups;',
    @database_name = N'OEE_Dashboard';
GO

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'Every_Hour',
    @freq_type = 4,
    @freq_interval = 1,
    @freq_subday_type = 8,
    @freq_subday_interval = 1;
GO

EXEC msdb.dbo.sp_attach_schedule
    @job_name = N'OEE_Calculate_Shift_Rollups',
    @schedule_name = N'Every_Hour';
GO

EXEC msdb.dbo.sp_add_jobserver
    @job_name = N'OEE_Calculate_Shift_Rollups';
GO

-- Job for data cleanup
EXEC msdb.dbo.sp_add_job
    @job_name = N'OEE_Data_Cleanup',
    @enabled = 1,
    @description = N'Clean up old OEE data based on retention policies',
    @category_name = N'Database Maintenance';
GO

EXEC msdb.dbo.sp_add_jobstep
    @job_name = N'OEE_Data_Cleanup',
    @step_name = N'Execute_Cleanup',
    @command = N'EXEC dbo.sp_CleanupOldData @DryRun = 0;',
    @database_name = N'OEE_Dashboard';
GO

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'Daily_2AM',
    @freq_type = 4,
    @freq_interval = 1,
    @active_start_time = 20000;
GO

EXEC msdb.dbo.sp_attach_schedule
    @job_name = N'OEE_Data_Cleanup',
    @schedule_name = N'Daily_2AM';
GO

EXEC msdb.dbo.sp_add_jobserver
    @job_name = N'OEE_Data_Cleanup';
GO

-- =============================================
-- 7. INDEX MAINTENANCE
-- =============================================

-- Create index maintenance job
EXEC msdb.dbo.sp_add_job
    @job_name = N'OEE_Index_Maintenance',
    @enabled = 1,
    @description = N'Maintain indexes for optimal OEE dashboard performance',
    @category_name = N'Database Maintenance';
GO

EXEC msdb.dbo.sp_add_jobstep
    @job_name = N'OEE_Index_Maintenance',
    @step_name = N'Rebuild_Fragmented_Indexes',
    @command = N'
DECLARE @sql NVARCHAR(MAX);
DECLARE @table_name NVARCHAR(128);
DECLARE @index_name NVARCHAR(128);
DECLARE @fragmentation FLOAT;

DECLARE index_cursor CURSOR FOR
SELECT 
    OBJECT_NAME(ips.object_id) AS table_name,
    i.name AS index_name,
    ips.avg_fragmentation_in_percent
FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, ''LIMITED'') ips
INNER JOIN sys.indexes i ON ips.object_id = i.object_id AND ips.index_id = i.index_id
WHERE ips.avg_fragmentation_in_percent > 10
  AND ips.page_count > 1000
  AND i.type_desc IN (''CLUSTERED'', ''NONCLUSTERED'');

OPEN index_cursor;
FETCH NEXT FROM index_cursor INTO @table_name, @index_name, @fragmentation;

WHILE @@FETCH_STATUS = 0
BEGIN
    IF @fragmentation > 30
        SET @sql = ''ALTER INDEX ['' + @index_name + ''] ON [dbo].['' + @table_name + ''] REBUILD WITH (ONLINE = ON, SORT_IN_TEMPDB = ON);'';
    ELSE IF @fragmentation > 10
        SET @sql = ''ALTER INDEX ['' + @index_name + ''] ON [dbo].['' + @table_name + ''] REORGANIZE;'';
    
    EXEC sp_executesql @sql;
    
    FETCH NEXT FROM index_cursor INTO @table_name, @index_name, @fragmentation;
END

CLOSE index_cursor;
DEALLOCATE index_cursor;

-- Update statistics
EXEC sp_updatestats;
',
    @database_name = N'OEE_Dashboard';
GO

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'Weekly_Sunday_1AM',
    @freq_type = 8,
    @freq_interval = 1,
    @active_start_time = 10000;
GO

EXEC msdb.dbo.sp_attach_schedule
    @job_name = N'OEE_Index_Maintenance',
    @schedule_name = N'Weekly_Sunday_1AM';
GO

EXEC msdb.dbo.sp_add_jobserver
    @job_name = N'OEE_Index_Maintenance';
GO

-- =============================================
-- 8. BACKUP CONFIGURATION
-- =============================================

-- Full backup job
EXEC msdb.dbo.sp_add_job
    @job_name = N'OEE_Full_Backup',
    @enabled = 1,
    @description = N'Full backup of OEE Dashboard database',
    @category_name = N'Database Maintenance';
GO

EXEC msdb.dbo.sp_add_jobstep
    @job_name = N'OEE_Full_Backup',
    @step_name = N'Execute_Full_Backup',
    @command = N'
DECLARE @filename NVARCHAR(256);
SET @filename = ''C:\SQLBackups\OEE_Dashboard_Full_'' + CONVERT(NVARCHAR(8), GETDATE(), 112) + ''.bak'';

BACKUP DATABASE OEE_Dashboard 
TO DISK = @filename
WITH COMPRESSION, CHECKSUM, STATS = 10;
',
    @database_name = N'master';
GO

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'Daily_11PM',
    @freq_type = 4,
    @freq_interval = 1,
    @active_start_time = 230000;
GO

EXEC msdb.dbo.sp_attach_schedule
    @job_name = N'OEE_Full_Backup',
    @schedule_name = N'Daily_11PM';
GO

EXEC msdb.dbo.sp_add_jobserver
    @job_name = N'OEE_Full_Backup';
GO

-- Transaction log backup job
EXEC msdb.dbo.sp_add_job
    @job_name = N'OEE_Log_Backup',
    @enabled = 1,
    @description = N'Transaction log backup of OEE Dashboard database',
    @category_name = N'Database Maintenance';
GO

EXEC msdb.dbo.sp_add_jobstep
    @job_name = N'OEE_Log_Backup',
    @step_name = N'Execute_Log_Backup',
    @command = N'
DECLARE @filename NVARCHAR(256);
SET @filename = ''C:\SQLBackups\OEE_Dashboard_Log_'' + CONVERT(NVARCHAR(8), GETDATE(), 112) + ''_'' + REPLACE(CONVERT(NVARCHAR(8), GETDATE(), 108), '':'', '''') + ''.trn'';

BACKUP LOG OEE_Dashboard 
TO DISK = @filename
WITH COMPRESSION, CHECKSUM, STATS = 10;
',
    @database_name = N'master';
GO

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'Every_15_Minutes',
    @freq_type = 4,
    @freq_interval = 1,
    @freq_subday_type = 4,
    @freq_subday_interval = 15;
GO

EXEC msdb.dbo.sp_attach_schedule
    @job_name = N'OEE_Log_Backup',
    @schedule_name = N'Every_15_Minutes';
GO

EXEC msdb.dbo.sp_add_jobserver
    @job_name = N'OEE_Log_Backup';
GO

-- =============================================
-- 9. ALERTING SETUP
-- =============================================

-- Create alerts for critical events
EXEC msdb.dbo.sp_add_alert
    @name = N'OEE_Database_Full',
    @message_id = 1105,
    @severity = 0,
    @notification_message = N'OEE Dashboard database is full. Immediate action required.',
    @database_name = N'OEE_Dashboard';
GO

EXEC msdb.dbo.sp_add_alert
    @name = N'OEE_Log_Full',
    @message_id = 9002,
    @severity = 0,
    @notification_message = N'OEE Dashboard transaction log is full. Immediate action required.',
    @database_name = N'OEE_Dashboard';
GO

EXEC msdb.dbo.sp_add_alert
    @name = N'OEE_Corruption_Detected',
    @message_id = 824,
    @severity = 0,
    @notification_message = N'Database corruption detected in OEE Dashboard. Check immediately.',
    @database_name = N'OEE_Dashboard';
GO

-- =============================================
-- 10. VERIFICATION AND TESTING
-- =============================================

-- Create procedure to verify setup
CREATE OR ALTER PROCEDURE dbo.sp_VerifyOEESetup
AS
BEGIN
    SET NOCOUNT ON;
    
    PRINT 'OEE Dashboard Database Setup Verification';
    PRINT '========================================';
    
    -- Check database configuration
    PRINT 'Database Configuration:';
    SELECT 
        name,
        recovery_model_desc,
        state_desc,
        user_access_desc
    FROM sys.databases 
    WHERE name = 'OEE_Dashboard';
    
    -- Check filegroups
    PRINT CHAR(13) + 'Filegroups:';
    SELECT 
        fg.name AS filegroup_name,
        f.name AS file_name,
        f.size * 8 / 1024 AS size_mb,
        f.state_desc
    FROM sys.filegroups fg
    INNER JOIN sys.database_files f ON fg.data_space_id = f.data_space_id
    WHERE fg.name IN ('FG_Current', 'FG_Historical', 'FG_Archive');
    
    -- Check partition function
    PRINT CHAR(13) + 'Partition Function:';
    SELECT 
        pf.name,
        pf.type_desc,
        prv.boundary_id,
        prv.value
    FROM sys.partition_functions pf
    INNER JOIN sys.partition_range_values prv ON pf.function_id = prv.function_id
    WHERE pf.name = 'PF_Monthly';
    
    -- Check users and permissions
    PRINT CHAR(13) + 'Users and Roles:';
    SELECT 
        dp.name AS principal_name,
        dp.type_desc,
        r.name AS role_name
    FROM sys.database_principals dp
    LEFT JOIN sys.database_role_members rm ON dp.principal_id = rm.member_principal_id
    LEFT JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
    WHERE dp.name IN ('oee_app_user', 'oee_readonly_user', 'oee_service_user');
    
    -- Check SQL Agent jobs
    PRINT CHAR(13) + 'SQL Agent Jobs:';
    SELECT 
        j.name,
        j.enabled,
        ja.run_requested_date AS last_run
    FROM msdb.dbo.sysjobs j
    LEFT JOIN msdb.dbo.sysjobactivity ja ON j.job_id = ja.job_id
    WHERE j.name LIKE 'OEE_%';
    
    -- Check Query Store
    PRINT CHAR(13) + 'Query Store Status:';
    SELECT 
        actual_state_desc,
        readonly_reason,
        current_storage_size_mb,
        max_storage_size_mb
    FROM sys.database_query_store_options;
    
    PRINT CHAR(13) + 'Setup verification completed successfully!';
END;
GO

-- Run verification
EXEC dbo.sp_VerifyOEESetup;
GO

PRINT 'OEE Dashboard SQL Server setup completed successfully!';
PRINT 'Next steps:';
PRINT '1. Run the schema creation script (sql_server_schema.sql)';
PRINT '2. Run the stored procedures script (sql_server_stored_procedures.sql)';
PRINT '3. Run the views creation script (sql_server_views.sql)';
PRINT '4. Configure Django settings for SQL Server connection';
PRINT '5. Run Django migrations to sync with existing schema';
GO