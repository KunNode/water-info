-- Legacy public schema seed data for local/demo testing
-- Accounts:
--   admin / Admin@123456
--   operator01 / Operator@123456
--   analyst01 / Analyst@123456
--   viewer01 / Viewer@123456
--   locked01 / Locked@123456 (LOCKED)

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- Roles, organizations, departments, users
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

INSERT INTO sys_org (id, code, name, region, created_at, updated_at)
VALUES
  ('90000000-0000-0000-0000-000000000001', 'ORG_HQ', '省级水信息中心', '省级', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('90000000-0000-0000-0000-000000000002', 'ORG_QS', '青山市水务局', '青山市', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('90000000-0000-0000-0000-000000000003', 'ORG_LH', '临河市防汛办', '临河市', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO UPDATE
SET
  name = EXCLUDED.name,
  region = EXCLUDED.region,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at)
SELECT
  '91000000-0000-0000-0000-000000000001',
  o.id,
  '监测管理处',
  NULL,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM sys_org o
WHERE o.code = 'ORG_HQ'
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  parent_id = EXCLUDED.parent_id,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at)
SELECT
  '91000000-0000-0000-0000-000000000002',
  o.id,
  '预警调度处',
  NULL,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM sys_org o
WHERE o.code = 'ORG_HQ'
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  parent_id = EXCLUDED.parent_id,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at)
SELECT
  '91000000-0000-0000-0000-000000000003',
  o.id,
  '青山调度科',
  NULL,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM sys_org o
WHERE o.code = 'ORG_QS'
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  parent_id = EXCLUDED.parent_id,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at)
SELECT
  '91000000-0000-0000-0000-000000000004',
  o.id,
  '青山巡检组',
  '91000000-0000-0000-0000-000000000003',
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM sys_org o
WHERE o.code = 'ORG_QS'
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  parent_id = EXCLUDED.parent_id,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at)
SELECT
  '91000000-0000-0000-0000-000000000005',
  o.id,
  '临河值守组',
  NULL,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM sys_org o
