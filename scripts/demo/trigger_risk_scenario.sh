#!/usr/bin/env bash
set -euo pipefail

# Inject a controlled demo risk scenario.
# Usage:
#   scripts/demo/trigger_risk_scenario.sh [warning|high|critical]
#
# Default: critical

SCENARIO="${1:-critical}"
DB_USER="${PGUSER:-root}"
DB_NAME="${PGDATABASE:-water_info}"

case "$SCENARIO" in
  warning)
    SCENARIO_RANK=1
    RAIN_CP01=32.0
    RAIN_CP02=34.0
    WL_CP01=3.82
    WL_CP02=3.42
    FLOW_CP01=360.0
    RES_CP01=39.90
    GATE_CP01=1.70
    PUMP_CP01=195.0
    ;;
  high)
    SCENARIO_RANK=2
    RAIN_CP01=48.0
    RAIN_CP02=52.0
    WL_CP01=4.32
    WL_CP02=3.88
    FLOW_CP01=510.0
    RES_CP01=40.70
    GATE_CP01=2.10
    PUMP_CP01=245.0
    ;;
  critical)
    SCENARIO_RANK=3
    RAIN_CP01=68.0
    RAIN_CP02=76.0
    WL_CP01=4.78
    WL_CP02=4.18
    FLOW_CP01=575.0
    RES_CP01=41.18
    GATE_CP01=2.65
    PUMP_CP01=285.0
    ;;
  *)
    echo "Unknown scenario: ${SCENARIO}. Use warning, high, or critical." >&2
    exit 2
    ;;
esac

cd "$(dirname "$0")/../.."

echo "[$(date '+%Y-%m-%d %H:%M:%S')] injecting ${SCENARIO} demo risk scenario"

docker compose exec -T postgres psql \
  -v ON_ERROR_STOP=1 \
  -v scenario="$SCENARIO" \
  -v scenario_rank="$SCENARIO_RANK" \
  -v rain_cp01="$RAIN_CP01" \
  -v rain_cp02="$RAIN_CP02" \
  -v wl_cp01="$WL_CP01" \
  -v wl_cp02="$WL_CP02" \
  -v flow_cp01="$FLOW_CP01" \
  -v res_cp01="$RES_CP01" \
  -v gate_cp01="$GATE_CP01" \
  -v pump_cp01="$PUMP_CP01" \
  -U "$DB_USER" \
  -d "$DB_NAME" <<'SQL'
DO $$
DECLARE
  expected_count integer;
BEGIN
  SELECT count(*) INTO expected_count
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
  );

  IF expected_count < 8 THEN
    RAISE EXCEPTION 'Expected 8 Cuiping demo stations, found %. Load station baseline/demo seed first.', expected_count;
  END IF;
END $$;

WITH threshold_seed(station_code, metric_type, warning_value, critical_value, warning_duration, critical_duration) AS (
  VALUES
    ('ST_RAIN_CP_01', 'RAINFALL',        25.000, 45.000, 60, 30),
    ('ST_RAIN_CP_02', 'RAINFALL',        30.000, 50.000, 60, 30),
    ('ST_WL_CP_01',   'WATER_LEVEL',      3.600,  4.150, 15, 10),
    ('ST_WL_CP_02',   'WATER_LEVEL',      3.250,  3.800, 15, 10),
    ('ST_FLOW_CP_01', 'FLOW',           320.000, 480.000, 20, 15),
    ('ST_RES_CP_01',  'RESERVOIR_LEVEL', 39.600, 41.000, 30, 20),
    ('ST_GATE_CP_01', 'GATE_OPENING',     1.500,  2.400, 10, 10),
    ('ST_PUMP_CP_01', 'PUMP_POWER',     180.000, 260.000, 20, 15)
),
desired_thresholds AS (
  SELECT s.id AS station_id, t.metric_type, 'WARNING' AS level,
         t.warning_value AS threshold_value, t.warning_duration AS duration_min
  FROM threshold_seed t
  JOIN station s ON s.code = t.station_code
  UNION ALL
  SELECT s.id AS station_id, t.metric_type, 'CRITICAL' AS level,
         t.critical_value AS threshold_value, t.critical_duration AS duration_min
  FROM threshold_seed t
  JOIN station s ON s.code = t.station_code
),
updated AS (
  UPDATE threshold_rule tr
  SET threshold_value = d.threshold_value,
      duration_min = d.duration_min,
      enabled = TRUE,
      updated_at = CURRENT_TIMESTAMP
  FROM desired_thresholds d
  WHERE tr.station_id = d.station_id
    AND tr.metric_type = d.metric_type
    AND tr.level = d.level
  RETURNING tr.station_id, tr.metric_type, tr.level
)
INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value, duration_min,
  rate_threshold, enabled, created_at, updated_at
)
SELECT gen_random_uuid()::text, d.station_id, d.metric_type, d.level,
       d.threshold_value, d.duration_min, NULL::numeric, TRUE,
       CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM desired_thresholds d
WHERE NOT EXISTS (
  SELECT 1
  FROM threshold_rule tr
  WHERE tr.station_id = d.station_id
    AND tr.metric_type = d.metric_type
    AND tr.level = d.level
);

