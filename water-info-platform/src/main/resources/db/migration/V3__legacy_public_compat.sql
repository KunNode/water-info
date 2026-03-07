-- Compatibility migration for existing Java entities/mappers that use legacy public tables.
-- This keeps current water_info schema intact while ensuring runtime table names exist.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- Legacy user/access tables in public schema
-- ============================================================

CREATE TABLE IF NOT EXISTS sys_org (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(128) NOT NULL,
    code VARCHAR(64) NOT NULL UNIQUE,
    region VARCHAR(128),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sys_dept (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    org_id VARCHAR(36) NOT NULL,
    name VARCHAR(128) NOT NULL,
    parent_id VARCHAR(36),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dept_org FOREIGN KEY (org_id) REFERENCES sys_org(id) ON DELETE CASCADE,
    CONSTRAINT fk_dept_parent FOREIGN KEY (parent_id) REFERENCES sys_dept(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sys_user (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    real_name VARCHAR(64),
    phone VARCHAR(32),
    email VARCHAR(128),
    org_id VARCHAR(36),
    dept_id VARCHAR(36),
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DISABLED', 'LOCKED')),
    last_login_at TIMESTAMP,
    password_updated_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_user_org FOREIGN KEY (org_id) REFERENCES sys_org(id) ON DELETE SET NULL,
    CONSTRAINT fk_user_dept FOREIGN KEY (dept_id) REFERENCES sys_dept(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sys_role (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    code VARCHAR(32) NOT NULL UNIQUE CHECK (code IN ('ADMIN', 'OPERATOR', 'VIEWER')),
    name VARCHAR(64) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sys_user_role (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id VARCHAR(36) NOT NULL,
    role_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES sys_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES sys_role(id) ON DELETE CASCADE,
    CONSTRAINT uk_user_role UNIQUE (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS sys_audit_log (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    actor_user_id VARCHAR(36),
    actor_username VARCHAR(64),
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(64),
    target_id VARCHAR(36),
    detail JSONB,
    ip VARCHAR(64),
    user_agent VARCHAR(512),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (actor_user_id) REFERENCES sys_user(id) ON DELETE SET NULL
);

-- ============================================================
-- Legacy water-domain tables in public schema
-- ============================================================

CREATE TABLE IF NOT EXISTS station (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    type VARCHAR(32) NOT NULL CHECK (type IN ('RAIN_GAUGE', 'WATER_LEVEL', 'FLOW', 'RESERVOIR', 'GATE', 'PUMP_STATION', 'OTHER')),
    river_basin VARCHAR(128),
    admin_region VARCHAR(128),
    lat DECIMAL(10, 7),
    lon DECIMAL(10, 7),
    elevation DECIMAL(10, 2),
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensor (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    station_id VARCHAR(36) NOT NULL,
    type VARCHAR(32) NOT NULL,
    unit VARCHAR(32),
    sampling_interval_sec INTEGER DEFAULT 300,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')),
    last_seen_at TIMESTAMP,
    meta JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sensor_station FOREIGN KEY (station_id) REFERENCES station(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS observation (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    station_id VARCHAR(36) NOT NULL,
    metric_type VARCHAR(32) NOT NULL CHECK (metric_type IN ('RAINFALL', 'WATER_LEVEL', 'FLOW', 'RESERVOIR_LEVEL', 'GATE_OPENING', 'PUMP_POWER')),
    value DECIMAL(18, 6) NOT NULL,
    unit VARCHAR(32),
    observed_at TIMESTAMP NOT NULL,
    quality_flag VARCHAR(16) NOT NULL DEFAULT 'GOOD' CHECK (quality_flag IN ('GOOD', 'BAD', 'SUSPECT', 'MISSING')),
    source VARCHAR(64),
    request_id VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_obs_station FOREIGN KEY (station_id) REFERENCES station(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS threshold_rule (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    station_id VARCHAR(36) NOT NULL,
    metric_type VARCHAR(32) NOT NULL CHECK (metric_type IN ('RAINFALL', 'WATER_LEVEL', 'FLOW', 'RESERVOIR_LEVEL', 'GATE_OPENING', 'PUMP_POWER')),
    level VARCHAR(16) NOT NULL CHECK (level IN ('INFO', 'WARNING', 'CRITICAL')),
    threshold_value DECIMAL(18, 6) NOT NULL,
    duration_min INTEGER,
    rate_threshold DECIMAL(18, 6),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rule_station FOREIGN KEY (station_id) REFERENCES station(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alarm (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    station_id VARCHAR(36) NOT NULL,
    metric_type VARCHAR(32) NOT NULL CHECK (metric_type IN ('RAINFALL', 'WATER_LEVEL', 'FLOW', 'RESERVOIR_LEVEL', 'GATE_OPENING', 'PUMP_POWER')),
    level VARCHAR(16) NOT NULL CHECK (level IN ('INFO', 'WARNING', 'CRITICAL')),
    start_at TIMESTAMP NOT NULL,
    last_trigger_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP,
    status VARCHAR(16) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACK', 'CLOSED')),
    message TEXT,
    acknowledged_by VARCHAR(36),
    acknowledged_at TIMESTAMP,
    closed_by VARCHAR(36),
    closed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alarm_station FOREIGN KEY (station_id) REFERENCES station(id) ON DELETE CASCADE,
    CONSTRAINT fk_alarm_ack_user FOREIGN KEY (acknowledged_by) REFERENCES sys_user(id) ON DELETE SET NULL,
    CONSTRAINT fk_alarm_close_user FOREIGN KEY (closed_by) REFERENCES sys_user(id) ON DELETE SET NULL
);

-- ============================================================
-- Legacy indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_user_status ON sys_user(status);
CREATE INDEX IF NOT EXISTS idx_user_org ON sys_user(org_id);
CREATE INDEX IF NOT EXISTS idx_user_dept ON sys_user(dept_id);
CREATE INDEX IF NOT EXISTS idx_dept_org ON sys_dept(org_id);
CREATE INDEX IF NOT EXISTS idx_dept_parent ON sys_dept(parent_id);
CREATE INDEX IF NOT EXISTS idx_user_role_user ON sys_user_role(user_id);
CREATE INDEX IF NOT EXISTS idx_user_role_role ON sys_user_role(role_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON sys_audit_log(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON sys_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_time ON sys_audit_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_station_type ON station(type);
CREATE INDEX IF NOT EXISTS idx_station_status ON station(status);
CREATE INDEX IF NOT EXISTS idx_station_region ON station(admin_region);

CREATE INDEX IF NOT EXISTS idx_sensor_station ON sensor(station_id);
CREATE INDEX IF NOT EXISTS idx_sensor_type ON sensor(type);
CREATE INDEX IF NOT EXISTS idx_sensor_status ON sensor(status);

CREATE INDEX IF NOT EXISTS idx_obs_station_metric_time ON observation(station_id, metric_type, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_obs_time ON observation(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_obs_request ON observation(request_id) WHERE request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rule_station_metric_enabled ON threshold_rule(station_id, metric_type, enabled);

CREATE INDEX IF NOT EXISTS idx_alarm_status_level_time ON alarm(status, level, last_trigger_at DESC);
CREATE INDEX IF NOT EXISTS idx_alarm_station ON alarm(station_id);
CREATE INDEX IF NOT EXISTS idx_alarm_status ON alarm(status);

-- ============================================================
-- Legacy updated_at triggers
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_sys_org_updated_at ON sys_org;
CREATE TRIGGER update_sys_org_updated_at BEFORE UPDATE ON sys_org FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sys_dept_updated_at ON sys_dept;
CREATE TRIGGER update_sys_dept_updated_at BEFORE UPDATE ON sys_dept FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sys_user_updated_at ON sys_user;
CREATE TRIGGER update_sys_user_updated_at BEFORE UPDATE ON sys_user FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sys_role_updated_at ON sys_role;
CREATE TRIGGER update_sys_role_updated_at BEFORE UPDATE ON sys_role FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_station_updated_at ON station;
CREATE TRIGGER update_station_updated_at BEFORE UPDATE ON station FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sensor_updated_at ON sensor;
CREATE TRIGGER update_sensor_updated_at BEFORE UPDATE ON sensor FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_threshold_rule_updated_at ON threshold_rule;
CREATE TRIGGER update_threshold_rule_updated_at BEFORE UPDATE ON threshold_rule FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_alarm_updated_at ON alarm;
CREATE TRIGGER update_alarm_updated_at BEFORE UPDATE ON alarm FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Legacy seed data
-- ============================================================

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'ADMIN', 'Administrator', 'Full system access'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'ADMIN');

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'OPERATOR', 'Operator', 'Can manage data, alarms, and resources'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'OPERATOR');

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'VIEWER', 'Viewer', 'Read-only access'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'VIEWER');

INSERT INTO sys_org (id, code, name, region)
SELECT gen_random_uuid()::text, 'DEFAULT_ORG', 'Default Organization', 'Default Region'
WHERE NOT EXISTS (SELECT 1 FROM sys_org WHERE code = 'DEFAULT_ORG');

COMMIT;
