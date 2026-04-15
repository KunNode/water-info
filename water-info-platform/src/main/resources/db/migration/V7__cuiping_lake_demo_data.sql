-- ============================================================
-- V7: Rebuild demo data as a single-basin "Cuiping Lake" model
-- Clears V4/V6 business data and reseeds a compact, coherent
-- 7-day flood narrative for demos.
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. Clear existing demo/business data
-- ============================================================

DELETE FROM sys_audit_log;
DELETE FROM alarm;
DELETE FROM observation;
DELETE FROM threshold_rule;
DELETE FROM sensor;
DELETE FROM station;
DELETE FROM sys_user_role;
DELETE FROM sys_user;
DELETE FROM sys_dept;
DELETE FROM sys_org WHERE code <> 'DEFAULT_ORG';

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'ADMIN', 'Administrator', 'Full system access'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'ADMIN');

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'OPERATOR', 'Operator', 'Can manage data, alarms, and resources'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'OPERATOR');

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'VIEWER', 'Viewer', 'Read-only access'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'VIEWER');

INSERT INTO sys_org (id, code, name, region, created_at, updated_at)
SELECT '90000000-0000-0000-0000-000000000001', 'DEFAULT_ORG', 'Default Organization', 'Default Region', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM sys_org WHERE code = 'DEFAULT_ORG');

-- ============================================================
-- 2. Single organization / department / user setup
-- ============================================================

INSERT INTO sys_org (id, code, name, region, created_at, updated_at)
VALUES
  ('90000000-0000-0000-0000-000000000101', 'ORG_CP', '翠屏市水务局', '翠屏市', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at)
