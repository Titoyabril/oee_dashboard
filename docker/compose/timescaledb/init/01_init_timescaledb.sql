-- TimescaleDB Initialization Script for OEE Analytics
-- Creates hypertables, continuous aggregates, compression policies, and retention policies

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create roles
DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oee_readonly') THEN
        CREATE ROLE oee_readonly;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oee_readwrite') THEN
        CREATE ROLE oee_readwrite;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oee_analytics') THEN
        CREATE ROLE oee_analytics;
    END IF;
END
$$;

-- Grant permissions
GRANT CONNECT ON DATABASE oee_analytics TO oee_readonly, oee_readwrite, oee_analytics;

\echo 'Creating OEE Analytics schema...'

-- ========================================
-- Time-Series Telemetry Table
-- ========================================

CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMPTZ NOT NULL,
    machine_id VARCHAR(100) NOT NULL,
    metric_name VARCHAR(200) NOT NULL,
    value DOUBLE PRECISION,
    quality SMALLINT DEFAULT 192,  -- Sparkplug quality (192 = GOOD)
    meta JSONB,

    -- Indexes will be created after hypertable conversion
    CONSTRAINT telemetry_quality_check CHECK (quality >= 0 AND quality <= 255)
);

-- Convert to hypertable with space partitioning
SELECT create_hypertable(
    'telemetry',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Add space partitioning by machine_id for better query performance
SELECT add_dimension(
    'telemetry',
    'machine_id',
    number_partitions => 16,
    if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_telemetry_machine_time
    ON telemetry (machine_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_name_time
    ON telemetry (metric_name, time DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_quality
    ON telemetry (quality) WHERE quality < 192;  -- Partial index for bad quality

\echo 'Telemetry hypertable created'

-- ========================================
-- Event Store for Faults/Downtime
-- ========================================

CREATE TABLE IF NOT EXISTS events (
    event_id BIGSERIAL,
    machine_id VARCHAR(100) NOT NULL,
    line_id VARCHAR(100),
    event_type VARCHAR(50) NOT NULL,  -- 'FAULT', 'DOWNTIME', 'CYCLE', 'QUALITY'
    code VARCHAR(50),
    severity VARCHAR(20),
    ts_start TIMESTAMPTZ NOT NULL,
    ts_end TIMESTAMPTZ,
    duration_seconds NUMERIC(12, 3),
    payload JSONB,
    ack_by VARCHAR(100),
    ack_ts TIMESTAMPTZ,

    PRIMARY KEY (event_id, ts_start)
);

-- Convert to hypertable
SELECT create_hypertable(
    'events',
    'ts_start',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

-- Add space partitioning
SELECT add_dimension(
    'events',
    'machine_id',
    number_partitions => 16,
    if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_events_machine_start
    ON events (machine_id, ts_start DESC);

CREATE INDEX IF NOT EXISTS idx_events_type_start
    ON events (event_type, ts_start DESC);

CREATE INDEX IF NOT EXISTS idx_events_active
    ON events (machine_id, ts_end) WHERE ts_end IS NULL;  -- Active events

CREATE INDEX IF NOT EXISTS idx_events_severity
    ON events (severity, ts_start DESC) WHERE severity IN ('CRITICAL', 'HIGH');

\echo 'Events hypertable created'

-- ========================================
-- Continuous Aggregates (Pre-computed Rollups)
-- ========================================

-- 1-minute rollup
CREATE MATERIALIZED VIEW telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    machine_id,
    metric_name,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    STDDEV(value) AS stddev_value,
    COUNT(*) AS sample_count,
    AVG(quality) AS avg_quality
FROM telemetry
WHERE quality >= 192  -- Only include good quality data
GROUP BY bucket, machine_id, metric_name
WITH NO DATA;

\echo 'Creating 1-minute continuous aggregate refresh policy...'
SELECT add_continuous_aggregate_policy('telemetry_1min',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');

-- 5-minute rollup
CREATE MATERIALIZED VIEW telemetry_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    machine_id,
    metric_name,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95_value,
    COUNT(*) AS sample_count
FROM telemetry
WHERE quality >= 192
GROUP BY bucket, machine_id, metric_name
WITH NO DATA;

SELECT add_continuous_aggregate_policy('telemetry_5min',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');

-- 1-hour rollup
CREATE MATERIALIZED VIEW telemetry_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    machine_id,
    metric_name,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95_value,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) AS p99_value,
    COUNT(*) AS sample_count
FROM telemetry
WHERE quality >= 192
GROUP BY bucket, machine_id, metric_name
WITH NO DATA;

SELECT add_continuous_aggregate_policy('telemetry_1hour',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

\echo 'Continuous aggregates created'

-- ========================================
-- Compression Policies
-- ========================================

-- Enable compression on telemetry table for data older than 7 days
ALTER TABLE telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'machine_id, metric_name',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('telemetry', INTERVAL '7 days');

-- Enable compression on events table for data older than 30 days
ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'machine_id, event_type',
    timescaledb.compress_orderby = 'ts_start DESC'
);

SELECT add_compression_policy('events', INTERVAL '30 days');

\echo 'Compression policies created'

-- ========================================
-- Retention Policies
-- ========================================

-- Drop raw telemetry data older than 90 days (continuous aggregates retained)
SELECT add_retention_policy('telemetry', INTERVAL '90 days');

-- Drop events older than 2 years
SELECT add_retention_policy('events', INTERVAL '2 years');

\echo 'Retention policies created'

-- ========================================
-- Helper Functions for OEE Calculations
-- ========================================

-- Function to calculate availability for a time window
CREATE OR REPLACE FUNCTION calculate_availability(
    p_machine_id VARCHAR,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
)
RETURNS NUMERIC(5, 2) AS $$
DECLARE
    v_total_time NUMERIC;
    v_downtime NUMERIC;
    v_availability NUMERIC;
BEGIN
    -- Total planned time in seconds
    v_total_time := EXTRACT(EPOCH FROM (p_end_time - p_start_time));

    -- Sum of downtime events
    SELECT COALESCE(SUM(
        EXTRACT(EPOCH FROM (COALESCE(ts_end, p_end_time) - ts_start))
    ), 0)
    INTO v_downtime
    FROM events
    WHERE machine_id = p_machine_id
      AND event_type = 'DOWNTIME'
      AND ts_start BETWEEN p_start_time AND p_end_time;

    -- Calculate availability percentage
    IF v_total_time > 0 THEN
        v_availability := ((v_total_time - v_downtime) / v_total_time) * 100;
    ELSE
        v_availability := 0;
    END IF;

    RETURN v_availability;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get current machine status
CREATE OR REPLACE FUNCTION get_machine_status(p_machine_id VARCHAR)
RETURNS TABLE(
    machine_id VARCHAR,
    status VARCHAR,
    last_seen TIMESTAMPTZ,
    active_events BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_machine_id AS machine_id,
        CASE
            WHEN MAX(e.ts_end) IS NULL AND MAX(e.ts_start) > NOW() - INTERVAL '5 minutes' THEN 'DOWN'
            WHEN MAX(t.time) > NOW() - INTERVAL '1 minute' THEN 'RUNNING'
            ELSE 'IDLE'
        END AS status,
        MAX(t.time) AS last_seen,
        COUNT(e.event_id) FILTER (WHERE e.ts_end IS NULL) AS active_events
    FROM telemetry t
    LEFT JOIN events e ON e.machine_id = t.machine_id AND e.ts_end IS NULL
    WHERE t.machine_id = p_machine_id
      AND t.time > NOW() - INTERVAL '10 minutes'
    GROUP BY p_machine_id;
END;
$$ LANGUAGE plpgsql STABLE;

\echo 'Helper functions created'

-- ========================================
-- Permissions
-- ========================================

-- Read-only role
GRANT SELECT ON ALL TABLES IN SCHEMA public TO oee_readonly;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO oee_readonly;

-- Read-write role
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO oee_readwrite;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO oee_readwrite;

-- Analytics role (includes function execution)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO oee_analytics;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO oee_analytics;

\echo 'Permissions granted'

-- ========================================
-- Sample Data (Optional - for testing)
-- ========================================

-- Uncomment to insert sample data
-- INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
-- SELECT
--     NOW() - (n || ' seconds')::INTERVAL,
--     'MACHINE_01',
--     'temperature',
--     75 + (random() * 10)::NUMERIC(5,2),
--     192
-- FROM generate_series(1, 1000) AS n;

\echo 'TimescaleDB initialization complete!'
\echo ''
\echo 'Summary:'
\echo '- Hypertables created: telemetry, events'
\echo '- Continuous aggregates: 1min, 5min, 1hour rollups'
\echo '- Compression: enabled for data > 7 days (telemetry), > 30 days (events)'
\echo '- Retention: 90 days (telemetry), 2 years (events)'
\echo '- Helper functions: calculate_availability, get_machine_status'
\echo ''
