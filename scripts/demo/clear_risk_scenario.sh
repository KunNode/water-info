#!/usr/bin/env bash
set -euo pipefail

# Clear demo risk data and restore one normal observation batch.
# Usage:
#   scripts/demo/clear_risk_scenario.sh

DB_USER="${PGUSER:-root}"
DB_NAME="${PGDATABASE:-water_info}"

cd "$(dirname "$0")/../.."

echo "[$(date '+%Y-%m-%d %H:%M:%S')] clearing demo risk scenario"

docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" <<'SQL'
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND table_name = 'alarm'
      AND column_name = 'source_tag'
  ) THEN
    EXECUTE $sql$
      UPDATE alarm
      SET status = 'CLOSED',
          end_at = CURRENT_TIMESTAMP,
          last_trigger_at = CURRENT_TIMESTAMP,
          closed_at = CURRENT_TIMESTAMP,
          updated_at = CURRENT_TIMESTAMP
      WHERE status IN ('OPEN', 'ACK')
        AND (message LIKE '[DEMO_RISK]%' OR source_tag = 'DEMO_RISK')
    $sql$;
  ELSE
    UPDATE alarm
    SET status = 'CLOSED',
        end_at = CURRENT_TIMESTAMP,
        last_trigger_at = CURRENT_TIMESTAMP,
        closed_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE status IN ('OPEN', 'ACK')
      AND message LIKE '[DEMO_RISK]%';
  END IF;
END $$;

DELETE FROM observation
WHERE source = 'DEMO_RISK'
   OR request_id LIKE 'DEMO_RISK_%';

WITH metric_seed(station_code, metric_type, unit, value) AS (
  VALUES
    ('ST_RAIN_CP_01', 'RAINFALL',        'mm',     6.0),
    ('ST_RAIN_CP_02', 'RAINFALL',        'mm',     7.5),
    ('ST_WL_CP_01',   'WATER_LEVEL',     'm',      3.42),
    ('ST_WL_CP_02',   'WATER_LEVEL',     'm',      3.05),
    ('ST_FLOW_CP_01', 'FLOW',            'm3/s', 245.0),
    ('ST_RES_CP_01',  'RESERVOIR_LEVEL', 'm',     39.35),
    ('ST_GATE_CP_01', 'GATE_OPENING',    'm',      1.05),
    ('ST_PUMP_CP_01', 'PUMP_POWER',      'kW',   135.0)
),
generated AS (
  SELECT
    s.id AS station_id,
    m.station_code,
    m.metric_type,
    m.unit,
    m.value::numeric AS value,
    clock_timestamp() AS observed_at
  FROM metric_seed m
  JOIN station s ON s.code = m.station_code
)
INSERT INTO observation (
  station_id,
  metric_type,
  value,
  unit,
  observed_at,
  quality_flag,
  source,
  request_id
)
SELECT
  station_id,
  metric_type,
  value,
  unit,
  observed_at,
  'GOOD',
  'DEMO_RECOVERY',
  'DEMO_RECOVERY_' || to_char(observed_at, 'YYYYMMDDHH24MISS') || '_' || station_code
FROM generated;

UPDATE sensor
SET status = 'ONLINE',
    last_seen_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE station_id IN (
  SELECT id
  FROM station
  WHERE code IN (
    'ST_RAIN_CP_01',
    'ST_RAIN_CP_02',
    'ST_WL_CP_01',
    'ST_WL_CP_02',
    'ST_FLOW_CP_01',
    'ST_RES_CP_01',
    'ST_GATE_CP_01',
    'ST_PUMP_CP_01'
  )
);

SELECT
  (
    SELECT count(*)
    FROM alarm
    WHERE status IN ('OPEN', 'ACK')
      AND message LIKE '[DEMO_RISK]%'
  ) AS remaining_demo_alarms,
  (
    SELECT count(*)
    FROM observation
    WHERE source = 'DEMO_RISK'
       OR request_id LIKE 'DEMO_RISK_%'
  ) AS remaining_demo_observations;
SQL

echo "[$(date '+%Y-%m-%d %H:%M:%S')] demo risk scenario cleared; normal recovery observations inserted"