WHERE o.code = 'ORG_LH'
ON CONFLICT (id) DO UPDATE
SET
  org_id = EXCLUDED.org_id,
  name = EXCLUDED.name,
  parent_id = EXCLUDED.parent_id,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_user (
  id, username, password_hash, real_name, phone, email,
  org_id, dept_id, status, last_login_at, password_updated_at,
  created_at, updated_at, deleted
)
SELECT
  '92000000-0000-0000-0000-000000000001',
  'admin',
  crypt('Admin@123456', gen_salt('bf')),
  '系统管理员',
  '13800000001',
  'admin@water.local',
  o.id,
  '91000000-0000-0000-0000-000000000001',
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '2 hour',
  CURRENT_TIMESTAMP - INTERVAL '30 day',
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  0
FROM sys_org o
WHERE o.code = 'ORG_HQ'
ON CONFLICT (username) DO UPDATE
SET
  real_name = EXCLUDED.real_name,
  phone = EXCLUDED.phone,
  email = EXCLUDED.email,
  org_id = EXCLUDED.org_id,
  dept_id = EXCLUDED.dept_id,
  status = EXCLUDED.status,
  deleted = 0,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_user (
  id, username, password_hash, real_name, phone, email,
  org_id, dept_id, status, last_login_at, password_updated_at,
  created_at, updated_at, deleted
)
SELECT
  '92000000-0000-0000-0000-000000000002',
  'operator01',
  crypt('Operator@123456', gen_salt('bf')),
  '值班调度员',
  '13800000002',
  'operator01@water.local',
  o.id,
  '91000000-0000-0000-0000-000000000003',
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '6 hour',
  CURRENT_TIMESTAMP - INTERVAL '15 day',
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  0
FROM sys_org o
WHERE o.code = 'ORG_QS'
ON CONFLICT (username) DO UPDATE
SET
  real_name = EXCLUDED.real_name,
  phone = EXCLUDED.phone,
  email = EXCLUDED.email,
  org_id = EXCLUDED.org_id,
  dept_id = EXCLUDED.dept_id,
  status = EXCLUDED.status,
  deleted = 0,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_user (
  id, username, password_hash, real_name, phone, email,
  org_id, dept_id, status, last_login_at, password_updated_at,
  created_at, updated_at, deleted
)
SELECT
  '92000000-0000-0000-0000-000000000003',
  'analyst01',
  crypt('Analyst@123456', gen_salt('bf')),
  '水情分析员',
  '13800000003',
  'analyst01@water.local',
  o.id,
  '91000000-0000-0000-0000-000000000002',
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '1 day',
  CURRENT_TIMESTAMP - INTERVAL '20 day',
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  0
FROM sys_org o
WHERE o.code = 'ORG_HQ'
ON CONFLICT (username) DO UPDATE
SET
  real_name = EXCLUDED.real_name,
  phone = EXCLUDED.phone,
  email = EXCLUDED.email,
  org_id = EXCLUDED.org_id,
  dept_id = EXCLUDED.dept_id,
  status = EXCLUDED.status,
  deleted = 0,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_user (
  id, username, password_hash, real_name, phone, email,
  org_id, dept_id, status, last_login_at, password_updated_at,
  created_at, updated_at, deleted
)
SELECT
  '92000000-0000-0000-0000-000000000004',
  'viewer01',
  crypt('Viewer@123456', gen_salt('bf')),
  '监管查看员',
  '13800000004',
  'viewer01@water.local',
  o.id,
  '91000000-0000-0000-0000-000000000005',
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '3 day',
  CURRENT_TIMESTAMP - INTERVAL '10 day',
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  0
FROM sys_org o
WHERE o.code = 'ORG_LH'
ON CONFLICT (username) DO UPDATE
SET
  real_name = EXCLUDED.real_name,
  phone = EXCLUDED.phone,
  email = EXCLUDED.email,
  org_id = EXCLUDED.org_id,
  dept_id = EXCLUDED.dept_id,
  status = EXCLUDED.status,
  deleted = 0,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_user (
  id, username, password_hash, real_name, phone, email,
  org_id, dept_id, status, last_login_at, password_updated_at,
  created_at, updated_at, deleted
)
SELECT
  '92000000-0000-0000-0000-000000000005',
  'locked01',
  crypt('Locked@123456', gen_salt('bf')),
  '锁定测试账号',
  '13800000005',
  'locked01@water.local',
  o.id,
  '91000000-0000-0000-0000-000000000004',
  'LOCKED',
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '40 day',
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  0
FROM sys_org o
WHERE o.code = 'ORG_QS'
ON CONFLICT (username) DO UPDATE
SET
  real_name = EXCLUDED.real_name,
  phone = EXCLUDED.phone,
  email = EXCLUDED.email,
  org_id = EXCLUDED.org_id,
  dept_id = EXCLUDED.dept_id,
  status = EXCLUDED.status,
  deleted = 0,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT
  gen_random_uuid()::text,
  u.id,
  r.id,
  CURRENT_TIMESTAMP
FROM sys_user u
JOIN sys_role r ON r.code = 'ADMIN'
WHERE u.username = 'admin'
ON CONFLICT ON CONSTRAINT uk_user_role DO NOTHING;

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT
  gen_random_uuid()::text,
  u.id,
  r.id,
  CURRENT_TIMESTAMP
FROM sys_user u
JOIN sys_role r ON r.code = 'OPERATOR'
WHERE u.username = 'operator01'
ON CONFLICT ON CONSTRAINT uk_user_role DO NOTHING;

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT
  gen_random_uuid()::text,
  u.id,
  r.id,
  CURRENT_TIMESTAMP
FROM sys_user u
JOIN sys_role r ON r.code = 'OPERATOR'
WHERE u.username = 'analyst01'
ON CONFLICT ON CONSTRAINT uk_user_role DO NOTHING;

INSERT INTO sys_user_role (id, user_id, role_id, created_at)
SELECT
  gen_random_uuid()::text,
  u.id,
  r.id,
  CURRENT_TIMESTAMP
FROM sys_user u
JOIN sys_role r ON r.code = 'VIEWER'
WHERE u.username IN ('analyst01', 'viewer01', 'locked01')
ON CONFLICT ON CONSTRAINT uk_user_role DO NOTHING;

-- ============================================================
-- Stations, sensors, thresholds
-- ============================================================

