-- ============================================================
-- V6: Demo scenario seed data — 7-day flood narrative
-- Adds 14 stations (total 20), sensors, thresholds, realistic
-- observations with a Normal→Buildup→Peak→Recession story arc,
-- 16 alarms at various lifecycle stages, and 35 audit log entries.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. New organization and department for Donghu (upstream)
-- ============================================================

INSERT INTO sys_org (id, code, name, region, created_at, updated_at)
VALUES ('90000000-0000-0000-0000-000000000004', 'ORG_DH', '东湖区水务站', '东湖区', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, region = EXCLUDED.region, updated_at = CURRENT_TIMESTAMP;

INSERT INTO sys_dept (id, org_id, name, parent_id, created_at, updated_at)
SELECT 'A6000000-0000-0000-0000-000000000001', o.id, '东湖防汛科', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM sys_org o WHERE o.code = 'ORG_DH'
ON CONFLICT (id) DO UPDATE SET org_id = EXCLUDED.org_id, name = EXCLUDED.name, updated_at = CURRENT_TIMESTAMP;

-- ============================================================
-- 2. Additional stations (14 new, total 20)
-- ============================================================

INSERT INTO station (
  id, code, name, type, river_basin, admin_region,
  lat, lon, elevation, status, created_at, updated_at
)
VALUES
  -- Qingshan (+4)
  ('A6100000-0000-0000-0000-000000000001', 'ST_RAIN_QS_02', '青山南雨量站',     'RAIN_GAUGE',    '青山河', '青山市', 31.2201, 121.4750, 14.20, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000002', 'ST_WL_QS_02',   '青山河口水位站',   'WATER_LEVEL',   '青山河', '青山市', 31.2750, 121.5200,  8.50, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000003', 'ST_FLOW_QS_02', '青山支流流量站',   'FLOW',          '青山河', '青山市', 31.2400, 121.4600, 11.30, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000004', 'ST_PUMP_QS_01', '青山城区泵站',     'PUMP_STATION',  '青山河', '青山市', 31.2550, 121.4900,  9.80, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  -- Linhe (+4)
  ('A6100000-0000-0000-0000-000000000005', 'ST_RAIN_LH_01', '临河西雨量站',     'RAIN_GAUGE',    '临河',   '临河市', 31.1100, 121.0950, 22.60, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000006', 'ST_WL_LH_01',   '临河大桥水位站',   'WATER_LEVEL',   '临河',   '临河市', 31.1200, 121.1450, 20.10, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000007', 'ST_FLOW_LH_01', '临河干流流量站',   'FLOW',          '临河',   '临河市', 31.1150, 121.1600, 19.50, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000008', 'ST_GATE_LH_02', '临河南闸站',       'GATE',          '临河',   '临河市', 31.0900, 121.1500, 17.00, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  -- Donghu (+6)
  ('A6100000-0000-0000-0000-000000000009', 'ST_RAIN_DH_01', '东湖上游雨量站',   'RAIN_GAUGE',    '东湖河', '东湖区', 31.0500, 120.9200, 85.00, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000010', 'ST_RAIN_DH_02', '东湖山区雨量站',   'RAIN_GAUGE',    '东湖河', '东湖区', 31.0200, 120.8800,120.50, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000011', 'ST_WL_DH_01',   '东湖水库上游水位站','WATER_LEVEL',   '东湖河', '东湖区', 31.0650, 120.9500, 68.30, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000012', 'ST_RES_DH_01',  '东湖蓄洪水库站',   'RESERVOIR',     '东湖河', '东湖区', 31.0800, 120.9800, 52.00, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000013', 'ST_FLOW_DH_01', '东湖出库流量站',   'FLOW',          '东湖河', '东湖区', 31.0850, 121.0000, 48.60, 'ACTIVE',      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('A6100000-0000-0000-0000-000000000014', 'ST_GATE_DH_01', '东湖泄洪闸站',     'GATE',          '东湖河', '东湖区', 31.0820, 120.9900, 50.20, 'INACTIVE',    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name, type = EXCLUDED.type, river_basin = EXCLUDED.river_basin,
    admin_region = EXCLUDED.admin_region, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
    elevation = EXCLUDED.elevation, status = EXCLUDED.status, updated_at = CURRENT_TIMESTAMP;

-- ============================================================
-- 3. Sensors for new stations (14 new)
-- ============================================================

-- Helper: insert sensor by station code
INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000001', s.id, 'RAINFALL', 'mm', 300, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '3 minute', '{"vendor":"DemoTech","model":"RG-100","channel":"A2"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_RAIN_QS_02'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000002', s.id, 'WATER_LEVEL', 'm', 60, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '1 minute', '{"vendor":"DemoTech","model":"WL-210","channel":"B2"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_WL_QS_02'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000003', s.id, 'FLOW', 'm3/s', 120, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '6 minute', '{"vendor":"HydroLabs","model":"FM-330","channel":"C2"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_FLOW_QS_02'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000004', s.id, 'PUMP_POWER', 'kW', 300, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '2 minute', '{"vendor":"PumpEye","model":"PP-12","channel":"F2"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_PUMP_QS_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000005', s.id, 'RAINFALL', 'mm', 300, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '4 minute', '{"vendor":"DemoTech","model":"RG-200","channel":"A3"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_RAIN_LH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000006', s.id, 'WATER_LEVEL', 'm', 60, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '2 minute', '{"vendor":"DemoTech","model":"WL-210","channel":"B3"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_WL_LH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000007', s.id, 'FLOW', 'm3/s', 120, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '5 minute', '{"vendor":"HydroLabs","model":"FM-450","channel":"C3"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_FLOW_LH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000008', s.id, 'GATE_OPENING', 'm', 600, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '8 minute', '{"vendor":"GateSense","model":"GO-100","channel":"E2"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_GATE_LH_02'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000009', s.id, 'RAINFALL', 'mm', 300, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '2 minute', '{"vendor":"DemoTech","model":"RG-300","channel":"A4"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_RAIN_DH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000010', s.id, 'RAINFALL', 'mm', 300, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '3 minute', '{"vendor":"DemoTech","model":"RG-300","channel":"A5"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_RAIN_DH_02'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000011', s.id, 'WATER_LEVEL', 'm', 60, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '1 minute', '{"vendor":"HydroLabs","model":"WL-520","channel":"B4"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_WL_DH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000012', s.id, 'RESERVOIR_LEVEL', 'm', 300, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '10 minute', '{"vendor":"HydroLabs","model":"RL-520","channel":"D2"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_RES_DH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000013', s.id, 'FLOW', 'm3/s', 120, 'ACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '7 minute', '{"vendor":"HydroLabs","model":"FM-450","channel":"C4"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_FLOW_DH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

INSERT INTO sensor (id, station_id, type, unit, sampling_interval_sec, status, last_seen_at, meta, created_at, updated_at)
SELECT 'A6200000-0000-0000-0000-000000000014', s.id, 'GATE_OPENING', 'm', 600, 'INACTIVE',
  CURRENT_TIMESTAMP - INTERVAL '2 hour', '{"vendor":"GateSense","model":"GO-88","channel":"E3"}'::jsonb,
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code = 'ST_GATE_DH_01'
ON CONFLICT (id) DO UPDATE SET station_id=EXCLUDED.station_id, type=EXCLUDED.type, unit=EXCLUDED.unit,
  sampling_interval_sec=EXCLUDED.sampling_interval_sec, status=EXCLUDED.status,
  last_seen_at=EXCLUDED.last_seen_at, meta=EXCLUDED.meta, updated_at=CURRENT_TIMESTAMP;

-- ============================================================
-- 4. Threshold rules for new stations (2 per station = 28)
-- ============================================================

-- ST_RAIN_QS_02
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000001', s.id, 'RAINFALL', 'WARNING', 30.000, 60, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_QS_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000002', s.id, 'RAINFALL', 'CRITICAL', 50.000, 30, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_QS_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_WL_QS_02
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000003', s.id, 'WATER_LEVEL', 'WARNING', 3.000, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_WL_QS_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000004', s.id, 'WATER_LEVEL', 'CRITICAL', 3.600, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_WL_QS_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_FLOW_QS_02
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000005', s.id, 'FLOW', 'WARNING', 550.000, 20, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_FLOW_QS_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000006', s.id, 'FLOW', 'CRITICAL', 750.000, 15, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_FLOW_QS_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_PUMP_QS_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000007', s.id, 'PUMP_POWER', 'WARNING', 200.000, 15, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_PUMP_QS_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000008', s.id, 'PUMP_POWER', 'CRITICAL', 250.000, 15, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_PUMP_QS_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_RAIN_LH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000009', s.id, 'RAINFALL', 'WARNING', 25.000, 60, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_LH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000010', s.id, 'RAINFALL', 'CRITICAL', 45.000, 30, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_LH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_WL_LH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000011', s.id, 'WATER_LEVEL', 'WARNING', 4.500, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_WL_LH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000012', s.id, 'WATER_LEVEL', 'CRITICAL', 5.200, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_WL_LH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_FLOW_LH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000013', s.id, 'FLOW', 'WARNING', 600.000, 20, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_FLOW_LH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000014', s.id, 'FLOW', 'CRITICAL', 850.000, 15, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_FLOW_LH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_GATE_LH_02
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000015', s.id, 'GATE_OPENING', 'WARNING', 2.000, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_GATE_LH_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000016', s.id, 'GATE_OPENING', 'CRITICAL', 3.000, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_GATE_LH_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_RAIN_DH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000017', s.id, 'RAINFALL', 'WARNING', 35.000, 60, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000018', s.id, 'RAINFALL', 'CRITICAL', 55.000, 30, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_RAIN_DH_02
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000019', s.id, 'RAINFALL', 'WARNING', 40.000, 60, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_DH_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000020', s.id, 'RAINFALL', 'CRITICAL', 60.000, 30, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RAIN_DH_02' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_WL_DH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000021', s.id, 'WATER_LEVEL', 'WARNING', 5.000, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_WL_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000022', s.id, 'WATER_LEVEL', 'CRITICAL', 6.000, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_WL_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_RES_DH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000023', s.id, 'RESERVOIR_LEVEL', 'WARNING', 48.000, 30, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RES_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000024', s.id, 'RESERVOIR_LEVEL', 'CRITICAL', 50.000, 30, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_RES_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_FLOW_DH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000025', s.id, 'FLOW', 'WARNING', 400.000, 20, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_FLOW_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000026', s.id, 'FLOW', 'CRITICAL', 600.000, 15, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_FLOW_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ST_GATE_DH_01
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000027', s.id, 'GATE_OPENING', 'WARNING', 1.800, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_GATE_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;
INSERT INTO threshold_rule (id, station_id, metric_type, level, threshold_value, duration_min, rate_threshold, enabled, created_at, updated_at)
SELECT 'A6300000-0000-0000-0000-000000000028', s.id, 'GATE_OPENING', 'CRITICAL', 2.500, 10, NULL, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM station s WHERE s.code='ST_GATE_DH_01' ON CONFLICT (id) DO UPDATE SET threshold_value=EXCLUDED.threshold_value, level=EXCLUDED.level, updated_at=CURRENT_TIMESTAMP;

-- ============================================================
-- 5. Observations — 7-day flood narrative for ALL 20 stations
-- ============================================================
-- Phases: Normal (h 0-71), Buildup (h 72-119), Peak (h 120-143), Recession (h 144-167)
-- h=0 corresponds to T-168h, h=167 corresponds to ~now

DELETE FROM observation WHERE request_id = 'SEED_V6_OBS_7D';
DELETE FROM observation WHERE request_id = 'SEED_V4_OBS_72H';

WITH metric_def AS (
  -- station_code, metric_type, unit, base_val, peak_val, lag_hours (upstream=0, mid=6, downstream=12)
  -- RAINFALL stations
  SELECT 'ST_RAIN_QS_01' AS scode, 'RAINFALL' AS mtype, 'mm' AS unit, 3.0 AS base_val, 48.0 AS peak_val, 8 AS lag_h UNION ALL
  SELECT 'ST_RAIN_QS_02',         'RAINFALL',           'mm',          2.5,             52.0,              9          UNION ALL
  SELECT 'ST_RAIN_LH_01',         'RAINFALL',           'mm',          4.0,             42.0,              4          UNION ALL
  SELECT 'ST_RAIN_DH_01',         'RAINFALL',           'mm',          5.0,             58.0,              0          UNION ALL
  SELECT 'ST_RAIN_DH_02',         'RAINFALL',           'mm',          6.0,             65.0,              0          UNION ALL
  -- WATER_LEVEL stations
  SELECT 'ST_WL_QS_01',           'WATER_LEVEL',        'm',           2.20,            3.85,              12         UNION ALL
  SELECT 'ST_WL_QS_02',           'WATER_LEVEL',        'm',           2.00,            3.50,              12         UNION ALL
  SELECT 'ST_WL_LH_01',           'WATER_LEVEL',        'm',           3.50,            5.10,              6          UNION ALL
  SELECT 'ST_WL_DH_01',           'WATER_LEVEL',        'm',           3.80,            5.90,              2          UNION ALL
  -- FLOW stations
  SELECT 'ST_FLOW_QS_01',         'FLOW',               'm3/s',        420.0,           910.0,             12         UNION ALL
  SELECT 'ST_FLOW_QS_02',         'FLOW',               'm3/s',        280.0,           620.0,             11         UNION ALL
  SELECT 'ST_FLOW_LH_01',         'FLOW',               'm3/s',        350.0,           780.0,             6          UNION ALL
  SELECT 'ST_FLOW_DH_01',         'FLOW',               'm3/s',        250.0,           580.0,             2          UNION ALL
  -- RESERVOIR stations
  SELECT 'ST_RES_LH_01',          'RESERVOIR_LEVEL',    'm',           72.0,            79.5,              6          UNION ALL
  SELECT 'ST_RES_DH_01',          'RESERVOIR_LEVEL',    'm',           42.0,            50.5,              2          UNION ALL
  -- GATE stations
  SELECT 'ST_GATE_LH_01',         'GATE_OPENING',       'm',           0.80,            2.60,              6          UNION ALL
  SELECT 'ST_GATE_LH_02',         'GATE_OPENING',       'm',           0.50,            2.30,              6          UNION ALL
  SELECT 'ST_GATE_DH_01',         'GATE_OPENING',       'm',           0.60,            2.10,              2          UNION ALL
  -- PUMP stations
  SELECT 'ST_PUMP_LH_01',         'PUMP_POWER',         'kW',          140.0,           255.0,             8          UNION ALL
  SELECT 'ST_PUMP_QS_01',         'PUMP_POWER',         'kW',          120.0,           240.0,             10
),
time_grid AS (
  SELECT generate_series(0, 167) AS h
),
computed AS (
  SELECT
    m.scode,
    m.mtype,
    m.unit,
    t.h,
    -- effective hour adjusted for upstream/downstream lag
    GREATEST(0, t.h - m.lag_h) AS eff_h,
    m.base_val,
    m.peak_val
  FROM metric_def m
  CROSS JOIN time_grid t
),
valued AS (
  SELECT
    c.*,
    CASE
      -- Phase 1: Normal (eff_h 0-71) — gentle sine around base
      WHEN c.eff_h < 72 THEN
        c.base_val + (c.peak_val - c.base_val) * 0.05 * (1.0 + sin(c.eff_h::double precision * 0.3))
      -- Phase 2: Buildup (eff_h 72-119) — ramp up
      WHEN c.eff_h < 120 THEN
        c.base_val + (c.peak_val - c.base_val) * (0.10 + 0.55 * ((c.eff_h - 72.0) / 48.0))
      -- Phase 3: Peak (eff_h 120-143) — near peak with oscillation
      WHEN c.eff_h < 144 THEN
        c.base_val + (c.peak_val - c.base_val) * (0.65 + 0.35 * sin(((c.eff_h - 120.0) / 24.0) * 3.14159))
      -- Phase 4: Recession (eff_h 144-167) — exponential decay
      ELSE
        c.base_val + (c.peak_val - c.base_val) * (0.65 * exp(-((c.eff_h - 144.0)::double precision / 18.0)))
    END
    -- Add deterministic noise: sin with a prime multiplier unique per station-metric
    + (c.peak_val - c.base_val) * 0.03 * sin(c.h::double precision * 7.13 + length(c.scode)::double precision)
    AS raw_val
  FROM computed c
)
INSERT INTO observation (
  id, station_id, metric_type, value, unit, observed_at,
  quality_flag, source, request_id, created_at
)
SELECT
  gen_random_uuid()::text,
  s.id,
  v.mtype,
  ROUND(GREATEST(0, v.raw_val)::numeric, 3),
  v.unit,
  date_trunc('hour', CURRENT_TIMESTAMP) - INTERVAL '167 hour' + (v.h * INTERVAL '1 hour'),
  CASE
    WHEN (v.h % 23 = 0) THEN 'SUSPECT'
    WHEN (v.h % 37 = 0) THEN 'MISSING'
    ELSE 'GOOD'
  END,
  'SEED_V6_GENERATOR',
  'SEED_V6_OBS_7D',
  CURRENT_TIMESTAMP
FROM valued v
JOIN station s ON s.code = v.scode;

-- ============================================================
-- 6. Alarms — 16 alarms spanning the flood narrative
-- ============================================================

-- Delete old V4 alarms
DELETE FROM alarm WHERE id IN (
  '97000000-0000-0000-0000-000000000001',
  '97000000-0000-0000-0000-000000000002',
  '97000000-0000-0000-0000-000000000003',
  '97000000-0000-0000-0000-000000000004'
);

-- Phase 1: Historical CLOSED alarms
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000001', s.id, 'RAINFALL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '120 hour', CURRENT_TIMESTAMP - INTERVAL '118 hour', CURRENT_TIMESTAMP - INTERVAL '116 hour',
  'CLOSED', '短时降雨超过30mm/h，已恢复正常', u1.id, CURRENT_TIMESTAMP - INTERVAL '119 hour', u2.id, CURRENT_TIMESTAMP - INTERVAL '116 hour',
  CURRENT_TIMESTAMP - INTERVAL '120 hour', CURRENT_TIMESTAMP - INTERVAL '116 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' JOIN sys_user u2 ON u2.username='analyst01' WHERE s.code='ST_RAIN_QS_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000002', s.id, 'WATER_LEVEL', 'INFO',
  CURRENT_TIMESTAMP - INTERVAL '100 hour', CURRENT_TIMESTAMP - INTERVAL '98 hour', CURRENT_TIMESTAMP - INTERVAL '96 hour',
  'CLOSED', '水位接近汛限水位，已回落至安全范围', u1.id, CURRENT_TIMESTAMP - INTERVAL '99 hour', u1.id, CURRENT_TIMESTAMP - INTERVAL '96 hour',
  CURRENT_TIMESTAMP - INTERVAL '100 hour', CURRENT_TIMESTAMP - INTERVAL '96 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' WHERE s.code='ST_WL_LH_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000003', s.id, 'GATE_OPENING', 'INFO',
  CURRENT_TIMESTAMP - INTERVAL '90 hour', CURRENT_TIMESTAMP - INTERVAL '88 hour', CURRENT_TIMESTAMP - INTERVAL '85 hour',
  'CLOSED', '闸门开启角度达到提示阈值，已恢复正常', u1.id, CURRENT_TIMESTAMP - INTERVAL '89 hour', u2.id, CURRENT_TIMESTAMP - INTERVAL '85 hour',
  CURRENT_TIMESTAMP - INTERVAL '90 hour', CURRENT_TIMESTAMP - INTERVAL '85 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' JOIN sys_user u2 ON u2.username='analyst01' WHERE s.code='ST_GATE_LH_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

-- Phase 2: Buildup — ACK and CLOSED
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000004', s.id, 'RAINFALL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '72 hour', CURRENT_TIMESTAMP - INTERVAL '68 hour', NULL,
  'ACK', '上游山区降雨量持续增加，已超过预警阈值35mm/h', u1.id, CURRENT_TIMESTAMP - INTERVAL '70 hour', NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '72 hour', CURRENT_TIMESTAMP - INTERVAL '70 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' WHERE s.code='ST_RAIN_DH_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000005', s.id, 'RAINFALL', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '60 hour', CURRENT_TIMESTAMP - INTERVAL '56 hour', NULL,
  'ACK', '东湖山区特大暴雨，1小时降雨量突破60mm', u1.id, CURRENT_TIMESTAMP - INTERVAL '58 hour', NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '60 hour', CURRENT_TIMESTAMP - INTERVAL '58 hour'
FROM station s JOIN sys_user u1 ON u1.username='analyst01' WHERE s.code='ST_RAIN_DH_02'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000006', s.id, 'WATER_LEVEL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '55 hour', CURRENT_TIMESTAMP - INTERVAL '50 hour', CURRENT_TIMESTAMP - INTERVAL '30 hour',
  'CLOSED', '青山桥水位站水位超过预警线3.2m，经持续监测后回落', u1.id, CURRENT_TIMESTAMP - INTERVAL '52 hour', u2.id, CURRENT_TIMESTAMP - INTERVAL '30 hour',
  CURRENT_TIMESTAMP - INTERVAL '55 hour', CURRENT_TIMESTAMP - INTERVAL '30 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' JOIN sys_user u2 ON u2.username='analyst01' WHERE s.code='ST_WL_QS_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000007', s.id, 'FLOW', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '50 hour', CURRENT_TIMESTAMP - INTERVAL '45 hour', CURRENT_TIMESTAMP - INTERVAL '28 hour',
  'CLOSED', '临河干流流量超过600m³/s预警值，已恢复', u1.id, CURRENT_TIMESTAMP - INTERVAL '48 hour', u1.id, CURRENT_TIMESTAMP - INTERVAL '28 hour',
  CURRENT_TIMESTAMP - INTERVAL '50 hour', CURRENT_TIMESTAMP - INTERVAL '28 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' WHERE s.code='ST_FLOW_LH_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

-- Phase 3: Peak — OPEN and ACK alarms (current emergency)
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000008', s.id, 'RAINFALL', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '36 hour', CURRENT_TIMESTAMP - INTERVAL '2 hour', NULL,
  'OPEN', '青山北站持续暴雨，近1小时累计降雨量超过50mm，已持续36小时', NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '36 hour', CURRENT_TIMESTAMP - INTERVAL '2 hour'
FROM station s WHERE s.code='ST_RAIN_QS_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000009', s.id, 'RAINFALL', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '34 hour', CURRENT_TIMESTAMP - INTERVAL '3 hour', NULL,
  'OPEN', '青山南站暴雨预警，累计降雨量超标', NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '34 hour', CURRENT_TIMESTAMP - INTERVAL '3 hour'
FROM station s WHERE s.code='ST_RAIN_QS_02'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000010', s.id, 'WATER_LEVEL', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '30 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour', NULL,
  'OPEN', '青山桥水位站水位突破危险线3.8m，当前3.87m，仍在上涨', NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '30 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM station s WHERE s.code='ST_WL_QS_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000011', s.id, 'WATER_LEVEL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '28 hour', CURRENT_TIMESTAMP - INTERVAL '4 hour', NULL,
  'ACK', '青山河口水位超过预警线3.0m，已安排加密观测', u1.id, CURRENT_TIMESTAMP - INTERVAL '26 hour', NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '28 hour', CURRENT_TIMESTAMP - INTERVAL '26 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' WHERE s.code='ST_WL_QS_02'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000012', s.id, 'FLOW', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '25 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour', NULL,
  'OPEN', '青山闸流量超过900m³/s危险阈值，当前约915m³/s', NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '25 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM station s WHERE s.code='ST_FLOW_QS_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000013', s.id, 'RESERVOIR_LEVEL', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '20 hour', CURRENT_TIMESTAMP - INTERVAL '4 hour', NULL,
  'OPEN', '临河水库水位超过汛限水位76m，当前78.2m', NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '20 hour', CURRENT_TIMESTAMP - INTERVAL '4 hour'
FROM station s WHERE s.code='ST_RES_LH_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000014', s.id, 'RESERVOIR_LEVEL', 'CRITICAL',
  CURRENT_TIMESTAMP - INTERVAL '18 hour', CURRENT_TIMESTAMP - INTERVAL '2 hour', NULL,
  'OPEN', '东湖蓄洪水库水位逼近50m设计洪水位，需紧急泄洪', NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '18 hour', CURRENT_TIMESTAMP - INTERVAL '2 hour'
FROM station s WHERE s.code='ST_RES_DH_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

-- Phase 3-4: Additional alarms
INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000015', s.id, 'PUMP_POWER', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '15 hour', CURRENT_TIMESTAMP - INTERVAL '6 hour', NULL,
  'ACK', '临河北泵站功率超过220kW预警值，泵组满负荷运行', u1.id, CURRENT_TIMESTAMP - INTERVAL '12 hour', NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '15 hour', CURRENT_TIMESTAMP - INTERVAL '12 hour'
FROM station s JOIN sys_user u1 ON u1.username='operator01' WHERE s.code='ST_PUMP_LH_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

INSERT INTO alarm (id, station_id, metric_type, level, start_at, last_trigger_at, end_at, status, message, acknowledged_by, acknowledged_at, closed_by, closed_at, created_at, updated_at)
SELECT 'A6400000-0000-0000-0000-000000000016', s.id, 'PUMP_POWER', 'WARNING',
  CURRENT_TIMESTAMP - INTERVAL '10 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour', NULL,
  'OPEN', '青山城区泵站功率接近预警阈值200kW，排涝压力大', NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP - INTERVAL '10 hour', CURRENT_TIMESTAMP - INTERVAL '1 hour'
FROM station s WHERE s.code='ST_PUMP_QS_01'
ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, message=EXCLUDED.message, updated_at=CURRENT_TIMESTAMP;

-- ============================================================
-- 7. Audit logs — 35 realistic entries
-- ============================================================

DELETE FROM sys_audit_log WHERE action LIKE 'SEED_%';

-- Day 1-3: Normal operations
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '156 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '150 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'STATION_VIEW', 'STATION', '93000000-0000-0000-0000-000000000001',
  '{"station_code":"ST_RAIN_QS_01"}'::jsonb, '10.20.1.30', 'Mozilla/5.0 (Macintosh; Intel Mac OS X) Firefox/125.0',
  CURRENT_TIMESTAMP - INTERVAL '148 hour' FROM sys_user u WHERE u.username='viewer01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.20', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '144 hour' FROM sys_user u WHERE u.username='analyst01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'THRESHOLD_UPDATE', 'THRESHOLD_RULE', '95000000-0000-0000-0000-000000000003',
  '{"field":"threshold_value","old":"3.00","new":"3.20","reason":"汛前调整"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '140 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'REPORT_EXPORT', 'REPORT', NULL,
  '{"report_type":"daily_summary","date":"2026-03-28"}'::jsonb, '10.20.1.20', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '132 hour' FROM sys_user u WHERE u.username='analyst01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '126 hour' FROM sys_user u WHERE u.username='operator01';

-- Day 4: Storm starts, alarm acks begin
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', 'A6400000-0000-0000-0000-000000000001',
  '{"alarm_level":"WARNING","station":"ST_RAIN_QS_01","message":"短时降雨超标"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '119 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_CLOSE', 'ALARM', 'A6400000-0000-0000-0000-000000000001',
  '{"alarm_level":"WARNING","station":"ST_RAIN_QS_01","close_reason":"降雨已停"}'::jsonb, '10.20.1.20', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '116 hour' FROM sys_user u WHERE u.username='analyst01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '100 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', 'A6400000-0000-0000-0000-000000000002',
  '{"alarm_level":"INFO","station":"ST_WL_LH_01"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '99 hour' FROM sys_user u WHERE u.username='operator01';

-- Day 5: Buildup intensifies
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '78 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', 'A6400000-0000-0000-0000-000000000004',
  '{"alarm_level":"WARNING","station":"ST_RAIN_DH_01","message":"上游持续降雨"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '70 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', 'A6400000-0000-0000-0000-000000000005',
  '{"alarm_level":"CRITICAL","station":"ST_RAIN_DH_02","message":"山区特大暴雨"}'::jsonb, '10.20.1.20', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '58 hour' FROM sys_user u WHERE u.username='analyst01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', 'A6400000-0000-0000-0000-000000000006',
  '{"alarm_level":"WARNING","station":"ST_WL_QS_01"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '52 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'THRESHOLD_UPDATE', 'THRESHOLD_RULE', '95000000-0000-0000-0000-000000000004',
  '{"field":"threshold_value","old":"3.60","new":"3.80","reason":"根据上游来水调高危险阈值"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '50 hour' FROM sys_user u WHERE u.username='admin';

-- Day 6: Peak — emergency operations
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success","scene":"emergency"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '42 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success","scene":"emergency"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '42 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success","scene":"emergency"}'::jsonb, '10.20.1.20', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '41 hour' FROM sys_user u WHERE u.username='analyst01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'STATION_EDIT', 'STATION', 'A6100000-0000-0000-0000-000000000014',
  '{"field":"status","old":"INACTIVE","new":"ACTIVE","reason":"启用泄洪闸站"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '40 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'EMERGENCY_PLAN_CREATE', 'PLAN', 'EP-DEMO-20260403-001',
  '{"plan_name":"青山流域特大暴雨防汛Ⅰ级响应预案","risk_level":"critical","source":"AI_GENERATED"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '36 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'EMERGENCY_PLAN_APPROVE', 'PLAN', 'EP-DEMO-20260403-001',
  '{"plan_name":"青山流域特大暴雨防汛Ⅰ级响应预案","approved_by":"admin"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '35 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'EMERGENCY_PLAN_EXECUTE', 'PLAN', 'EP-DEMO-20260403-001',
  '{"plan_name":"青山流域特大暴雨防汛Ⅰ级响应预案","actions_count":5}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '34 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'RESOURCE_DISPATCH', 'RESOURCE', 'EP-DEMO-20260403-001',
  '{"resource":"移动排涝泵车x3","target":"青山河河口涵洞段","eta_minutes":25}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '33 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'NOTIFICATION_SEND', 'NOTIFICATION', 'EP-DEMO-20260403-001',
  '{"channel":"SMS","targets":"社区网格员、排水值班组","content":"启动防汛Ⅰ级响应"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '33 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', 'A6400000-0000-0000-0000-000000000011',
  '{"alarm_level":"WARNING","station":"ST_WL_QS_02"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '26 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_ACK', 'ALARM', 'A6400000-0000-0000-0000-000000000015',
  '{"alarm_level":"WARNING","station":"ST_PUMP_LH_01"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '12 hour' FROM sys_user u WHERE u.username='operator01';

-- Day 7: Recession — monitoring and closing
INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '8 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_CLOSE', 'ALARM', 'A6400000-0000-0000-0000-000000000006',
  '{"alarm_level":"WARNING","station":"ST_WL_QS_01","close_reason":"水位回落至安全范围"}'::jsonb, '10.20.1.20', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '6 hour' FROM sys_user u WHERE u.username='analyst01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'ALARM_CLOSE', 'ALARM', 'A6400000-0000-0000-0000-000000000007',
  '{"alarm_level":"WARNING","station":"ST_FLOW_LH_01","close_reason":"流量恢复正常"}'::jsonb, '10.20.1.11', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '5 hour' FROM sys_user u WHERE u.username='operator01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'EMERGENCY_PLAN_CREATE', 'PLAN', 'EP-DEMO-20260404-001',
  '{"plan_name":"青山城区内涝排水应急预案","risk_level":"moderate","source":"AI_GENERATED"}'::jsonb, '10.20.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
  CURRENT_TIMESTAMP - INTERVAL '2 hour' FROM sys_user u WHERE u.username='admin';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'REPORT_GENERATE', 'REPORT', NULL,
  '{"report_type":"flood_event_summary","period":"2026-03-28 to 2026-04-04"}'::jsonb, '10.20.1.20', 'Mozilla/5.0 (Macintosh; Intel Mac OS X) Firefox/125.0',
  CURRENT_TIMESTAMP - INTERVAL '1 hour' FROM sys_user u WHERE u.username='analyst01';

INSERT INTO sys_audit_log (id, actor_user_id, actor_username, action, target_type, target_id, detail, ip, user_agent, created_at)
SELECT gen_random_uuid()::text, u.id, u.username, 'LOGIN_SUCCESS', 'AUTH', NULL,
  '{"result":"success"}'::jsonb, '10.20.1.40', 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4) Mobile/15E148 Safari/604.1',
  CURRENT_TIMESTAMP - INTERVAL '30 minute' FROM sys_user u WHERE u.username='admin';

COMMIT;
