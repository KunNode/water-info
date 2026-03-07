
-- Database Indexes for Performance Optimization
-- V5__performance_indexes.sql

-- ─── Observation Table Indexes ───
-- Index for querying observations by station and time (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_observations_station_time
    ON observation(station_id, observed_at DESC);

-- Index for metric type filtering with time
CREATE INDEX IF NOT EXISTS idx_observations_metric_time
    ON observation(metric_type, observed_at DESC);

-- Composite index for batch queries
CREATE INDEX IF NOT EXISTS idx_observations_station_metric
    ON observation(station_id, metric_type, observed_at DESC);

-- ─── Alarm Table Indexes ───
-- Index for querying alarms by status and level
CREATE INDEX IF NOT EXISTS idx_alarms_status_level
    ON alarm(status, level, start_at DESC);

-- Index for active alarms
CREATE INDEX IF NOT EXISTS idx_alarms_active
    ON alarm(status, last_trigger_at DESC) WHERE status IN ('OPEN', 'ACK');

-- Index for station-specific alarms
CREATE INDEX IF NOT EXISTS idx_alarms_station_status
    ON alarm(station_id, status, last_trigger_at DESC);

-- ─── Station Table Indexes ───
-- Index for station code (unique lookup)
CREATE INDEX IF NOT EXISTS idx_stations_code
    ON station(code);

-- Index for station type filtering
CREATE INDEX IF NOT EXISTS idx_stations_type
    ON station(type, status);

-- Index for region-based queries
CREATE INDEX IF NOT EXISTS idx_stations_region
    ON station(admin_region, river_basin);

-- ─── Sensor Table Indexes ───
-- Index for station-sensor relationship
CREATE INDEX IF NOT EXISTS idx_sensors_station
    ON sensor(station_id, status);

-- Index for sensor status queries
CREATE INDEX IF NOT EXISTS idx_sensors_status
    ON sensor(status, last_seen_at DESC);

-- ─── Threshold Rules Table Indexes ───
-- Index for station-threshold lookup
CREATE INDEX IF NOT EXISTS idx_threshold_station_metric
    ON threshold_rule(station_id, metric_type, enabled);

-- Index for enabled rules
CREATE INDEX IF NOT EXISTS idx_threshold_enabled
    ON threshold_rule(enabled, level) WHERE enabled = true;

-- ─── Audit Log Indexes ───
-- Index for audit log by user and time
CREATE INDEX IF NOT EXISTS idx_audit_user_time
    ON sys_audit_log(actor_user_id, created_at DESC);

-- Index for audit log by action type
CREATE INDEX IF NOT EXISTS idx_audit_operation
    ON sys_audit_log(action, created_at DESC);

-- ─── User Table Indexes ───
-- Index for username lookup
CREATE INDEX IF NOT EXISTS idx_users_username
    ON sys_user(username) WHERE deleted = 0;

-- Index for user organization
CREATE INDEX IF NOT EXISTS idx_users_org
    ON sys_user(org_id, dept_id) WHERE deleted = 0;