INSERT INTO station (
  id, code, name, type, river_basin, admin_region,
  lat, lon, elevation, status, created_at, updated_at
)
VALUES
  ('93000000-0000-0000-0000-000000000001', 'ST_RAIN_QS_01', '青山北雨量站', 'RAIN_GAUGE', '青山河', '青山市', 31.2456132, 121.4839981, 12.50, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000002', 'ST_WL_QS_01', '青山桥水位站', 'WATER_LEVEL', '青山河', '青山市', 31.2588114, 121.4967162, 10.80, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000003', 'ST_FLOW_QS_01', '青山闸流量站', 'FLOW', '青山河', '青山市', 31.2664139, 121.5070224, 9.70, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000004', 'ST_RES_LH_01', '临河水库站', 'RESERVOIR', '临河', '临河市', 31.1288025, 121.1215908, 26.40, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000005', 'ST_GATE_LH_01', '临河东闸站', 'GATE', '临河', '临河市', 31.1034117, 121.1680475, 18.30, 'MAINTENANCE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('93000000-0000-0000-0000-000000000006', 'ST_PUMP_LH_01', '临河北泵站', 'PUMP_STATION', '临河', '临河市', 31.1429055, 121.1937042, 15.90, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO UPDATE
SET
  name = EXCLUDED.name,
  type = EXCLUDED.type,
  river_basin = EXCLUDED.river_basin,
  admin_region = EXCLUDED.admin_region,
  lat = EXCLUDED.lat,
  lon = EXCLUDED.lon,
  elevation = EXCLUDED.elevation,
  status = EXCLUDED.status,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
)
SELECT
  '94000000-0000-0000-0000-000000000001',
  s.id,
  'RAINFALL',
  'mm',
  300,
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '5 minute',
  '{"vendor":"DemoTech","model":"RG-100","channel":"A1"}'::jsonb,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_RAIN_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  type = EXCLUDED.type,
  unit = EXCLUDED.unit,
  sampling_interval_sec = EXCLUDED.sampling_interval_sec,
  status = EXCLUDED.status,
  last_seen_at = EXCLUDED.last_seen_at,
  meta = EXCLUDED.meta,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
)
SELECT
  '94000000-0000-0000-0000-000000000002',
  s.id,
  'WATER_LEVEL',
  'm',
  60,
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '2 minute',
  '{"vendor":"DemoTech","model":"WL-210","channel":"B1"}'::jsonb,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_WL_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  type = EXCLUDED.type,
  unit = EXCLUDED.unit,
  sampling_interval_sec = EXCLUDED.sampling_interval_sec,
  status = EXCLUDED.status,
  last_seen_at = EXCLUDED.last_seen_at,
  meta = EXCLUDED.meta,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
)
SELECT
  '94000000-0000-0000-0000-000000000003',
  s.id,
  'FLOW',
  'm3/s',
  120,
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '8 minute',
  '{"vendor":"HydroLabs","model":"FM-330","channel":"C1"}'::jsonb,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_FLOW_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  type = EXCLUDED.type,
  unit = EXCLUDED.unit,
  sampling_interval_sec = EXCLUDED.sampling_interval_sec,
  status = EXCLUDED.status,
  last_seen_at = EXCLUDED.last_seen_at,
  meta = EXCLUDED.meta,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
)
SELECT
  '94000000-0000-0000-0000-000000000004',
  s.id,
  'RESERVOIR_LEVEL',
  'm',
  300,
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '15 minute',
  '{"vendor":"HydroLabs","model":"RL-520","channel":"D1"}'::jsonb,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_RES_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  type = EXCLUDED.type,
  unit = EXCLUDED.unit,
  sampling_interval_sec = EXCLUDED.sampling_interval_sec,
  status = EXCLUDED.status,
  last_seen_at = EXCLUDED.last_seen_at,
  meta = EXCLUDED.meta,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
)
SELECT
  '94000000-0000-0000-0000-000000000005',
  s.id,
  'GATE_OPENING',
  'm',
  600,
  'MAINTENANCE',
  CURRENT_TIMESTAMP - INTERVAL '3 hour',
  '{"vendor":"GateSense","model":"GO-88","channel":"E1"}'::jsonb,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_GATE_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  type = EXCLUDED.type,
  unit = EXCLUDED.unit,
  sampling_interval_sec = EXCLUDED.sampling_interval_sec,
  status = EXCLUDED.status,
  last_seen_at = EXCLUDED.last_seen_at,
  meta = EXCLUDED.meta,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO sensor (
  id, station_id, type, unit, sampling_interval_sec, status,
  last_seen_at, meta, created_at, updated_at
)
SELECT
  '94000000-0000-0000-0000-000000000006',
  s.id,
  'PUMP_POWER',
  'kW',
  300,
  'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '4 minute',
  '{"vendor":"PumpEye","model":"PP-12","channel":"F1"}'::jsonb,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_PUMP_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  type = EXCLUDED.type,
  unit = EXCLUDED.unit,
  sampling_interval_sec = EXCLUDED.sampling_interval_sec,
  status = EXCLUDED.status,
  last_seen_at = EXCLUDED.last_seen_at,
  meta = EXCLUDED.meta,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000001',
  s.id,
  'RAINFALL',
  'WARNING',
  30.000,
  60,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_RAIN_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000002',
  s.id,
  'RAINFALL',
  'CRITICAL',
  50.000,
  30,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_RAIN_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000003',
  s.id,
  'WATER_LEVEL',
  'WARNING',
  3.200,
  10,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_WL_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000004',
  s.id,
  'WATER_LEVEL',
  'CRITICAL',
  3.800,
  10,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_WL_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000005',
  s.id,
  'FLOW',
  'WARNING',
  680.000,
  20,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_FLOW_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000006',
  s.id,
  'FLOW',
  'CRITICAL',
  900.000,
  15,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_FLOW_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000007',
  s.id,
  'RESERVOIR_LEVEL',
  'WARNING',
  76.000,
  30,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_RES_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000008',
  s.id,
  'RESERVOIR_LEVEL',
  'CRITICAL',
  80.000,
  30,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_RES_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000009',
  s.id,
  'GATE_OPENING',
  'INFO',
  1.500,
  10,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_GATE_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000010',
  s.id,
  'PUMP_POWER',
  'WARNING',
  220.000,
  15,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_PUMP_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO threshold_rule (
  id, station_id, metric_type, level, threshold_value,
  duration_min, rate_threshold, enabled, created_at, updated_at
)
SELECT
  '95000000-0000-0000-0000-000000000011',
  s.id,
  'PUMP_POWER',
  'CRITICAL',
  260.000,
  15,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM station s
