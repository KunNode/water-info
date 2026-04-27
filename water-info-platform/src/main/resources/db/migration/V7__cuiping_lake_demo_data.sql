-- ============================================================
-- V7: Cuiping Lake (翠屏湖) single-basin demo data
-- Replaces V4/V6 multi-basin data with one fictional lake basin.
-- 8 stations, 3 users, 1344 observations, 16 thresholds, 6 alarms,
-- 20 audit logs, 3 emergency plans.
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. Clear existing demo/business data (FK-safe order)
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

-- Purge AI tables (may not exist on first run — wrap in DO block)
DO $$ BEGIN
  DELETE FROM notification_record;
  DELETE FROM resource_allocation;
  DELETE FROM emergency_action;
  DELETE FROM emergency_plan;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Ensure roles exist
INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'ADMIN', 'Administrator', 'Full system access'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'ADMIN');

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'OPERATOR', 'Operator', 'Can manage data, alarms, and resources'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'OPERATOR');

INSERT INTO sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'VIEWER', 'Viewer', 'Read-only access'
WHERE NOT EXISTS (SELECT 1 FROM sys_role WHERE code = 'VIEWER');

-- ============================================================
-- 2. Organization & departments
-- ============================================================

INSERT INTO sys_org (id, code, name, region, created_at, updated_at)
VALUES ('90000000-0000-0000-0000-000000000101', 'ORG_CP', '翠屏市水务局', '翠屏市', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, region = EXCLUDED.region, updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at) VALUES
  ('91000000-0000-0000-0000-000000000101', '90000000-0000-0000-0000-000000000101', '监测调度科', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('91000000-0000-0000-0000-000000000102', '90000000-0000-0000-0000-000000000101', '防汛巡检组', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE SET org_id = EXCLUDED.org_id, name = EXCLUDED.name, updated_at = CURRENT_TIMESTAMP;

-- ============================================================
-- 3. Users (3 accounts)
--   admin      / Admin@123456    → ADMIN
--   operator01 / Operator@123456 → OPERATOR
--   viewer01   / Viewer@123456   → VIEWER
-- ============================================================

INSERT INTO sys_user (
  id, username, password_hash, real_name, phone, email,
  org_id, dept_id, status, last_login_at, password_updated_at,
  created_at, updated_at, deleted
) VALUES
  ('92000000-0000-0000-0000-000000000001', 'admin',
   crypt('Admin@123456', gen_salt('bf')),
   '系统管理员', '13800000101', 'admin@cuiping-water.local',
   '90000000-0000-0000-0000-000000000101', '91000000-0000-0000-0000-000000000101',
   'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '2 hour', CURRENT_TIMESTAMP - INTERVAL '30 day',
   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0),
  ('92000000-0000-0000-0000-000000000002', 'operator01',
   crypt('Operator@123456', gen_salt('bf')),
   '值班调度员', '13800000102', 'operator01@cuiping-water.local',
   '90000000-0000-0000-0000-000000000101', '91000000-0000-0000-0000-000000000101',
   'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '5 hour', CURRENT_TIMESTAMP - INTERVAL '20 day',
   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0),
  ('92000000-0000-0000-0000-000000000004', 'viewer01',
   crypt('Viewer@123456', gen_salt('bf')),
   '监管查看员', '13800000103', 'viewer01@cuiping-water.local',
   '90000000-0000-0000-0000-000000000101', '91000000-0000-0000-0000-000000000102',
   'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '1 day', CURRENT_TIMESTAMP - INTERVAL '18 day',
   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
ON CONFLICT (username) DO UPDATE SET
  password_hash = EXCLUDED.password_hash, real_name = EXCLUDED.real_name,
  phone = EXCLUDED.phone, email = EXCLUDED.email, org_id = EXCLUDED.org_id,
  dept_id = EXCLUDED.dept_id, status = EXCLUDED.status, deleted = 0,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT gen_random_uuid()::text, u.id, r.id, CURRENT_TIMESTAMP
FROM sys_user u JOIN sys_role r ON r.code = 'ADMIN' WHERE u.username = 'admin'
ON CONFLICT ON CONSTRAINT uk_user_role DO NOTHING;

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT gen_random_uuid()::text, u.id, r.id, CURRENT_TIMESTAMP
FROM sys_user u JOIN sys_role r ON r.code = 'OPERATOR' WHERE u.username = 'operator01'
ON CONFLICT ON CONSTRAINT uk_user_role DO NOTHING;

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT gen_random_uuid()::text, u.id, r.id, CURRENT_TIMESTAMP
FROM sys_user u JOIN sys_role r ON r.code = 'VIEWER' WHERE u.username = 'viewer01'
ON CONFLICT ON CONSTRAINT uk_user_role DO NOTHING;

-- ============================================================
-- 4. Stations (8 — single basin: 翠屏湖流域)
-- ============================================================
-- Coordinates cluster around (30.55, 120.33) — fictional Cuiping Lake

INSERT INTO station (
  id, code, name, type, river_basin, admin_region,
  lat, lon, elevation, status, created_at, updated_at
) VALUES
  ('93000000-0000-0000-0000-000000000101', 'ST_RAIN_CP_01', '翠屏北溪雨量站', 'RAIN_GAUGE',    '翠屏湖流域', '翠屏市', 30.5632100, 120.3128100, 38.20, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000102', 'ST_RAIN_CP_02', '翠屏南溪雨量站', 'RAIN_GAUGE',    '翠屏湖流域', '翠屏市', 30.5416200, 120.2943500, 62.40, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000103', 'ST_WL_CP_01',   '翠屏湖心水位站', 'WATER_LEVEL',   '翠屏湖流域', '翠屏市', 30.5524100, 120.3277300, 27.10, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000104', 'ST_WL_CP_02',   '翠屏北岸水位站', 'WATER_LEVEL',   '翠屏湖流域', '翠屏市', 30.5579800, 120.3361100, 24.80, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000105', 'ST_FLOW_CP_01', '翠屏出湖流量站', 'FLOW',          '翠屏湖流域', '翠屏市', 30.5455100, 120.3496600, 22.60, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000106', 'ST_RES_CP_01',  '翠屏水库站',     'RESERVOIR',     '翠屏湖流域', '翠屏市', 30.5511700, 120.3238800, 31.50, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000107', 'ST_GATE_CP_01', '翠屏闸站',       'GATE',          '翠屏湖流域', '翠屏市', 30.5437200, 120.3529400, 21.80, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000108', 'ST_PUMP_CP_01', '翠屏城区泵站',   'PUMP_STATION',  '翠屏湖流域', '翠屏市', 30.5586400, 120.3418200, 23.40, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO UPDATE SET
  name = EXCLUDED.name, type = EXCLUDED.type, river_basin = EXCLUDED.river_basin,
  admin_region = EXCLUDED.admin_region, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
  elevation = EXCLUDED.elevation, status = EXCLUDED.status, updated_at = CURRENT_TIMESTAMP;

-- ============================================================
-- 5. Sensors (8 — one per station)
-- ============================================================

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
) VALUES
  ('94000000-0000-0000-0000-000000000101', '93000000-0000-0000-0000-000000000101', 'RAINFALL',        'mm',   300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '3 minute', '{"zone":"北溪入湖口","model":"CP-RG-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000102', '93000000-0000-0000-0000-000000000102', 'RAINFALL',        'mm',   300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '4 minute', '{"zone":"南溪山区","model":"CP-RG-02"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000103', '93000000-0000-0000-0000-000000000103', 'WATER_LEVEL',     'm',     60, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '1 minute', '{"zone":"湖心","model":"CP-WL-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000104', '93000000-0000-0000-0000-000000000104', 'WATER_LEVEL',     'm',     60, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '2 minute', '{"zone":"北岸城区段","model":"CP-WL-02"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000105', '93000000-0000-0000-0000-000000000105', 'FLOW',            'm3/s', 120, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '5 minute', '{"zone":"出湖口","model":"CP-FM-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000106', '93000000-0000-0000-0000-000000000106', 'RESERVOIR_LEVEL', 'm',    300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '6 minute', '{"zone":"湖心水库","model":"CP-RL-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000107', '93000000-0000-0000-0000-000000000107', 'GATE_OPENING',    'm',    600, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '8 minute', '{"zone":"出湖泄洪闸","model":"CP-GT-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('94000000-0000-0000-0000-000000000108', '93000000-0000-0000-0000-000000000108', 'PUMP_POWER',      'kW',   300, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '2 minute', '{"zone":"北岸城区泵站","model":"CP-PP-01"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  status=EXCLUDED.status, last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

-- ============================================================
-- 6. Threshold rules (8 stations x 2 levels = 16)
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
SELECT t.warning_rule_id, s.id, t.metric_type, 'WARNING', t.warn_value, t.warn_duration,
       NULL::numeric, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM threshold_seed t JOIN station s ON s.code = t.station_code
UNION ALL
SELECT t.critical_rule_id, s.id, t.metric_type, 'CRITICAL', t.critical_value, t.critical_duration,
       NULL::numeric, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM threshold_seed t JOIN station s ON s.code = t.station_code;

-- ============================================================
-- 7. Observations (8 stations x 168 hours = 1344 rows)
-- Narrative: Normal(0-71) → Buildup(72-119) → Peak(120-143) → Recession(144-167)
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
  SELECT gs AS h,
    date_trunc('hour', CURRENT_TIMESTAMP) - INTERVAL '167 hour' + (gs * INTERVAL '1 hour') AS observed_at
  FROM generate_series(0, 167) AS gs
),
valued AS (
  SELECT sm.station_code, sm.metric_type, sm.unit, hr.observed_at, hr.h,
    GREATEST(0, hr.h - sm.lag_h) AS eff_h,
    sm.normal_base, sm.buildup_target, sm.peak_value,
    sm.recession_floor, sm.wave_amp, sm.noise_amp, sm.decay_hours
  FROM station_metric sm CROSS JOIN hourly hr
),
computed AS (
  SELECT v.station_code, v.metric_type, v.unit, v.observed_at,
    CASE
      WHEN v.eff_h < 72 THEN
        v.normal_base * (1.0 + v.wave_amp * sin(v.eff_h::double precision * 0.23))
      WHEN v.eff_h < 120 THEN
        v.normal_base + (v.buildup_target - v.normal_base) * ((v.eff_h - 72.0) / 48.0)
        + (v.buildup_target - v.normal_base) * 0.08 * sin(v.eff_h::double precision * 0.35)
      WHEN v.eff_h < 144 THEN
        v.buildup_target + (v.peak_value - v.buildup_target)
          * (0.62 + 0.38 * sin(((v.eff_h - 120.0) / 24.0) * 3.1415926))
      ELSE
        v.recession_floor + (v.peak_value - v.recession_floor)
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
  gen_random_uuid()::text, s.id, c.metric_type,
  ROUND(GREATEST(0, c.raw_value)::numeric, 3),
  c.unit, c.observed_at,
  CASE
    WHEN (EXTRACT(EPOCH FROM c.observed_at)::bigint % 23 = 0) THEN 'SUSPECT'
    WHEN (EXTRACT(EPOCH FROM c.observed_at)::bigint % 37 = 0) THEN 'MISSING'
    ELSE 'GOOD'
  END,
  'SEED_V7_CUIPING_GENERATOR', 'SEED_V7_CP_7D', CURRENT_TIMESTAMP
FROM computed c JOIN station s ON s.code = c.station_code;

-- ============================================================
-- 8. Alarms (2 CLOSED / 2 ACK / 2 OPEN)
-- ============================================================

-- CLOSED #1: Historical rainfall warning (resolved ~3.5 days ago)
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT '96000000-0000-0000-0000-000000000101', s.id, 'RAINFALL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '82 hour', CURRENT_TIMESTAMP - INTERVAL '80 hour', CURRENT_TIMESTAMP - INTERVAL '76 hour',
  'CLOSED', '翠屏北溪短时降雨超过 25mm/h，雨势已明显减弱并恢复正常。',
  u1.id, CURRENT_TIMESTAMP - INTERVAL '81 hour', u1.id, CURRENT_TIMESTAMP - INTERVAL '76 hour',
  CURRENT_TIMESTAMP - INTERVAL '82 hour', CURRENT_TIMESTAMP - INTERVAL '76 hour'
FROM station s JOIN sys_user u1 ON u1.username = 'operator01' WHERE s.code = 'ST_RAIN_CP_01';

-- CLOSED #2: Historical water level warning (resolved ~2 days ago)
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT '96000000-0000-0000-0000-000000000102', s.id, 'WATER_LEVEL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '66 hour', CURRENT_TIMESTAMP - INTERVAL '61 hour', CURRENT_TIMESTAMP - INTERVAL '40 hour',
  'CLOSED', '翠屏北岸水位曾突破 3.25m 预警线，随降雨减弱后已回落。',
  u1.id, CURRENT_TIMESTAMP - INTERVAL '64 hour', u1.id, CURRENT_TIMESTAMP - INTERVAL '40 hour',
  CURRENT_TIMESTAMP - INTERVAL '66 hour', CURRENT_TIMESTAMP - INTERVAL '40 hour'
FROM station s JOIN sys_user u1 ON u1.username = 'operator01' WHERE s.code = 'ST_WL_CP_02';

-- ACK #1: Ongoing rainfall (acknowledged by operator)
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT '96000000-0000-0000-0000-000000000103', s.id, 'RAINFALL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '34 hour', CURRENT_TIMESTAMP - INTERVAL '10 hour', NULL,
  'ACK', '翠屏南溪山区持续降雨，值班调度员已确认并加密关注上游来水。',
  u1.id, CURRENT_TIMESTAMP - INTERVAL '32 hour', NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '34 hour', CURRENT_TIMESTAMP - INTERVAL '10 hour'
FROM station s JOIN sys_user u1 ON u1.username = 'operator01' WHERE s.code = 'ST_RAIN_CP_02';

-- ACK #2: Pump overload (acknowledged)
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT '96000000-0000-0000-0000-000000000104', s.id, 'PUMP_POWER', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '18 hour', CURRENT_TIMESTAMP - INTERVAL '2 hour', NULL,
  'ACK', '翠屏城区泵站长时间高负荷运行，已安排持续值守和设备巡检。',
  u1.id, CURRENT_TIMESTAMP - INTERVAL '16 hour', NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '18 hour', CURRENT_TIMESTAMP - INTERVAL '2 hour'
FROM station s JOIN sys_user u1 ON u1.username = 'operator01' WHERE s.code = 'ST_PUMP_CP_01';

-- OPEN #1: Lake center water level critical (unacknowledged)
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT '96000000-0000-0000-0000-000000000105', s.id, 'WATER_LEVEL', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '14 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour', NULL,
  'OPEN', '翠屏湖心水位突破 4.15m 危险线，当前仍处于高位运行阶段。',
  NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '14 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM station s WHERE s.code = 'ST_WL_CP_01';

-- OPEN #2: Outflow critical (unacknowledged)
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT '96000000-0000-0000-0000-000000000106', s.id, 'FLOW', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '12 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour', NULL,
  'OPEN', '翠屏出湖流量超过 480m³/s 危险阈值，翠屏闸持续泄洪中。',
  NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '12 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM station s WHERE s.code = 'ST_FLOW_CP_01';

-- ============================================================
-- 9. Audit logs (20 entries spanning 7 days)
-- ============================================================

-- Day 1-2: Normal operations
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.10', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '156 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '150 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'STATION_VIEW', 'STATION', '93000000-0000-0000-0000-000000000101',
  '{"station_code":"ST_RAIN_CP_01"}'::jsonb, '10.20.1.30', 'Firefox/125.0',
  CURRENT_TIMESTAMP - INTERVAL '148 hour' FROM sys_user u WHERE u.username='viewer01';

-- Day 3: Pre-flood threshold adjustment
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'THRESHOLD_UPDATE', 'THRESHOLD_RULE', '95000000-0000-0000-0000-000000000105',
  '{"field":"threshold_value","old":"3.40","new":"3.60","reason":"汛前调整翠屏湖心预警线"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '140 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'REPORT_EXPORT', 'REPORT', NULL,
  '{"report_type":"daily_summary","date":"2026-04-09"}'::jsonb, '10.20.1.10', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '132 hour' FROM sys_user u WHERE u.username='admin';

-- Day 4: Storm starts, first alarms
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', '96000000-0000-0000-0000-000000000101',
  '{"alarm_level":"WARNING","station":"ST_RAIN_CP_01","message":"北溪短时降雨超标"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '81 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_CLOSE', 'ALARM', '96000000-0000-0000-0000-000000000101',
  '{"alarm_level":"WARNING","station":"ST_RAIN_CP_01","close_reason":"降雨已停"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '76 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', '96000000-0000-0000-0000-000000000102',
  '{"alarm_level":"WARNING","station":"ST_WL_CP_02"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '64 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_CLOSE', 'ALARM', '96000000-0000-0000-0000-000000000102',
  '{"alarm_level":"WARNING","station":"ST_WL_CP_02","close_reason":"水位回落"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '40 hour' FROM sys_user u WHERE u.username='operator01';

-- Day 5: Buildup intensifies
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '50 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', '96000000-0000-0000-0000-000000000103',
  '{"alarm_level":"WARNING","station":"ST_RAIN_CP_02","message":"南溪山区持续降雨"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '32 hour' FROM sys_user u WHERE u.username='operator01';

-- Day 6: Peak — emergency
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success","scene":"emergency"}'::jsonb, '10.20.1.10', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '20 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', '96000000-0000-0000-0000-000000000104',
  '{"alarm_level":"WARNING","station":"ST_PUMP_CP_01","message":"泵站高负荷运行"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '16 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'STATION_VIEW', 'STATION', '93000000-0000-0000-0000-000000000105',
  '{"station_code":"ST_FLOW_CP_01","context":"紧急查看出湖流量"}'::jsonb, '10.20.1.30', 'Firefox/125.0',
  CURRENT_TIMESTAMP - INTERVAL '13 hour' FROM sys_user u WHERE u.username='viewer01';

-- Day 7: Ongoing monitoring
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '6 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'STATION_VIEW', 'STATION', '93000000-0000-0000-0000-000000000103',
  '{"station_code":"ST_WL_CP_01","context":"巡查翠屏湖心水位"}'::jsonb, '10.20.1.11', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '3 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.10', 'Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '2 hour' FROM sys_user u WHERE u.username='admin';

-- ============================================================
-- 10. AI Emergency Plans (3 plans with actions/resources/notifications)
-- ============================================================

-- Plan 1: Completed historical plan (moderate risk)
INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-CP-20260410-001',
  '翠屏湖春季防汛预案',
  'moderate',
  '翠屏湖水位超过预警线3.6m，持续降雨导致北溪来水增加',
  'completed',
  'session-cp-20260410-001',
  E'# 翠屏湖春季防汛预案\n\n## 风险研判\n\n受持续降雨影响，翠屏湖水位自4月8日起持续上涨，**翠屏湖心水位站**水位一度达到 **3.75m**，超过预警线3.6m。\n\n- 北溪来水量增加约30%\n- 翠屏出湖流量峰值达到340m³/s\n- 降雨已于4月10日趋缓\n\n## 应急措施\n\n1. **加密监测**：翠屏湖心水位站观测频次提高至每30分钟一次\n2. **堤防巡查**：安排8人对翠屏湖北岸重点堤段进行巡查\n3. **物资准备**：调运沙袋2000袋至翠屏湖北岸备用\n\n> 本预案于4月10日经评估后结束执行，翠屏湖水位已回落至安全水位。',
  CURRENT_TIMESTAMP - INTERVAL '120 hour',
  CURRENT_TIMESTAMP - INTERVAL '72 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status, summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-CP-20260410-001';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status) VALUES
  ('EP-CP-20260410-001', 'ACT-001', 'monitoring', '加密翠屏湖心水位站监测频次至每30分钟', 2, '监测调度科', 30, 'completed'),
  ('EP-CP-20260410-001', 'ACT-002', 'patrol', '安排堤防巡查人员8人，重点巡查翠屏湖北岸堤段', 2, '防汛巡检组', 60, 'completed');

DELETE FROM resource_allocation WHERE plan_id = 'EP-CP-20260410-001';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes) VALUES
  ('EP-CP-20260410-001', '物资', '防汛沙袋', 2000, '翠屏市防汛物资仓库', '翠屏湖北岸', 40);

DELETE FROM notification_record WHERE plan_id = 'EP-CP-20260410-001';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at) VALUES
  ('EP-CP-20260410-001', '监测调度科', 'sms', '【黄色预警】翠屏湖水位超过预警线3.6m，请启动III级应急响应', 'sent', CURRENT_TIMESTAMP - INTERVAL '119 hour');

-- Plan 2: Currently executing (high risk) — main showcase
INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-CP-20260414-001',
  '翠屏湖暴雨Ⅱ级响应预案',
  'high',
  '翠屏湖流域持续暴雨，湖心水位超危险线，水库逼近设计洪水位',
  'executing',
  'session-cp-20260414-001',
  E'# 翠屏湖暴雨Ⅱ级响应预案\n\n## 风险研判\n\n**综合风险等级：高（II级响应）**\n\n受副热带高压异常北抬影响，翠屏湖流域自4月12日起遭遇持续强降雨。\n\n### 关键数据\n\n| 监测站 | 指标 | 当前值 | 预警值 | 危险值 | 状态 |\n|--------|------|--------|--------|--------|------|\n| 翠屏南溪雨量站 | 1h降雨 | 55mm | 30mm | 50mm | **超危险** |\n| 翠屏湖心水位站 | 水位 | 4.35m | 3.6m | 4.15m | **超危险** |\n| 翠屏出湖流量站 | 流量 | 520m³/s | 320m³/s | 480m³/s | **超危险** |\n| 翠屏水库站 | 库水位 | 41.0m | 39.6m | 41.0m | 临界 |\n\n## 应急行动\n\n### 一、人员疏散\n- 组织翠屏湖北岸低洼地区约 **1500名居民** 转移\n- 启用翠屏中学作为临时安置点\n\n### 二、工程措施\n- 翠屏闸全开泄洪，最大泄量约560m³/s\n- 翠屏城区泵站满负荷运行，排涝能力240m³/h\n\n### 三、抢险救援\n- 抢险队伍60人在翠屏湖北岸堤段值守\n- 冲锋舟3艘在翠屏闸附近待命\n\n> **当前进度**：人员疏散已完成，工程调度执行中。',
  CURRENT_TIMESTAMP - INTERVAL '36 hour',
  CURRENT_TIMESTAMP - INTERVAL '1 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status, summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-CP-20260414-001';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status) VALUES
  ('EP-CP-20260414-001', 'ACT-001', 'evacuation', '组织翠屏湖北岸低洼地区约1500名居民转移至安全地带', 1, '监测调度科', 120, 'completed'),
  ('EP-CP-20260414-001', 'ACT-002', 'gate_control', '翠屏闸全开泄洪，最大泄量约560m³/s', 1, '监测调度科', 30, 'completed'),
  ('EP-CP-20260414-001', 'ACT-003', 'resource_deploy', '调运移动排涝泵车2台增援城区积水点', 1, '监测调度科', 60, 'in_progress'),
  ('EP-CP-20260414-001', 'ACT-004', 'patrol', '抢险队伍60人在翠屏湖北岸堤段24小时值守', 1, '防汛巡检组', 180, 'in_progress'),
  ('EP-CP-20260414-001', 'ACT-005', 'notification', '通过短信、微信发布橙色预警', 2, '监测调度科', 30, 'pending');

DELETE FROM resource_allocation WHERE plan_id = 'EP-CP-20260414-001';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes) VALUES
  ('EP-CP-20260414-001', '设备', '移动排涝泵车', 2, '翠屏市设备调配中心', '翠屏湖北岸涵洞段', 25),
  ('EP-CP-20260414-001', '物资', '防汛沙袋', 15000, '翠屏市防汛物资储备库', '翠屏湖北岸堤段沿线', 40),
  ('EP-CP-20260414-001', '设备', '冲锋舟', 3, '翠屏市消防救援支队', '翠屏闸附近水域', 30),
  ('EP-CP-20260414-001', '人员', '抢险队员', 60, '翠屏市应急管理局', '翠屏湖北岸堤段', 45);

