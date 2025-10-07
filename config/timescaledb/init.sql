-- Helios TimescaleDB Schema
-- Time-series optimized database for event storage and analysis

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- EVENTS TABLE (Main time-series table for all events)
-- ============================================================================

CREATE TABLE IF NOT EXISTS events (
    time        TIMESTAMPTZ NOT NULL,
    service     TEXT NOT NULL,
    level       TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    message     TEXT NOT NULL,
    metadata    JSONB,
    trace_id    TEXT,
    span_id     TEXT,
    host        TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable (time-series optimization)
SELECT create_hypertable(
    'events',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_events_service_time
    ON events (service, time DESC);

CREATE INDEX IF NOT EXISTS idx_events_level_time
    ON events (level, time DESC)
    WHERE level IN ('ERROR', 'CRITICAL');

CREATE INDEX IF NOT EXISTS idx_events_trace_id
    ON events (trace_id)
    WHERE trace_id IS NOT NULL;

-- GIN index for JSONB metadata queries
CREATE INDEX IF NOT EXISTS idx_events_metadata_gin
    ON events USING GIN (metadata);

COMMENT ON TABLE events IS 'Time-series event storage for all application events';

-- ============================================================================
-- ANOMALIES TABLE (Detected anomalies)
-- ============================================================================

CREATE TABLE IF NOT EXISTS anomalies (
    time         TIMESTAMPTZ NOT NULL,
    anomaly_id   TEXT NOT NULL,
    service      TEXT NOT NULL,
    score        DOUBLE PRECISION NOT NULL,
    threshold    DOUBLE PRECISION NOT NULL DEFAULT -0.7,
    severity     TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    features     JSONB NOT NULL,
    confidence   DOUBLE PRECISION,
    is_resolved  BOOLEAN DEFAULT FALSE,
    resolved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable(
    'anomalies',
    'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Indexes for anomaly queries
CREATE INDEX IF NOT EXISTS idx_anomalies_service_time
    ON anomalies (service, time DESC);

CREATE INDEX IF NOT EXISTS idx_anomalies_severity
    ON anomalies (severity, time DESC)
    WHERE severity IN ('HIGH', 'CRITICAL');

CREATE INDEX IF NOT EXISTS idx_anomalies_unresolved
    ON anomalies (time DESC)
    WHERE is_resolved = FALSE;

COMMENT ON TABLE anomalies IS 'ML-detected anomalies with severity and confidence scores';

-- ============================================================================
-- INCIDENT REPORTS TABLE (AI-generated reports)
-- ============================================================================

CREATE TABLE IF NOT EXISTS incident_reports (
    id            SERIAL PRIMARY KEY,
    report_id     TEXT UNIQUE NOT NULL,
    anomaly_id    TEXT NOT NULL,
    service       TEXT NOT NULL,
    severity      TEXT NOT NULL,
    content       TEXT NOT NULL,
    s3_location   TEXT,
    generated_at  TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_anomaly_id
    ON incident_reports (anomaly_id);

CREATE INDEX IF NOT EXISTS idx_reports_service_time
    ON incident_reports (service, generated_at DESC);

COMMENT ON TABLE incident_reports IS 'AI-generated incident reports metadata';

-- ============================================================================
-- CONTINUOUS AGGREGATES (Pre-computed metrics for ML features)
-- ============================================================================

-- 1-minute rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS event_metrics_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    service,
    COUNT(*) AS event_count,
    AVG((metadata->>'latency_ms')::numeric) AS avg_latency,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (metadata->>'latency_ms')::numeric) AS p95_latency,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY (metadata->>'latency_ms')::numeric) AS p99_latency,
    STDDEV((metadata->>'latency_ms')::numeric) AS latency_stddev,
    SUM(CASE WHEN level = 'ERROR' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS error_rate,
    SUM(CASE WHEN level = 'CRITICAL' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS critical_rate,
    COUNT(DISTINCT (metadata->>'endpoint')) AS unique_endpoints
FROM events
WHERE metadata ? 'latency_ms'
GROUP BY bucket, service;

-- Add refresh policy for 1-minute rollup
SELECT add_continuous_aggregate_policy(
    'event_metrics_1m',
    start_offset => INTERVAL '10 minutes',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

-- 5-minute rollup (for ML features)
CREATE MATERIALIZED VIEW IF NOT EXISTS event_metrics_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    service,
    COUNT(*) AS event_count,
    AVG((metadata->>'latency_ms')::numeric) AS avg_latency,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (metadata->>'latency_ms')::numeric) AS p95_latency,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY (metadata->>'latency_ms')::numeric) AS p99_latency,
    STDDEV((metadata->>'latency_ms')::numeric) AS latency_stddev,
    SUM(CASE WHEN level = 'ERROR' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS error_rate,
    SUM(CASE WHEN level = 'CRITICAL' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS critical_rate,
    COUNT(DISTINCT (metadata->>'endpoint')) AS unique_endpoints
FROM events
WHERE metadata ? 'latency_ms'
GROUP BY bucket, service;

-- Add refresh policy for 5-minute rollup
SELECT add_continuous_aggregate_policy(
    'event_metrics_5m',
    start_offset => INTERVAL '20 minutes',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- 1-hour rollup (for dashboards and historical analysis)
CREATE MATERIALIZED VIEW IF NOT EXISTS event_metrics_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    service,
    COUNT(*) AS event_count,
    AVG((metadata->>'latency_ms')::numeric) AS avg_latency,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (metadata->>'latency_ms')::numeric) AS p95_latency,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY (metadata->>'latency_ms')::numeric) AS p99_latency,
    STDDEV((metadata->>'latency_ms')::numeric) AS latency_stddev,
    SUM(CASE WHEN level = 'ERROR' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS error_rate,
    SUM(CASE WHEN level = 'CRITICAL' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS critical_rate,
    COUNT(DISTINCT (metadata->>'endpoint')) AS unique_endpoints
FROM events
WHERE metadata ? 'latency_ms'
GROUP BY bucket, service;

-- Add refresh policy for 1-hour rollup
SELECT add_continuous_aggregate_policy(
    'event_metrics_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ============================================================================
-- COMPRESSION POLICIES (Save storage space)
-- ============================================================================

-- Enable compression on events table
ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'service, level',
    timescaledb.compress_orderby = 'time DESC'
);

-- Add compression policy: compress chunks older than 7 days
SELECT add_compression_policy(
    'events',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Enable compression on anomalies table
ALTER TABLE anomalies SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'service, severity',
    timescaledb.compress_orderby = 'time DESC'
);

-- Compress anomalies older than 14 days
SELECT add_compression_policy(
    'anomalies',
    INTERVAL '14 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- RETENTION POLICIES (Auto-delete old data)
-- ============================================================================

-- Retain raw events for 30 days
SELECT add_retention_policy(
    'events',
    INTERVAL '30 days',
    if_not_exists => TRUE
);

-- Retain anomalies for 90 days
SELECT add_retention_policy(
    'anomalies',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- USEFUL QUERIES (For reference)
-- ============================================================================

-- Create a view for easy anomaly analysis
CREATE OR REPLACE VIEW anomaly_summary AS
SELECT
    service,
    severity,
    COUNT(*) AS total_anomalies,
    AVG(score) AS avg_score,
    MIN(time) AS first_occurrence,
    MAX(time) AS last_occurrence,
    SUM(CASE WHEN is_resolved THEN 1 ELSE 0 END) AS resolved_count,
    SUM(CASE WHEN NOT is_resolved THEN 1 ELSE 0 END) AS open_count
FROM anomalies
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY service, severity
ORDER BY total_anomalies DESC;

-- Create a view for recent high-severity anomalies
CREATE OR REPLACE VIEW recent_critical_anomalies AS
SELECT
    a.time,
    a.service,
    a.anomaly_id,
    a.score,
    a.severity,
    a.confidence,
    a.is_resolved,
    r.report_id,
    r.s3_location
FROM anomalies a
LEFT JOIN incident_reports r ON a.anomaly_id = r.anomaly_id
WHERE a.severity IN ('HIGH', 'CRITICAL')
    AND a.time > NOW() - INTERVAL '24 hours'
ORDER BY a.time DESC;

-- ============================================================================
-- SAMPLE DATA INSERTION (For testing)
-- ============================================================================

-- Insert sample events
INSERT INTO events (time, service, level, message, metadata) VALUES
(NOW(), 'payment-service', 'INFO', 'Payment processed successfully', '{"latency_ms": 150, "endpoint": "/checkout", "amount": 99.99}'::jsonb),
(NOW(), 'auth-service', 'INFO', 'User authenticated', '{"latency_ms": 45, "endpoint": "/login", "user_id": "user_123"}'::jsonb),
(NOW(), 'api-gateway', 'WARN', 'High latency detected', '{"latency_ms": 850, "endpoint": "/api/v1/users", "retries": 2}'::jsonb),
(NOW(), 'payment-service', 'ERROR', 'Database connection timeout', '{"latency_ms": 5000, "endpoint": "/checkout", "error_code": "DB_TIMEOUT"}'::jsonb);

-- Verify insertion
SELECT * FROM events ORDER BY time DESC LIMIT 5;

-- Check hypertable info
SELECT * FROM timescaledb_information.hypertables;

-- Check continuous aggregates
SELECT * FROM timescaledb_information.continuous_aggregates;

-- ============================================================================
-- GRANTS (For application users)
-- ============================================================================

-- Create application user (if needed)
-- CREATE USER helios_app WITH PASSWORD 'secure_password';

-- Grant necessary permissions
-- GRANT SELECT, INSERT, UPDATE ON events TO helios_app;
-- GRANT SELECT, INSERT, UPDATE ON anomalies TO helios_app;
-- GRANT SELECT, INSERT ON incident_reports TO helios_app;
-- GRANT SELECT ON event_metrics_1m, event_metrics_5m, event_metrics_1h TO helios_app;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