WHERE s.code = 'ST_PUMP_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  threshold_value = EXCLUDED.threshold_value,
  duration_min = EXCLUDED.duration_min,
  rate_threshold = EXCLUDED.rate_threshold,
  enabled = EXCLUDED.enabled,
  updated_at = CURRENT_TIMESTAMP;

-- ============================================================
-- Observations (last 72 hours, hourly)
-- ============================================================

DELETE FROM observation WHERE request_id = 'SEED_V4_OBS_72H';

WITH metric_seed AS (
  SELECT s.id AS station_id, 'RAINFALL'::text AS metric_type, 'mm'::text AS unit, 6.0::numeric AS base, 0.15::numeric AS slope, 11.0::numeric AS wave
  FROM station s WHERE s.code = 'ST_RAIN_QS_01'
  UNION ALL
  SELECT s.id, 'WATER_LEVEL', 'm', 2.55::numeric, 0.01::numeric, 0.52::numeric
  FROM station s WHERE s.code = 'ST_WL_QS_01'
  UNION ALL
  SELECT s.id, 'FLOW', 'm3/s', 520.0::numeric, 3.5::numeric, 95.0::numeric
  FROM station s WHERE s.code = 'ST_FLOW_QS_01'
  UNION ALL
  SELECT s.id, 'RESERVOIR_LEVEL', 'm', 72.0::numeric, 0.04::numeric, 1.6::numeric
  FROM station s WHERE s.code = 'ST_RES_LH_01'
  UNION ALL
  SELECT s.id, 'GATE_OPENING', 'm', 0.85::numeric, 0.01::numeric, 0.45::numeric
  FROM station s WHERE s.code = 'ST_GATE_LH_01'
  UNION ALL
  SELECT s.id, 'PUMP_POWER', 'kW', 160.0::numeric, 0.9::numeric, 36.0::numeric
  FROM station s WHERE s.code = 'ST_PUMP_LH_01'
),
time_seed AS (
  SELECT generate_series(0, 71) AS idx
)
INSERT INTO observation (
  id, station_id, metric_type, value, unit, observed_at,
  quality_flag, source, request_id, created_at
)
SELECT
  gen_random_uuid()::text,
  m.station_id,
  m.metric_type,
  ROUND(GREATEST(0, (m.base + m.slope * t.idx + m.wave * SIN(t.idx::double precision / 3.0)))::numeric, 3),
  m.unit,
  date_trunc('hour', CURRENT_TIMESTAMP) - INTERVAL '71 hour' + (t.idx * INTERVAL '1 hour'),
  CASE
    WHEN (t.idx % 17 = 0) THEN 'SUSPECT'
    WHEN (t.idx % 29 = 0) THEN 'MISSING'
    ELSE 'GOOD'
  END,
  'SEED_GENERATOR',
  'SEED_V4_OBS_72H',
  CURRENT_TIMESTAMP
