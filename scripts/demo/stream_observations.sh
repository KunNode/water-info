#!/usr/bin/env bash
set -euo pipefail

# Insert demo observations continuously, once per minute by default.
# Usage:
#   scripts/demo/stream_observations.sh [interval_seconds]
#
# Default: 60 seconds between batches. Stop with Ctrl+C.

INTERVAL_SECONDS="${1:-60}"
DB_USER="${PGUSER:-root}"
DB_NAME="${PGDATABASE:-water_info}"

cd "$(dirname "$0")/../.."

BATCH=1
while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] inserting demo observation batch ${BATCH}"

  if ! docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" <<'SQL'
WITH metric_seed(station_code, metric_type, unit, base_value, amplitude, jitter, phase) AS (
  VALUES
    ('ST_RAIN_CP_01', 'RAINFALL',        'mm',    8.000,  6.000,  4.000, 0.0),
    ('ST_RAIN_CP_02', 'RAINFALL',        'mm',   10.000,  7.000,  4.500, 1.4),
    ('ST_WL_CP_01',   'WATER_LEVEL',     'm',     3.480,  0.260,  0.080, 2.0),
    ('ST_WL_CP_02',   'WATER_LEVEL',     'm',     3.160,  0.220,  0.070, 2.8),
    ('ST_FLOW_CP_01', 'FLOW',            'm3/s', 260.000, 45.000, 20.000, 3.5),
    ('ST_RES_CP_01',  'RESERVOIR_LEVEL', 'm',    39.420,  0.180,  0.050, 4.2),
    ('ST_GATE_CP_01', 'GATE_OPENING',    'm',     1.120,  0.280,  0.100, 5.1),
    ('ST_PUMP_CP_01', 'PUMP_POWER',      'kW',  145.000, 32.000, 15.000, 6.0)
),
generated AS (
  SELECT
    s.id AS station_id,
    m.station_code,
    m.metric_type,
    m.unit,
    round(
      greatest(
        0,
        m.base_value
          + m.amplitude * sin((extract(epoch FROM clock_timestamp() AT TIME ZONE 'Asia/Shanghai') / 60.0 + m.phase) / 7.0)
          + (random() - 0.5) * m.jitter
      )::numeric,
      3
    ) AS value,
    (clock_timestamp() AT TIME ZONE 'Asia/Shanghai') AS observed_at
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
  'DEMO_STREAM',
  'DEMO_STREAM_' || to_char(observed_at, 'YYYYMMDDHH24MISS') || '_' || station_code
FROM generated;

UPDATE sensor
SET status = 'ONLINE',
    last_seen_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE station_id IN (
  SELECT id FROM station
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
SQL
  then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] insert failed; retrying after ${INTERVAL_SECONDS}s" >&2
  fi

  sleep "$INTERVAL_SECONDS"
  ((BATCH += 1))
done