DELETE FROM notification_record WHERE plan_id = 'EP-CP-20260414-001';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at) VALUES
  ('EP-CP-20260414-001', '翠屏湖北岸社区网格员', 'sms', '【橙色预警】翠屏湖水位超危险线4.15m，请立即组织低洼地区居民转移', 'sent', CURRENT_TIMESTAMP - INTERVAL '35 hour'),
  ('EP-CP-20260414-001', '排涝值班组', 'sms', '请立即启动排涝泵车部署，翠屏湖北岸涵洞段为重点排涝区域', 'sent', CURRENT_TIMESTAMP - INTERVAL '35 hour'),
  ('EP-CP-20260414-001', '翠屏市防汛指挥部', 'wechat', '翠屏湖流域Ⅱ级响应预案已启动执行，5项应急行动中2项已完成、2项执行中', 'pending', NULL);

-- Plan 3: AI-generated draft — urban waterlogging (moderate risk)
INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-CP-20260415-001',
  '翠屏城区内涝排水预案',
  'moderate',
  '持续暴雨导致翠屏城区多处积水，泵站满负荷运行',
  'draft',
  'session-cp-20260415-001',
  E'# 翠屏城区内涝排水预案\n\n## 风险研判\n\n受持续暴雨影响，翠屏城区出现多处积水点。翠屏城区泵站当前功率 **265kW**，接近260kW满载上限。\n\n**主要积水区域：**\n- 翠屏湖北岸涵洞段：积水深度约40cm\n- 城南低洼居民区：积水深度约25cm\n\n## 建议措施\n\n1. 调配移动排涝泵车增援主要积水点\n2. 疏通城区排水管网堵塞点\n\n## 预计恢复时间\n\n若降雨在6小时内停止，预计12小时内可基本排除积水。',
  CURRENT_TIMESTAMP - INTERVAL '2 hour',
  CURRENT_TIMESTAMP - INTERVAL '2 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status, summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-CP-20260415-001';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status) VALUES
  ('EP-CP-20260415-001', 'ACT-001', 'resource_deploy', '调配移动排涝泵车2台增援城区积水点', 2, '监测调度科', 60, 'pending'),
  ('EP-CP-20260415-001', 'ACT-002', 'engineering', '疏通城区排水管网主要堵塞点', 2, '防汛巡检组', 120, 'pending');

DELETE FROM resource_allocation WHERE plan_id = 'EP-CP-20260415-001';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes) VALUES
  ('EP-CP-20260415-001', '设备', '移动排涝泵车', 2, '翠屏市设备仓库', '城区主要积水点', 30);

DELETE FROM notification_record WHERE plan_id = 'EP-CP-20260415-001';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at) VALUES
  ('EP-CP-20260415-001', '城区社区网格员', 'wechat', '【通知】翠屏城区部分区域积水较深，请引导居民避开积水路段，注意出行安全', 'pending', NULL);

COMMIT;