FROM metric_seed m
CROSS JOIN time_seed t;

-- ============================================================
-- Alarms
-- ============================================================

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '97000000-0000-0000-0000-000000000001',
  s.id,
  'RAINFALL',
  'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '3 hour',
  CURRENT_TIMESTAMP - INTERVAL '20 minute',
  NULL,
  'OPEN',
  '近 1 小时雨量持续超过 50mm',
  NULL,
  NULL,
  NULL,
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '3 hour',
  CURRENT_TIMESTAMP - INTERVAL '20 minute'
FROM station s
WHERE s.code = 'ST_RAIN_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  start_at = EXCLUDED.start_at,
  last_trigger_at = EXCLUDED.last_trigger_at,
  end_at = EXCLUDED.end_at,
  status = EXCLUDED.status,
  message = EXCLUDED.message,
  acknowledged_by = EXCLUDED.acknowledged_by,
  acknowledged_at = EXCLUDED.acknowledged_at,
  closed_by = EXCLUDED.closed_by,
  closed_at = EXCLUDED.closed_at,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '97000000-0000-0000-0000-000000000002',
  s.id,
  'WATER_LEVEL',
  'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '5 hour',
  CURRENT_TIMESTAMP - INTERVAL '2 hour',
  NULL,
  'ACK',
  '水位超过预警阈值 3.2m，已人工确认',
  u.id,
  CURRENT_TIMESTAMP - INTERVAL '100 minute',
  NULL,
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '5 hour',
  CURRENT_TIMESTAMP - INTERVAL '100 minute'
FROM station s
JOIN sys_user u ON u.username = 'operator01'
WHERE s.code = 'ST_WL_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  start_at = EXCLUDED.start_at,
  last_trigger_at = EXCLUDED.last_trigger_at,
  end_at = EXCLUDED.end_at,
  status = EXCLUDED.status,
  message = EXCLUDED.message,
  acknowledged_by = EXCLUDED.acknowledged_by,
  acknowledged_at = EXCLUDED.acknowledged_at,
  closed_by = EXCLUDED.closed_by,
  closed_at = EXCLUDED.closed_at,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '97000000-0000-0000-0000-000000000003',
  s.id,
  'GATE_OPENING',
  'INFO',
  CURRENT_TIMESTAMP - INTERVAL '12 hour',
  CURRENT_TIMESTAMP - INTERVAL '10 hour',
  CURRENT_TIMESTAMP - INTERVAL '9 hour',
  'CLOSED',
  '闸门开启角度达到提示阈值，已恢复正常',
  u1.id,
  CURRENT_TIMESTAMP - INTERVAL '10 hour',
  u2.id,
  CURRENT_TIMESTAMP - INTERVAL '9 hour',
  CURRENT_TIMESTAMP - INTERVAL '12 hour',
  CURRENT_TIMESTAMP - INTERVAL '9 hour'
