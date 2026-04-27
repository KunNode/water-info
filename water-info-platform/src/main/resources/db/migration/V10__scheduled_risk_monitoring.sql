-- Scheduled risk monitoring and AI assessment persistence

ALTER TABLE alarm
    ADD COLUMN IF NOT EXISTS source_tag VARCHAR(32) NOT NULL DEFAULT 'MANUAL';

CREATE UNIQUE INDEX IF NOT EXISTS ux_alarm_open_station_metric_level
    ON alarm(station_id, metric_type, level)
    WHERE status = 'OPEN';

CREATE TABLE IF NOT EXISTS ai_assessment (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    station_id VARCHAR(36) NOT NULL,
    metric_type VARCHAR(32),
    level VARCHAR(16) NOT NULL,
    summary TEXT NOT NULL,
    plan_excerpt TEXT,
    source VARCHAR(16) NOT NULL CHECK (source IN ('PERIODIC', 'EVENT')),
    assessed_at TIMESTAMP NOT NULL,
    assessed_at_minute TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_assessment_station FOREIGN KEY (station_id) REFERENCES station(id) ON DELETE CASCADE,
    CONSTRAINT ux_ai_assessment_station_source_minute UNIQUE (station_id, source, assessed_at_minute)
);

CREATE INDEX IF NOT EXISTS idx_ai_assessment_station_time
    ON ai_assessment(station_id, assessed_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_assessment_time
    ON ai_assessment(assessed_at DESC);
