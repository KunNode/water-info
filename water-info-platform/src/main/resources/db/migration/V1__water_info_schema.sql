-- Water Info Management Schema (PostgreSQL)
-- Requires: pgcrypto for gen_random_uuid()

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS water_info;
SET LOCAL search_path TO water_info, public;

-- Generic updated_at trigger
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Regions (hierarchy for admin/basin organization)
CREATE TABLE IF NOT EXISTS station_region (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(32) UNIQUE NOT NULL,
  name VARCHAR(128) NOT NULL,
  parent_id UUID NULL REFERENCES station_region(id) ON DELETE SET NULL,
  region_type VARCHAR(32) NULL DEFAULT 'ADMIN'
    CHECK (region_type IN ('ADMIN','BASIN','CUSTOM')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_station_region_set_updated_at ON station_region;
CREATE TRIGGER trg_station_region_set_updated_at
BEFORE UPDATE ON station_region
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Stations
CREATE TABLE IF NOT EXISTS station (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(128) NOT NULL,
  station_type VARCHAR(32) NOT NULL
    CHECK (station_type IN ('RIVER','RESERVOIR','GATE','RAIN')),
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive','maintenance')),
  latitude NUMERIC(10,7) NULL,
  longitude NUMERIC(10,7) NULL,
  address VARCHAR(255) NULL,
  region_id UUID NULL REFERENCES station_region(id),
  -- JSONB for type-specific attributes (reservoir capacity, gate count, etc.)
  station_profile JSONB NULL,
  -- Metadata for display/sorting
  sort_order INT NULL DEFAULT 0,
  description TEXT NULL,
  CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_station_set_updated_at ON station;
CREATE TRIGGER trg_station_set_updated_at
BEFORE UPDATE ON station
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Station contacts (responsible persons)
CREATE TABLE IF NOT EXISTS station_contact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES station(id) ON DELETE CASCADE,
  name VARCHAR(64) NOT NULL,
  role VARCHAR(32) NULL,
  phone VARCHAR(32) NULL,
  email VARCHAR(128) NULL,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sensor types (e.g., WATER_LEVEL_SENSOR, RAIN_GAUGE, DISCHARGE_SENSOR)
CREATE TABLE IF NOT EXISTS sensor_type (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(128) NOT NULL,
  description TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sensors (physical devices)
CREATE TABLE IF NOT EXISTS sensor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES station(id) ON DELETE CASCADE,
  sensor_type_id UUID NOT NULL REFERENCES sensor_type(id),
  code VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(128) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive','maintenance')),
  installed_at TIMESTAMPTZ NULL,
  removed_at TIMESTAMPTZ NULL,
  calibration_date TIMESTAMPTZ NULL,
  metadata JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_sensor_set_updated_at ON sensor;
CREATE TRIGGER trg_sensor_set_updated_at
BEFORE UPDATE ON sensor
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Units (e.g., m, mm, m3/s)
CREATE TABLE IF NOT EXISTS unit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(16) UNIQUE NOT NULL,
  name VARCHAR(64) NOT NULL,
  symbol VARCHAR(16) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Metrics (measurable quantities)
CREATE TABLE IF NOT EXISTS metric (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(32) UNIQUE NOT NULL,
  name VARCHAR(64) NOT NULL,
  unit_id UUID NOT NULL REFERENCES unit(id),
  value_type VARCHAR(16) NOT NULL DEFAULT 'number'
    CHECK (value_type IN ('number','integer')),
  precision SMALLINT NULL,
  -- Valid range for quality control
  valid_min NUMERIC(18,6) NULL,
  valid_max NUMERIC(18,6) NULL,
  -- Aggregation configuration
  aggregatable BOOLEAN NOT NULL DEFAULT TRUE,
  default_aggregation VARCHAR(16) NULL
    CHECK (default_aggregation IN ('sum','avg','max','min','last','count')),
  -- Description for UI/help
  description TEXT NULL,
  CHECK (valid_min IS NULL OR valid_max IS NULL OR valid_min <= valid_max),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_metric_set_updated_at ON metric;
CREATE TRIGGER trg_metric_set_updated_at
BEFORE UPDATE ON metric
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Ingestion sources (e.g., API partners, batch import systems)
CREATE TABLE IF NOT EXISTS ingest_source (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(128) NOT NULL,
  type VARCHAR(16) NOT NULL
    CHECK (type IN ('api','batch','manual','sensor')),
  -- Authentication/authorization config
  auth_type VARCHAR(32) NULL DEFAULT 'none'
    CHECK (auth_type IN ('none','api_key','oauth2','basic','signature')),
  credentials_encrypted TEXT NULL,
  -- Rate limiting
  rate_limit_per_minute INT NULL,
  -- Contact for this source
  contact_name VARCHAR(128) NULL,
  contact_phone VARCHAR(32) NULL,
  contact_email VARCHAR(128) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive','suspended')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_ingest_source_set_updated_at ON ingest_source;
CREATE TRIGGER trg_ingest_source_set_updated_at
BEFORE UPDATE ON ingest_source
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Observation batches (grouped ingestion for atomicity and traceability)
CREATE TABLE IF NOT EXISTS observation_batch (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES ingest_source(id),
  -- Idempotency support (unique key prevents duplicate processing)
  idempotency_key VARCHAR(128) NULL,
  source_request_id VARCHAR(128) NULL,
  payload_hash VARCHAR(128) NULL,
  -- Timing
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processing_started_at TIMESTAMPTZ NULL,
  processing_completed_at TIMESTAMPTZ NULL,
  -- Statistics
  record_count INT NOT NULL DEFAULT 0,
  accepted_count INT NOT NULL DEFAULT 0,
  rejected_count INT NOT NULL DEFAULT 0,
  -- Status
  status VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','processing','accepted','rejected','partial','failed')),
  -- Error aggregation
  error_summary JSONB NULL,
  -- Metadata
  source_ip VARCHAR(45) NULL,
  user_agent VARCHAR(512) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_observation_batch_set_updated_at ON observation_batch;
CREATE TRIGGER trg_observation_batch_set_updated_at
BEFORE UPDATE ON observation_batch
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Row-level ingestion results (for diagnostics, retry, and reporting)
CREATE TABLE IF NOT EXISTS observation_batch_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id UUID NOT NULL REFERENCES observation_batch(id) ON DELETE CASCADE,
  item_index INT NOT NULL,
  -- Original input values (as received)
  station_code VARCHAR(64) NOT NULL,
  metric_code VARCHAR(32) NOT NULL,
  observed_at TIMESTAMPTZ NULL,
  value NUMERIC(18,6) NULL,
  quality_code VARCHAR(32) NULL,
  sensor_code VARCHAR(64) NULL,
  -- Processing result
  status VARCHAR(16) NOT NULL
    CHECK (status IN ('accepted','rejected','skipped')),
  error_code VARCHAR(64) NULL,
  error_message TEXT NULL,
  -- Reference to resolved IDs (if accepted)
  station_id UUID NULL REFERENCES station(id),
  metric_id UUID NULL REFERENCES metric(id),
  sensor_id UUID NULL REFERENCES sensor(id),
  -- observation_id intentionally has no FK to avoid circular dependency during batch processing
  observation_id UUID NULL,
  -- Raw input for debugging
  raw_payload JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (batch_id, item_index)
);

-- Data quality states
CREATE TABLE IF NOT EXISTS data_quality (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(32) UNIQUE NOT NULL,
  name VARCHAR(64) NOT NULL,
  description TEXT NULL,
  severity VARCHAR(16) NULL DEFAULT 'info'
    CHECK (severity IN ('info','warning','error')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Observations (time series data)
CREATE TABLE IF NOT EXISTS observation (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES station(id),
  sensor_id UUID NULL REFERENCES sensor(id),
  metric_id UUID NOT NULL REFERENCES metric(id),
  -- Event time (when the phenomenon occurred)
  observed_at TIMESTAMPTZ NOT NULL,
  -- Value with precision from metric definition
  value NUMERIC(18,6) NOT NULL,
  quality_id UUID NOT NULL REFERENCES data_quality(id),
  -- Batch reference for traceability
  batch_id UUID NULL REFERENCES observation_batch(id),
  -- Ingest time (when the system received the data)
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Quality control metadata
  qc_flags JSONB NULL,
  -- Anomaly detection results (optional)
  anomaly_score NUMERIC(5,2) NULL,
  -- Audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Idempotency constraint
  UNIQUE (station_id, metric_id, observed_at)
);

-- Alert rules
CREATE TABLE IF NOT EXISTS alert_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(128) NOT NULL,
  description TEXT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive','draft')),
  severity VARCHAR(16) NOT NULL
    CHECK (severity IN ('info','yellow','orange','red')),
  -- Expression format: {operator: 'gte', metricCode: 'WATER_LEVEL', value: 10.5}
  expression_json JSONB NOT NULL,
  -- Time window for condition evaluation (e.g., 60 minutes)
  window_minutes INT NULL,
  -- Evaluation interval
  evaluation_interval_seconds INT NULL DEFAULT 300,
  -- Notification settings
  cooldown_minutes INT NULL DEFAULT 5,
  -- Scope (can be NULL for global rules)
  is_global BOOLEAN NOT NULL DEFAULT FALSE,
  created_by VARCHAR(128) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_alert_rule_set_updated_at ON alert_rule;
CREATE TRIGGER trg_alert_rule_set_updated_at
BEFORE UPDATE ON alert_rule
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Alert rule scopes (which stations/metrics the rule applies to)
CREATE TABLE IF NOT EXISTS alert_rule_scope (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id UUID NOT NULL REFERENCES alert_rule(id) ON DELETE CASCADE,
  -- At least one of station_id or metric_id must be non-NULL
  station_id UUID NULL REFERENCES station(id),
  metric_id UUID NULL REFERENCES metric(id),
  CHECK (station_id IS NOT NULL OR metric_id IS NOT NULL),
  priority INT NULL DEFAULT 0,
  UNIQUE (rule_id, station_id, metric_id)
);

-- Alert rule actions (notification channels)
CREATE TABLE IF NOT EXISTS alert_rule_action (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id UUID NOT NULL REFERENCES alert_rule(id) ON DELETE CASCADE,
  type VARCHAR(32) NOT NULL
    CHECK (type IN ('sms','email','webhook','dingtalk','wechat','custom')),
  target VARCHAR(512) NOT NULL,
  payload_template JSONB NULL,
  -- Retry settings
  max_retries INT NULL DEFAULT 3,
  retry_interval_seconds INT NULL DEFAULT 60,
  -- Enable/disable per action
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_alert_rule_action_set_updated_at ON alert_rule_action;
CREATE TRIGGER trg_alert_rule_action_set_updated_at
BEFORE UPDATE ON alert_rule_action
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Alert events (instances of triggered alerts)
CREATE TABLE IF NOT EXISTS alert_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id UUID NOT NULL REFERENCES alert_rule(id),
  -- Copied from rule for historical accuracy
  rule_code VARCHAR(64) NOT NULL,
  rule_name VARCHAR(128) NOT NULL,
  station_id UUID NOT NULL REFERENCES station(id),
  metric_id UUID NOT NULL REFERENCES metric(id),
  observed_at TIMESTAMPTZ NOT NULL,
  value NUMERIC(18,6) NOT NULL,
  severity VARCHAR(16) NOT NULL
    CHECK (severity IN ('info','yellow','orange','red')),
  status VARCHAR(16) NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','acknowledged','closed','expired')),
  -- Lifecycle tracking
  acknowledged_at TIMESTAMPTZ NULL,
  acknowledged_by VARCHAR(128) NULL,
  closed_at TIMESTAMPTZ NULL,
  closed_by VARCHAR(128) NULL,
  close_reason VARCHAR(256) NULL,
  -- Context
  message TEXT NULL,
  context_json JSONB NULL,
  -- Deduplication
  fingerprint VARCHAR(128) NULL,
  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_alert_event_set_updated_at ON alert_event;
CREATE TRIGGER trg_alert_event_set_updated_at
BEFORE UPDATE ON alert_event
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Alert event to observation linkage (for evidence/tracing)
CREATE TABLE IF NOT EXISTS alert_event_observation (
  event_id UUID NOT NULL REFERENCES alert_event(id) ON DELETE CASCADE,
  observation_id UUID NOT NULL REFERENCES observation(id) ON DELETE CASCADE,
  PRIMARY KEY (event_id, observation_id)
);

-- Alert notifications (delivery attempts)
CREATE TABLE IF NOT EXISTS alert_notification (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES alert_event(id) ON DELETE CASCADE,
  action_id UUID NOT NULL REFERENCES alert_rule_action(id),
  -- Delivery status
  status VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','sending','sent','failed','skipped')),
  -- Attempt tracking
  attempt_count INT NOT NULL DEFAULT 0,
  last_attempt_at TIMESTAMPTZ NULL,
  next_retry_at TIMESTAMPTZ NULL,
  -- Response
  sent_at TIMESTAMPTZ NULL,
  response_code INT NULL,
  response_body TEXT NULL,
  error TEXT NULL,
  -- Payload sent
  payload_sent JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_alert_notification_set_updated_at ON alert_notification;
CREATE TRIGGER trg_alert_notification_set_updated_at
BEFORE UPDATE ON alert_notification
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- INDEXES
-- ============================================================

-- Foreign key indexes (PostgreSQL does not auto-create)
CREATE INDEX IF NOT EXISTS idx_station_region_id ON station (region_id);
CREATE INDEX IF NOT EXISTS idx_station_type ON station (station_type);
CREATE INDEX IF NOT EXISTS idx_station_status ON station (status);
CREATE INDEX IF NOT EXISTS idx_station_contact_station_id ON station_contact (station_id);
CREATE INDEX IF NOT EXISTS idx_sensor_station_id ON sensor (station_id);
CREATE INDEX IF NOT EXISTS idx_sensor_sensor_type_id ON sensor (sensor_type_id);
CREATE INDEX IF NOT EXISTS idx_sensor_status ON sensor (status);
CREATE INDEX IF NOT EXISTS idx_metric_unit_id ON metric (unit_id);
CREATE INDEX IF NOT EXISTS idx_ingest_source_status ON ingest_source (status);
CREATE INDEX IF NOT EXISTS idx_ingest_source_type ON ingest_source (type);
CREATE INDEX IF NOT EXISTS idx_observation_batch_source_id ON observation_batch (source_id);
CREATE INDEX IF NOT EXISTS idx_observation_batch_status ON observation_batch (status);
CREATE INDEX IF NOT EXISTS idx_observation_batch_received_at ON observation_batch (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_item_batch_id ON observation_batch_item (batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_item_station_code ON observation_batch_item (station_code);
CREATE INDEX IF NOT EXISTS idx_batch_item_metric_code ON observation_batch_item (metric_code);
CREATE INDEX IF NOT EXISTS idx_batch_item_status ON observation_batch_item (status);
CREATE INDEX IF NOT EXISTS idx_observation_batch_id ON observation (batch_id);
CREATE INDEX IF NOT EXISTS idx_observation_sensor_id ON observation (sensor_id);
CREATE INDEX IF NOT EXISTS idx_observation_metric_id ON observation (metric_id);
CREATE INDEX IF NOT EXISTS idx_observation_quality_id ON observation (quality_id);
CREATE INDEX IF NOT EXISTS idx_alert_rule_status ON alert_rule (status);
CREATE INDEX IF NOT EXISTS idx_alert_rule_scope_rule_id ON alert_rule_scope (rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_rule_scope_station_id ON alert_rule_scope (station_id);
CREATE INDEX IF NOT EXISTS idx_alert_rule_scope_metric_id ON alert_rule_scope (metric_id);
CREATE INDEX IF NOT EXISTS idx_alert_rule_action_rule_id ON alert_rule_action (rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_rule_action_type ON alert_rule_action (type);
CREATE INDEX IF NOT EXISTS idx_alert_event_rule_id ON alert_event (rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_event_station_id ON alert_event (station_id);
CREATE INDEX IF NOT EXISTS idx_alert_event_metric_id ON alert_event (metric_id);
CREATE INDEX IF NOT EXISTS idx_alert_event_status ON alert_event (status);
CREATE INDEX IF NOT EXISTS idx_alert_event_severity ON alert_event (severity);
CREATE INDEX IF NOT EXISTS idx_alert_notification_event_id ON alert_notification (event_id);
CREATE INDEX IF NOT EXISTS idx_alert_notification_action_id ON alert_notification (action_id);
CREATE INDEX IF NOT EXISTS idx_alert_notification_status ON alert_notification (status);

-- Query-focused indexes (high-frequency patterns)
CREATE INDEX IF NOT EXISTS idx_observation_station_metric_time
  ON observation (station_id, metric_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_observation_time
  ON observation (observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_observation_station_time
  ON observation (station_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_observation_metric_time
  ON observation (metric_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_observation_station_metric_observed
  ON observation (station_id, metric_id, observed_at DESC)
  INCLUDE (value, quality_id);

CREATE INDEX IF NOT EXISTS idx_alert_event_station_metric_observed_time
  ON alert_event (station_id, metric_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_event_created_at
  ON alert_event (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_event_open
  ON alert_event (status, created_at DESC)
  WHERE status IN ('open', 'acknowledged');

CREATE INDEX IF NOT EXISTS idx_alert_rule_scope_station_metric
  ON alert_rule_scope (station_id, metric_id);

-- Fill the uniqueness gap when one side of scope is NULL.
CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_rule_scope_rule_station_when_metric_null
  ON alert_rule_scope (rule_id, station_id)
  WHERE metric_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_rule_scope_rule_metric_when_station_null
  ON alert_rule_scope (rule_id, metric_id)
  WHERE station_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_batch_item_lookup
  ON observation_batch_item (batch_id, station_code, metric_code);

-- Unique index for idempotency_key (excluding NULL values)
CREATE UNIQUE INDEX IF NOT EXISTS idx_observation_batch_idempotency
  ON observation_batch (idempotency_key)
  WHERE idempotency_key IS NOT NULL;

-- ============================================================
-- COMMENTS (Documentation)
-- ============================================================

COMMENT ON TABLE observation IS 'Time series observations. Primary time axis is observed_at (event time). ingested_at tracks when data arrived in the system.';
COMMENT ON COLUMN observation.observed_at IS 'When the phenomenon occurred (event time)';
COMMENT ON COLUMN observation.ingested_at IS 'When the system received this observation';
COMMENT ON COLUMN observation.qc_flags IS 'Quality control flags: {range: boolean, spike: boolean, missing: boolean}';
COMMENT ON COLUMN observation.anomaly_score IS 'Optional ML-based anomaly score (0-100)';

COMMENT ON TABLE observation_batch IS 'Atomic group of observations for idempotency and transaction support';
COMMENT ON COLUMN observation_batch.idempotency_key IS 'Client-provided idempotency key to prevent duplicate processing';
COMMENT ON COLUMN observation_batch.payload_hash IS 'SHA-256 hash of the original payload for integrity verification';

COMMENT ON TABLE observation_batch_item IS 'Per-row ingestion results for debugging, retry, and reporting';
COMMENT ON COLUMN observation_batch_item.status IS 'accepted: stored in observation; rejected: error; skipped: skipped by rule';

COMMENT ON TABLE alert_rule IS 'Alert rules use JSONB expressions. Example: {"operator": "gte", "metricCode": "WATER_LEVEL", "value": 10.5, "windowMinutes": 60}';
COMMENT ON COLUMN alert_rule.expression_json IS 'Rule evaluation expression in JSON format';
COMMENT ON COLUMN alert_rule.window_minutes IS 'Time window for condition evaluation (e.g., alert if value exceeds threshold for N minutes)';

COMMENT ON COLUMN alert_event.fingerprint IS 'Hash for deduplication: prevents duplicate alerts for same condition within cooldown';

-- ============================================================
-- SEED DATA (Optional)
-- ============================================================

-- INSERT INTO unit (code, name, symbol) VALUES
--   ('m', 'Meter', 'm'),
--   ('mm', 'Millimeter', 'mm'),
--   ('m3s', 'Cubic meter per second', 'm鲁/s'),
--   ('m3', 'Cubic meter', 'm鲁'),
--   ('km', 'Kilometer', 'km'),
--   ('deg_c', 'Degree Celsius', '掳C'),
--   ('percent', 'Percent', '%');
--
-- INSERT INTO metric (code, name, unit_id, value_type, precision, aggregatable, default_aggregation)
-- SELECT 'WATER_LEVEL', 'Water Level', id, 'number', 3, TRUE, 'avg' FROM unit WHERE code='m';
-- SELECT 'RAIN_1H', 'Rainfall (1 Hour)', id, 'number', 2, TRUE, 'sum' FROM unit WHERE code='mm';
-- SELECT 'RAIN_24H', 'Rainfall (24 Hours)', id, 'number', 2, TRUE, 'sum' FROM unit WHERE code='mm';
-- SELECT 'DISCHARGE', 'Discharge', id, 'number', 3, TRUE, 'avg' FROM unit WHERE code='m3s';
-- SELECT 'INFLOW', 'Inflow', id, 'number', 3, TRUE, 'avg' FROM unit WHERE code='m3s';
-- SELECT 'OUTFLOW', 'Outflow', id, 'number', 3, TRUE, 'avg' FROM unit WHERE code='m3s';
-- SELECT 'STORAGE', 'Reservoir Storage', id, 'number', 4, TRUE, 'last' FROM unit WHERE code='m3';
-- SELECT 'GATE_OPENING', 'Gate Opening', id, 'number', 2, TRUE, 'last' FROM unit WHERE code='m';
--
-- INSERT INTO data_quality (code, name, description, severity) VALUES
--   ('raw', 'Raw', 'Newly ingested, not yet validated', 'info'),
--   ('validated', 'Validated', 'Passed quality control checks', 'info'),
--   ('suspect', 'Suspect', 'Failed quality control, needs review', 'warning'),
--   ('missing', 'Missing', 'Data gap detected', 'warning'),
--   ('interpolated', 'Interpolated', 'Filled by interpolation', 'info'),
--   ('corrected', 'Corrected', 'Manually corrected', 'info');

COMMIT;