WITH metric_seed(station_code, metric_type, unit, value) AS (
  VALUES
    ('ST_RAIN_CP_01', 'RAINFALL',        'mm',    :rain_cp01),
    ('ST_RAIN_CP_02', 'RAINFALL',        'mm',    :rain_cp02),
    ('ST_WL_CP_01',   'WATER_LEVEL',     'm',     :wl_cp01),
    ('ST_WL_CP_02',   'WATER_LEVEL',     'm',     :wl_cp02),
    ('ST_FLOW_CP_01', 'FLOW',            'm3/s',  :flow_cp01),
    ('ST_RES_CP_01',  'RESERVOIR_LEVEL', 'm',     :res_cp01),
    ('ST_GATE_CP_01', 'GATE_OPENING',    'm',     :gate_cp01),
    ('ST_PUMP_CP_01', 'PUMP_POWER',      'kW',    :pump_cp01)
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
  'DEMO_RISK',
  'DEMO_RISK_' || :'scenario' || '_' || to_char(observed_at, 'YYYYMMDDHH24MISS') || '_' || station_code
FROM generated;

WITH alarm_seed(station_code, metric_type, level, min_rank, message) AS (
  VALUES
    ('ST_RAIN_CP_01', 'RAINFALL',        'WARNING',  1, '[DEMO_RISK] 翠屏北溪短时降雨超过25mm/h，建议加密雨情监测。'),
    ('ST_WL_CP_02',   'WATER_LEVEL',     'WARNING',  1, '[DEMO_RISK] 翠屏北岸水位超过3.25m预警线，低洼岸段需巡查。'),
    ('ST_WL_CP_01',   'WATER_LEVEL',     'CRITICAL', 2, '[DEMO_RISK] 翠屏湖心水位突破4.15m危险线，需启动应急会商。'),
    ('ST_FLOW_CP_01', 'FLOW',            'CRITICAL', 2, '[DEMO_RISK] 翠屏出湖流量超过480m3/s危险阈值，闸站需联动调度。'),
    ('ST_PUMP_CP_01', 'PUMP_POWER',      'WARNING',  2, '[DEMO_RISK] 翠屏城区泵站接近满载运行，需安排设备值守。'),
    ('ST_RAIN_CP_02', 'RAINFALL',        'CRITICAL', 3, '[DEMO_RISK] 翠屏南溪雨量超过50mm/h危险阈值，上游来水风险升高。'),
    ('ST_RES_CP_01',  'RESERVOIR_LEVEL', 'CRITICAL', 3, '[DEMO_RISK] 翠屏水库水位达到危险控制线，需校核泄洪能力。'),
    ('ST_GATE_CP_01', 'GATE_OPENING',    'WARNING',  3, '[DEMO_RISK] 翠屏闸开度持续增大，需关注下游行洪安全。')
),
selected_alarms AS (
  SELECT s.id AS station_id, a.metric_type, a.level, a.message
  FROM alarm_seed a
  JOIN station s ON s.code = a.station_code
  WHERE a.min_rank <= :scenario_rank
),
closed_stale AS (
  UPDATE alarm existing
  SET status = 'CLOSED',
      end_at = CURRENT_TIMESTAMP,
      last_trigger_at = CURRENT_TIMESTAMP,
      closed_at = CURRENT_TIMESTAMP,
      updated_at = CURRENT_TIMESTAMP
  WHERE existing.status = 'OPEN'
    AND existing.message LIKE '[DEMO_RISK]%'
    AND NOT EXISTS (
      SELECT 1
      FROM selected_alarms
      WHERE selected_alarms.station_id = existing.station_id
        AND selected_alarms.metric_type = existing.metric_type
        AND selected_alarms.level = existing.level
    )
  RETURNING existing.id
),
updated AS (
  UPDATE alarm existing
  SET last_trigger_at = CURRENT_TIMESTAMP,
      end_at = NULL,
      status = 'OPEN',
      message = selected_alarms.message,
      acknowledged_by = NULL,
      acknowledged_at = NULL,
      closed_by = NULL,
      closed_at = NULL,
      updated_at = CURRENT_TIMESTAMP
  FROM selected_alarms
  WHERE existing.station_id = selected_alarms.station_id
    AND existing.metric_type = selected_alarms.metric_type
    AND existing.level = selected_alarms.level
    AND existing.status = 'OPEN'
    AND existing.message LIKE '[DEMO_RISK]%'
  RETURNING existing.id
)
INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  gen_random_uuid()::text,
  selected_alarms.station_id,
  selected_alarms.metric_type,
  selected_alarms.level,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  NULL,
  'OPEN',
  selected_alarms.message,
  NULL,
  NULL,
  NULL,
  NULL,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM selected_alarms
WHERE NOT EXISTS (
  SELECT 1
  FROM alarm existing
  WHERE existing.station_id = selected_alarms.station_id
    AND existing.metric_type = selected_alarms.metric_type
    AND existing.level = selected_alarms.level
    AND existing.status = 'OPEN'
);

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
      SET source_tag = 'DEMO_RISK'
      WHERE status = 'OPEN'
        AND message LIKE '[DEMO_RISK]%'
    $sql$;
  END IF;
END $$;

SELECT :'scenario' AS scenario,
       count(*) FILTER (WHERE status = 'OPEN') AS open_demo_alarms
FROM alarm
WHERE message LIKE '[DEMO_RISK]%';
SQL

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${SCENARIO} demo risk scenario is active"