VALUES
  ('91000000-0000-0000-0000-000000000101', '90000000-0000-0000-0000-000000000101', '监测调度科', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('91000000-0000-0000-0000-000000000102', '90000000-0000-0000-0000-000000000101', '防汛巡检组', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO sys_user (
  id, username, password_hash, real_name, phone, email,
  org_id, dept_id, status, last_login_at, password_updated_at,
  created_at, updated_at, deleted
)
VALUES
  (
    '92000000-0000-0000-0000-000000000001',
    'admin',
    crypt('Admin@123456', gen_salt('bf')),
    '系统管理员',
    '13800000101',
    'admin@cuiping-water.local',
    '90000000-0000-0000-0000-000000000101',
    '91000000-0000-0000-0000-000000000101',
    'ACTIVE',
    CURRENT_TIMESTAMP - INTERVAL '2 hour',
    CURRENT_TIMESTAMP - INTERVAL '30 day',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    0
  ),
  (
    '92000000-0000-0000-0000-000000000002',
    'operator01',
    crypt('Operator@123456', gen_salt('bf')),
    '值班调度员',
    '13800000102',
    'operator01@cuiping-water.local',
    '90000000-0000-0000-0000-000000000101',
    '91000000-0000-0000-0000-000000000101',
    'ACTIVE',
    CURRENT_TIMESTAMP - INTERVAL '5 hour',
    CURRENT_TIMESTAMP - INTERVAL '20 day',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    0
  ),
  (
    '92000000-0000-0000-0000-000000000004',
    'viewer01',
    crypt('Viewer@123456', gen_salt('bf')),
    '监管查看员',
    '13800000103',
    'viewer01@cuiping-water.local',
    '90000000-0000-0000-0000-000000000101',
    '91000000-0000-0000-0000-000000000102',
    'ACTIVE',
    CURRENT_TIMESTAMP - INTERVAL '1 day',
    CURRENT_TIMESTAMP - INTERVAL '18 day',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    0
  );

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT gen_random_uuid()::text, u.id, r.id, CURRENT_TIMESTAMP
FROM sys_user u
JOIN sys_role r ON r.code = 'ADMIN'
WHERE u.username = 'admin';

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT gen_random_uuid()::text, u.id, r.id, CURRENT_TIMESTAMP
FROM sys_user u
JOIN sys_role r ON r.code = 'OPERATOR'
WHERE u.username = 'operator01';

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT gen_random_uuid()::text, u.id, r.id, CURRENT_TIMESTAMP
FROM sys_user u
JOIN sys_role r ON r.code = 'VIEWER'
WHERE u.username = 'viewer01';

-- ============================================================
-- 3. Cuiping Lake basin stations and sensors
-- ============================================================

INSERT INTO station (
  id, code, name, type, river_basin, admin_region,
  lat, lon, elevation, status, created_at, updated_at
)
VALUES
  ('93000000-0000-0000-0000-000000000101', 'ST_RAIN_CP_01', '翠屏北溪雨量站', 'RAIN_GAUGE', '翠屏湖流域', '翠屏市', 30.5632100, 120.3128100, 38.20, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000102', 'ST_RAIN_CP_02', '翠屏南溪雨量站', 'RAIN_GAUGE', '翠屏湖流域', '翠屏市', 30.5416200, 120.2943500, 62.40, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000103', 'ST_WL_CP_01',   '翠屏湖心水位站', 'WATER_LEVEL', '翠屏湖流域', '翠屏市', 30.5524100, 120.3277300, 27.10, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000104', 'ST_WL_CP_02',   '翠屏北岸水位站', 'WATER_LEVEL', '翠屏湖流域', '翠屏市', 30.5579800, 120.3361100, 24.80, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000105', 'ST_FLOW_CP_01', '翠屏出湖流量站', 'FLOW',        '翠屏湖流域', '翠屏市', 30.5455100, 120.3496600, 22.60, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000106', 'ST_RES_CP_01',  '翠屏水库站',     'RESERVOIR',   '翠屏湖流域', '翠屏市', 30.5511700, 120.3238800, 31.50, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000107', 'ST_GATE_CP_01', '翠屏闸站',       'GATE',        '翠屏湖流域', '翠屏市', 30.5437200, 120.3529400, 21.80, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000108', 'ST_PUMP_CP_01', '翠屏城区泵站',   'PUMP_STATION','翠屏湖流域', '翠屏市', 30.5586400, 120.3418200, 23.40, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
)
VALUES
  ('94000000-0000-0000-0000-000000000101', '93000000-0000-0000-0000-000000000101', 'RAINFALL',        'mm',   300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '3 minute', '{"zone":"北溪入湖口","model":"CP-RG-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000102', '93000000-0000-0000-0000-000000000102', 'RAINFALL',        'mm',   300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '4 minute', '{"zone":"南溪山区","model":"CP-RG-02"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000103', '93000000-0000-0000-0000-000000000103', 'WATER_LEVEL',     'm',     60, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '1 minute', '{"zone":"湖心","model":"CP-WL-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000104', '93000000-0000-0000-0000-000000000104', 'WATER_LEVEL',     'm',     60, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '2 minute', '{"zone":"北岸城区段","model":"CP-WL-02"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000105', '93000000-0000-0000-0000-000000000105', 'FLOW',            'm3/s', 120, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '5 minute', '{"zone":"出湖口","model":"CP-FM-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000106', '93000000-0000-0000-0000-000000000106', 'RESERVOIR_LEVEL', 'm',    300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '6 minute', '{"zone":"湖心水库","model":"CP-RL-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000107', '93000000-0000-0000-0000-000000000107', 'GATE_OPENING',    'm',    600, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '8 minute', '{"zone":"出湖泄洪闸","model":"CP-GT-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000108', '93000000-0000-0000-0000-000000000108', 'PUMP_POWER',      'kW',   300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '2 minute', '{"zone":"北岸城区泵站","model":"CP-PP-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- ============================================================
-- 4. Threshold rules (8 stations x 2 levels = 16)
-- ============================================================

WITH threshold_seed (
  warning_rule_id, critical_rule_id, station_code, metric_type,
  warn_value, critical_value, warn_duration, critical_duration
) AS (
  VALUES
    ('95000000-0000-0000-0000-000000000101', '95000000-0000-0000-0000-000000000102', 'ST_RAIN_CP_01', 'RAINFALL',        25.000, 45.000, 60, 30),
    ('95000000-0000-0000-0000-000000000103', '95000000-0000-0000-0000-000000000104', 'ST_RAIN_CP_02', 'RAINFALL',        30.000, 50.000, 60, 30),
    ('95000000-0000-0000-0000-000000000105', '95000000-0000-0000-0000-000000000106', 'ST_WL_CP_01',   'WATER_LEVEL',      3.600,  4.150, 15, 10),
    ('95000000-0000-0000-0000-000000000107', '95000000-0000-0000-0000-000000000108', 'ST_WL_CP_02',   'WATER_LEVEL',      3.250,  3.800, 15, 10),
    ('95000000-0000-0000-0000-000000000109', '95000000-0000-0000-0000-000000000110', 'ST_FLOW_CP_01', 'FLOW',           320.000, 480.000, 20, 15),
    ('95000000-0000-0000-0000-000000000111', '95000000-0000-0000-0000-000000000112', 'ST_RES_CP_01',  'RESERVOIR_LEVEL', 39.600, 41.000, 30, 20),
    ('95000000-0000-0000-0000-000000000113', '95000000-0000-0000-0000-000000000114', 'ST_GATE_CP_01', 'GATE_OPENING',     1.500,  2.400, 10, 10),
    ('95000000-0000-0000-0000-000000000115', '95000000-0000-0000-0000-000000000116', 'ST_PUMP_CP_01', 'PUMP_POWER',     180.000, 260.000, 20, 15)
)
INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value, duration_min,
  rate_threshold, enabled, created_at, updated_at
)
SELECT
  t.warning_rule_id,
  s.id,
  t.metric_type,
  'WARNING',
  t.warn_value,
  t.warn_duration,
  NULL::numeric,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM threshold_seed t
JOIN station s ON s.code = t.station_code
UNION ALL
SELECT
  t.critical_rule_id,
  s.id,
  t.metric_type,
  'CRITICAL',
  t.critical_value,
  t.critical_duration,
  NULL::numeric,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM threshold_seed t
JOIN station s ON s.code = t.station_code;

-- ============================================================
-- 5. Observations (8 stations x 168 hours = 1344)
-- Narrative: Normal -> Buildup -> Peak -> Recession
-- ============================================================

WITH station_metric (
  station_code, metric_type, unit, normal_base, buildup_target, peak_value,
  recession_floor, lag_h, wave_amp, noise_amp, decay_hours
) AS (
  VALUES
    ('ST_RAIN_CP_01', 'RAINFALL',        'mm',    1.2, 24.0, 54.0, 12.0,  0, 0.20, 0.05, 18.0),
    ('ST_RAIN_CP_02', 'RAINFALL',        'mm',    1.5, 28.0, 60.0, 24.0,  1, 0.22, 0.05, 18.0),
    ('ST_WL_CP_01',   'WATER_LEVEL',     'm',     2.85, 3.75, 4.45, 4.05, 10, 0.04, 0.01, 20.0),
    ('ST_WL_CP_02',   'WATER_LEVEL',     'm',     2.60, 3.18, 3.82, 2.90, 11, 0.05, 0.01, 16.0),
    ('ST_FLOW_CP_01', 'FLOW',            'm3/s', 118.0, 340.0, 560.0, 460.0, 13, 0.05, 0.02, 20.0),
    ('ST_RES_CP_01',  'RESERVOIR_LEVEL', 'm',    37.40, 39.55, 41.35, 39.95,  8, 0.04, 0.01, 18.0),
    ('ST_GATE_CP_01', 'GATE_OPENING',    'm',     0.28, 1.55, 2.72, 1.65, 14, 0.08, 0.02, 16.0),
    ('ST_PUMP_CP_01', 'PUMP_POWER',      'kW',   62.0, 186.0, 282.0, 170.0, 12, 0.07, 0.02, 16.0)
),
hourly AS (
  SELECT
    gs AS h,
    date_trunc('hour', CURRENT_TIMESTAMP) - INTERVAL '167 hour' + (gs * INTERVAL '1 hour') AS observed_at
  FROM generate_series(0, 167) AS gs
),
valued AS (
  SELECT
    sm.station_code,
    sm.metric_type,
    sm.unit,
    hr.observed_at,
    hr.h,
    GREATEST(0, hr.h - sm.lag_h) AS eff_h,
    sm.normal_base,
    sm.buildup_target,
    sm.peak_value,
    sm.recession_floor,
    sm.wave_amp,
    sm.noise_amp,
    sm.decay_hours
  FROM station_metric sm
  CROSS JOIN hourly hr
),
computed AS (
  SELECT
    v.station_code,
    v.metric_type,
    v.unit,
    v.observed_at,
    CASE
      WHEN v.eff_h < 72 THEN
        v.normal_base * (1.0 + v.wave_amp * sin(v.eff_h::double precision * 0.23))
      WHEN v.eff_h < 120 THEN
        v.normal_base
        + (v.buildup_target - v.normal_base) * ((v.eff_h - 72.0) / 48.0)
        + (v.buildup_target - v.normal_base) * 0.08 * sin(v.eff_h::double precision * 0.35)
      WHEN v.eff_h < 144 THEN
        v.buildup_target
        + (v.peak_value - v.buildup_target)
          * (0.62 + 0.38 * sin(((v.eff_h - 120.0) / 24.0) * 3.1415926))
      ELSE
        v.recession_floor
        + (v.peak_value - v.recession_floor)
          * exp(-((v.eff_h - 144.0)::double precision / v.decay_hours))
    END
    + (v.peak_value - v.normal_base) * v.noise_amp
      * sin(v.h::double precision * 0.71 + length(v.station_code)::double precision)
    AS raw_value
  FROM valued v
)
INSERT INTO observation (
  id, station_id, metric_type, value, unit, observed_at,
  quality_flag, source, request_id, created_at
)
SELECT
  gen_random_uuid()::text,
  s.id,
  c.metric_type,
  ROUND(GREATEST(0, c.raw_value)::numeric, 3),
  c.unit,
  c.observed_at,
  'GOOD',
  'SEED_V7_CUIPING_GENERATOR',
  'SEED_V7_CP_7D',
  CURRENT_TIMESTAMP
FROM computed c
JOIN station s ON s.code = c.station_code;

-- ============================================================
-- 6. Alarm lifecycle coverage (2 CLOSED / 2 ACK / 2 OPEN)
-- ============================================================

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '96000000-0000-0000-0000-000000000101',
  s.id,
  'RAINFALL',
  'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '82 hour',
  CURRENT_TIMESTAMP - INTERVAL '80 hour',
  CURRENT_TIMESTAMP - INTERVAL '76 hour',
  'CLOSED',
  '翠屏北溪短时降雨超过 25mm/h，雨势已明显减弱并恢复正常。',
  u1.id,
  CURRENT_TIMESTAMP - INTERVAL '81 hour',
  u1.id,
  CURRENT_TIMESTAMP - INTERVAL '76 hour',
  CURRENT_TIMESTAMP - INTERVAL '82 hour',
  CURRENT_TIMESTAMP - INTERVAL '76 hour'
FROM station s
JOIN sys_user u1 ON u1.username = 'operator01'
WHERE s.code = 'ST_RAIN_CP_01';

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '96000000-0000-0000-0000-000000000102',
  s.id,
  'WATER_LEVEL',
  'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '66 hour',
  CURRENT_TIMESTAMP - INTERVAL '61 hour',
  CURRENT_TIMESTAMP - INTERVAL '40 hour',
  'CLOSED',
  '翠屏北岸水位曾突破 3.25m 预警线，随降雨减弱后已回落。',
  u1.id,
  CURRENT_TIMESTAMP - INTERVAL '64 hour',
  u1.id,
  CURRENT_TIMESTAMP - INTERVAL '40 hour',
  CURRENT_TIMESTAMP - INTERVAL '66 hour',
  CURRENT_TIMESTAMP - INTERVAL '40 hour'
FROM station s
JOIN sys_user u1 ON u1.username = 'operator01'
WHERE s.code = 'ST_WL_CP_02';

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '96000000-0000-0000-0000-000000000103',
  s.id,
  'RAINFALL',
  'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '34 hour',
  CURRENT_TIMESTAMP - INTERVAL '10 hour',
  NULL,
  'ACK',
  '翠屏南溪山区持续降雨，值班调度员已确认并加密关注上游来水。',
  u1.id,
  CURRENT_TIMESTAMP - INTERVAL '32 hour',
  NULL,
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '34 hour',
  CURRENT_TIMESTAMP - INTERVAL '10 hour'
FROM station s
JOIN sys_user u1 ON u1.username = 'operator01'
WHERE s.code = 'ST_RAIN_CP_02';

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '96000000-0000-0000-0000-000000000104',
  s.id,
  'PUMP_POWER',
  'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '18 hour',
  CURRENT_TIMESTAMP - INTERVAL '2 hour',
  NULL,
  'ACK',
  '翠屏城区泵站长时间高负荷运行，已安排持续值守和设备巡检。',
  u1.id,
  CURRENT_TIMESTAMP - INTERVAL '16 hour',
  NULL,
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '18 hour',
  CURRENT_TIMESTAMP - INTERVAL '2 hour'
FROM station s
JOIN sys_user u1 ON u1.username = 'operator01'
WHERE s.code = 'ST_PUMP_CP_01';

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '96000000-0000-0000-0000-000000000105',
  s.id,
  'WATER_LEVEL',
  'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '14 hour',
  CURRENT_TIMESTAMP - INTERVAL '1 hour',
  NULL,
  'OPEN',
  '翠屏湖心水位突破 4.15m 危险线，当前仍处于高位运行阶段。',
  NULL,
  NULL,
  NULL,
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '14 hour',
  CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM station s
WHERE s.code = 'ST_WL_CP_01';

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '96000000-0000-0000-0000-000000000106',
  s.id,
  'FLOW',
  'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '12 hour',
  CURRENT_TIMESTAMP - INTERVAL '1 hour',
  NULL,
  'OPEN',
  '翠屏出湖流量超过 480m3/s 危险阈值，翠屏闸持续泄洪中。',
  NULL,
  NULL,
  NULL,
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '12 hour',
  CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM station s
WHERE s.code = 'ST_FLOW_CP_01';

COMMIT;