FROM station s
JOIN sys_user u1 ON u1.username = 'operator01'
JOIN sys_user u2 ON u2.username = 'analyst01'
WHERE s.code = 'ST_GATE_LH_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  start_at = EXCLUDED.start_at,
  last_trigger_at = EXCLUDED.last_trigger_at,
  end_at = EXCLUDED.end_at,
  status = EXCLUDED.status,
  message = EXCLUDED.message,
  acknowledged_by = EXCLUDED.acknowledged_by,
  acknowledged_at = EXCLUDED.acknowledged_at,
  closed_by = EXCLUDED.closed_by,
  closed_at = EXCLUDED.closed_at,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO alarm (
  id, station_id, metric_type, level, start_at, last_trigger_at, end_at,
  status, message, acknowledged_by, acknowledged_at, closed_by, closed_at,
  created_at, updated_at
)
SELECT
  '97000000-0000-0000-0000-000000000004',
  s.id,
  'FLOW',
  'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '90 minute',
  CURRENT_TIMESTAMP - INTERVAL '10 minute',
  NULL,
  'OPEN',
  '瞬时流量接近 700 m3/s，请持续关注',
  NULL,
  NULL,
  NULL,
  NULL,
  CURRENT_TIMESTAMP - INTERVAL '90 minute',
  CURRENT_TIMESTAMP - INTERVAL '10 minute'
FROM station s
WHERE s.code = 'ST_FLOW_QS_01'
ON CONFLICT (id) DO UPDATE
SET
  station_id = EXCLUDED.station_id,
  metric_type = EXCLUDED.metric_type,
  level = EXCLUDED.level,
  start_at = EXCLUDED.start_at,
  last_trigger_at = EXCLUDED.last_trigger_at,
  end_at = EXCLUDED.end_at,
  status = EXCLUDED.status,
  message = EXCLUDED.message,
  acknowledged_by = EXCLUDED.acknowledged_by,
  acknowledged_at = EXCLUDED.acknowledged_at,
  closed_by = EXCLUDED.closed_by,
  closed_at = EXCLUDED.closed_at,
  updated_at = CURRENT_TIMESTAMP;

-- ============================================================
-- Audit logs
-- ============================================================

DELETE FROM sys_audit_log WHERE action LIKE 'SEED_%';

INSERT INTO sys_audit_log (
  id, actor_user_id, actor_username, action,
  target_type, target_id, detail, ip, user_agent, created_at
)
SELECT
  gen_random_uuid()::text,
  u.id,
  u.username,
  'SEED_LOGIN_SUCCESS',
  'AUTH',
  NULL,
  '{"result":"success","scene":"seed-data"}'::jsonb,
  '127.0.0.1',
  'seed-script/1.0',
  CURRENT_TIMESTAMP - INTERVAL '6 hour'
FROM sys_user u
WHERE u.username = 'admin';

INSERT INTO sys_audit_log (
  id, actor_user_id, actor_username, action,
  target_type, target_id, detail, ip, user_agent, created_at
)
SELECT
  gen_random_uuid()::text,
  u.id,
  u.username,
  'SEED_THRESHOLD_UPDATE',
  'THRESHOLD_RULE',
  '95000000-0000-0000-0000-000000000004',
  '{"field":"threshold_value","old":"3.60","new":"3.80"}'::jsonb,
  '10.20.1.11',
  'Chrome/seed',
  CURRENT_TIMESTAMP - INTERVAL '5 hour'
FROM sys_user u
WHERE u.username = 'operator01';

INSERT INTO sys_audit_log (
  id, actor_user_id, actor_username, action,
  target_type, target_id, detail, ip, user_agent, created_at
)
SELECT
  gen_random_uuid()::text,
  u.id,
  u.username,
  'SEED_ALARM_ACK',
  'ALARM',
  '97000000-0000-0000-0000-000000000002',
  '{"status":"ACK"}'::jsonb,
  '10.20.1.11',
  'Chrome/seed',
  CURRENT_TIMESTAMP - INTERVAL '100 minute'
FROM sys_user u
WHERE u.username = 'operator01';

INSERT INTO sys_audit_log (
  id, actor_user_id, actor_username, action,
  target_type, target_id, detail, ip, user_agent, created_at
)
SELECT
  gen_random_uuid()::text,
  u.id,
  u.username,
  'SEED_ALARM_CLOSE',
  'ALARM',
  '97000000-0000-0000-0000-000000000003',
  '{"status":"CLOSED"}'::jsonb,
  '10.20.1.30',
  'Firefox/seed',
  CURRENT_TIMESTAMP - INTERVAL '9 hour'
FROM sys_user u
WHERE u.username = 'analyst01';

COMMIT;
