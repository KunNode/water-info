-- ============================================================
-- AI Service Demo Data: Emergency Plans, Actions, Resources, Notifications
-- Creates tables if not exist, then seeds demo data.
-- Auto-loaded by PostgreSQL init on first docker-compose up.
-- ============================================================

BEGIN;

-- ────────────────────────────────────────────────────────────
-- Create AI tables (idempotent - same as ensure_plan_tables in database.py)
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS emergency_plan (
    id BIGSERIAL PRIMARY KEY,
    plan_id VARCHAR(64) UNIQUE NOT NULL,
    plan_name VARCHAR(255) NOT NULL,
    risk_level VARCHAR(32) DEFAULT 'unknown',
    trigger_conditions TEXT,
    status VARCHAR(32) DEFAULT 'draft',
    session_id VARCHAR(64),
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emergency_action (
    id BIGSERIAL PRIMARY KEY,
    plan_id VARCHAR(64) NOT NULL REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
    action_id VARCHAR(64) NOT NULL,
    action_type VARCHAR(64),
    description TEXT,
    priority INTEGER DEFAULT 3,
    responsible_dept VARCHAR(128),
    deadline_minutes INTEGER,
    status VARCHAR(32) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_allocation (
    id BIGSERIAL PRIMARY KEY,
    plan_id VARCHAR(64) NOT NULL REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
    resource_type VARCHAR(64),
    resource_name VARCHAR(128),
    quantity INTEGER DEFAULT 1,
    source_location VARCHAR(255),
    target_location VARCHAR(255),
    eta_minutes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notification_record (
    id BIGSERIAL PRIMARY KEY,
    plan_id VARCHAR(64) NOT NULL REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
    target VARCHAR(255),
    channel VARCHAR(32),
    content TEXT,
    status VARCHAR(32) DEFAULT 'pending',
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_emergency_plan_status ON emergency_plan(status);
CREATE INDEX IF NOT EXISTS idx_emergency_plan_risk_level ON emergency_plan(risk_level);
CREATE INDEX IF NOT EXISTS idx_emergency_action_plan_id ON emergency_action(plan_id);
CREATE INDEX IF NOT EXISTS idx_resource_allocation_plan_id ON resource_allocation(plan_id);
CREATE INDEX IF NOT EXISTS idx_notification_record_plan_id ON notification_record(plan_id);

-- ────────────────────────────────────────────────────────────
-- Plan 1: Completed historical plan (moderate risk)
-- ────────────────────────────────────────────────────────────

INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-DEMO-20260401-001',
  '青山河春季洪水应对预案',
  'moderate',
  '青山河水位超过预警线3.2m，持续降雨导致上游来水增加',
  'completed',
  'session-demo-20260401-001',
  E'# 青山河春季洪水应对预案\n\n## 风险研判\n\n受持续降雨影响，青山河水位自3月30日起持续上涨，**青山桥水位站**水位一度达到 **3.35m**，超过预警线3.2m。\n\n- 上游东湖水库来水量增加约30%\n- 青山河流量峰值达到680m³/s\n- 预计未来24小时降雨趋缓\n\n## 气象预报\n\n| 时段 | 降雨量 | 风力 |\n|------|--------|------|\n| 3月31日白天 | 中雨 15-25mm | 3-4级 |\n| 3月31日夜间 | 小雨 5-10mm | 2-3级 |\n| 4月1日 | 阴转多云 | 2级 |\n\n## 应急措施\n\n1. **加密监测**：青山桥水位站观测频次提高至每30分钟一次\n2. **堤防巡查**：安排12人对青山河重点堤段进行不间断巡查\n3. **物资准备**：调运沙袋3000袋至青山河沿线备用\n\n> 本预案于4月1日经评估后结束执行，青山河水位已回落至2.8m安全水位。',
  CURRENT_TIMESTAMP - INTERVAL '120 hour',
  CURRENT_TIMESTAMP - INTERVAL '72 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET
  plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status,
  summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-DEMO-20260401-001';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status, created_at) VALUES
  ('EP-DEMO-20260401-001', 'ACT-001', 'monitoring', '加密青山桥水位站监测频次至每30分钟', 2, '监测管理处', 30, 'completed', CURRENT_TIMESTAMP - INTERVAL '120 hour'),
  ('EP-DEMO-20260401-001', 'ACT-002', 'patrol', '安排堤防巡查人员12人，重点巡查青山河主堤段', 2, '青山巡检组', 60, 'completed', CURRENT_TIMESTAMP - INTERVAL '120 hour');

DELETE FROM resource_allocation WHERE plan_id = 'EP-DEMO-20260401-001';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes, created_at) VALUES
  ('EP-DEMO-20260401-001', '物资', '防汛沙袋', 3000, '青山市防汛物资仓库', '青山河沿线', 40, CURRENT_TIMESTAMP - INTERVAL '120 hour');

DELETE FROM notification_record WHERE plan_id = 'EP-DEMO-20260401-001';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at, created_at) VALUES
  ('EP-DEMO-20260401-001', '青山调度科', 'sms', '【黄色预警】青山河水位超过预警线3.2m，请启动III级应急响应', 'sent', CURRENT_TIMESTAMP - INTERVAL '119 hour', CURRENT_TIMESTAMP - INTERVAL '120 hour');

-- ────────────────────────────────────────────────────────────
-- Plan 2: Approved plan ready for activation (high risk)
-- ────────────────────────────────────────────────────────────

INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-DEMO-20260402-001',
  '临河水库超汛限水位应急预案',
  'high',
  '临河水库水位超过汛限水位76m，上游持续来水，预计继续上涨',
  'approved',
  'session-demo-20260402-001',
  E'# 临河水库超汛限水位应急预案\n\n## 风险研判\n\n临河水库水位自4月1日起持续上涨，当前水位 **77.8m**，已超过汛限水位76m。\n\n**关键风险指标：**\n- 水库蓄水量较汛限多出约 **120万m³**\n- 上游东湖河来水流量约 **450m³/s**，较常年同期偏多60%\n- 24小时内预计继续来水约 **80万m³**\n\n## 水情分析\n\n| 指标 | 当前值 | 预警值 | 危险值 |\n|------|--------|--------|--------|\n| 水库水位 | 77.8m | 76.0m | 80.0m |\n| 入库流量 | 450m³/s | 400m³/s | 600m³/s |\n| 出库流量 | 280m³/s | - | - |\n\n## 应急措施\n\n1. **加大泄洪**：开启临河东闸站泄洪闸，将出库流量提高至400m³/s\n2. **下游预警**：通知下游临河市沿岸居民做好防汛准备\n3. **值班加强**：安排24小时不间断值守，每小时报告水位变化\n\n> **注意**：如水位继续上涨至79m以上，需启动超标准洪水应急预案。',
  CURRENT_TIMESTAMP - INTERVAL '72 hour',
  CURRENT_TIMESTAMP - INTERVAL '48 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET
  plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status,
  summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-DEMO-20260402-001';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status, created_at) VALUES
  ('EP-DEMO-20260402-001', 'ACT-001', 'gate_control', '开启临河东闸泄洪闸，出库流量提高至400m³/s', 1, '临河值守组', 30, 'pending', CURRENT_TIMESTAMP - INTERVAL '72 hour'),
  ('EP-DEMO-20260402-001', 'ACT-002', 'notification', '通知下游临河市沿岸居民做好防汛准备', 1, '预警调度处', 45, 'pending', CURRENT_TIMESTAMP - INTERVAL '72 hour'),
  ('EP-DEMO-20260402-001', 'ACT-003', 'monitoring', '安排24小时不间断值守，每小时报告水位变化', 2, '临河值守组', 60, 'pending', CURRENT_TIMESTAMP - INTERVAL '72 hour');

DELETE FROM resource_allocation WHERE plan_id = 'EP-DEMO-20260402-001';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes, created_at) VALUES
  ('EP-DEMO-20260402-001', '设备', '移动排涝泵车', 2, '临河市设备仓库', '临河水库下游泄洪道', 35, CURRENT_TIMESTAMP - INTERVAL '72 hour'),
  ('EP-DEMO-20260402-001', '物资', '防汛沙袋', 5000, '临河市防汛物资仓库', '临河水库大坝段', 40, CURRENT_TIMESTAMP - INTERVAL '72 hour');

DELETE FROM notification_record WHERE plan_id = 'EP-DEMO-20260402-001';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at, created_at) VALUES
  ('EP-DEMO-20260402-001', '临河市防汛办', 'sms', '【橙色预警】临河水库水位超汛限76m，当前77.8m，请启动II级应急响应', 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '72 hour'),
  ('EP-DEMO-20260402-001', '沿岸社区网格员', 'wechat', '【防汛通知】临河水库将加大泄洪，请通知沿岸居民远离河道', 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '72 hour');

-- ────────────────────────────────────────────────────────────
-- Plan 3: Currently executing (critical risk) — main showcase
-- ────────────────────────────────────────────────────────────

INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-DEMO-20260403-001',
  '青山流域特大暴雨防汛Ⅰ级响应预案',
  'critical',
  '青山流域持续特大暴雨，多站水位超危险线，流量超历史同期',
  'executing',
  'session-demo-20260403-001',
  E'# 青山流域特大暴雨防汛Ⅰ级响应预案\n\n## 风险研判\n\n**综合风险等级：极高（I级响应）**\n\n受西太平洋副热带高压异常北抬影响，青山流域自4月2日起遭遇持续强降雨过程，多项水文指标突破预警阈值。\n\n### 关键数据\n\n| 监测站 | 指标 | 当前值 | 预警值 | 危险值 | 状态 |\n|--------|------|--------|--------|--------|------|\n| 青山北雨量站 | 1h降雨量 | 52mm | 30mm | 50mm | **超危险** |\n| 青山桥水位站 | 水位 | 3.87m | 3.2m | 3.8m | **超危险** |\n| 青山闸流量站 | 流量 | 915m³/s | 680m³/s | 900m³/s | **超危险** |\n| 临河水库 | 库水位 | 78.2m | 76.0m | 80.0m | 超预警 |\n| 东湖蓄洪水库 | 库水位 | 49.8m | 48.0m | 50.0m | 超预警 |\n\n### 气象展望\n\n未来12小时仍有**大到暴雨**（30-60mm），之后逐步减弱。预计洪峰将在6-8小时内通过青山河城区段。\n\n## 应急行动\n\n### 一、人员疏散\n- 立即组织青山河沿岸低洼地区 **约3000名居民** 转移至安全地带\n- 启用青山中学、青山体育馆作为临时安置点\n\n### 二、工程措施\n- 青山闸全开泄洪，**最大泄量约1000m³/s**\n- 青山城区泵站满负荷运行，排涝能力 **240m³/h**\n- 调运移动排涝泵车3台增援城区积水点\n\n### 三、抢险救援\n- 抢险队伍100人在青山河主堤段值守\n- 冲锋舟5艘在青山桥附近待命\n\n### 四、信息发布\n- 通过短信、微信、广播向辖区居民发布红色预警\n- 市防汛指挥部每2小时发布水情通报\n\n> **当前进度**：人员疏散和工程调度已启动，预计2小时内完成主要行动部署。',
  CURRENT_TIMESTAMP - INTERVAL '36 hour',
  CURRENT_TIMESTAMP - INTERVAL '1 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET
  plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status,
  summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-DEMO-20260403-001';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status, created_at) VALUES
  ('EP-DEMO-20260403-001', 'ACT-001', 'evacuation', '组织青山河沿岸低洼地区约3000名居民转移至安全地带', 1, '青山调度科', 120, 'completed', CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', 'ACT-002', 'gate_control', '青山闸全开泄洪，最大泄量约1000m³/s', 1, '青山调度科', 30, 'completed', CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', 'ACT-003', 'resource_deploy', '调运移动排涝泵车3台增援城区积水点', 1, '预警调度处', 60, 'in_progress', CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', 'ACT-004', 'patrol', '抢险队伍100人在青山河主堤段24小时值守', 1, '青山巡检组', 180, 'in_progress', CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', 'ACT-005', 'notification', '通过短信、微信、广播发布红色预警', 2, '预警调度处', 30, 'pending', CURRENT_TIMESTAMP - INTERVAL '36 hour');

DELETE FROM resource_allocation WHERE plan_id = 'EP-DEMO-20260403-001';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes, created_at) VALUES
  ('EP-DEMO-20260403-001', '设备', '移动排涝泵车', 3, '市级设备调配中心', '青山河河口涵洞段', 25, CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', '物资', '防汛沙袋', 20000, '市级防汛物资储备库', '青山河主堤沿线', 40, CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', '设备', '冲锋舟', 5, '消防救援支队', '青山桥附近水域', 30, CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', '人员', '抢险队员', 100, '青山市应急管理局', '青山河主堤段', 45, CURRENT_TIMESTAMP - INTERVAL '36 hour');

DELETE FROM notification_record WHERE plan_id = 'EP-DEMO-20260403-001';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at, created_at) VALUES
  ('EP-DEMO-20260403-001', '青山河沿岸社区网格员', 'sms', '【红色预警】青山河水位超危险线3.8m，请立即组织低洼地区居民转移', 'sent', CURRENT_TIMESTAMP - INTERVAL '35 hour', CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', '排涝值班组', 'radio', '请立即启动排涝泵车部署，青山河河口涵洞段为重点排涝区域，每15分钟汇报一次进展', 'sent', CURRENT_TIMESTAMP - INTERVAL '35 hour', CURRENT_TIMESTAMP - INTERVAL '36 hour'),
  ('EP-DEMO-20260403-001', '市防汛指挥部', 'wechat', '青山流域Ⅰ级响应预案已启动执行，5项应急行动中2项已完成、2项执行中', 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '36 hour');

-- ────────────────────────────────────────────────────────────
-- Plan 4: Draft from AI analysis (high risk)
-- ────────────────────────────────────────────────────────────

INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-DEMO-20260403-002',
  '东湖蓄洪水库泄洪预案',
  'high',
  '东湖蓄洪水库水位逼近50m设计洪水位，需实施紧急泄洪',
  'draft',
  'session-demo-20260403-002',
  E'# 东湖蓄洪水库泄洪预案\n\n## 风险研判\n\n东湖蓄洪水库水位已达 **49.8m**，距设计洪水位50m仅差0.2m。上游山区仍有中到大雨，预计未来6小时入库流量维持在500m³/s以上。\n\n**若不紧急泄洪，水库将在3-5小时内达到设计洪水位。**\n\n## 建议措施\n\n1. **开启东湖泄洪闸站**：泄洪流量控制在300-400m³/s\n2. **下游预警**：提前2小时通知下游临河市做好防范\n3. **堤防加固**：对泄洪道两侧堤防实施临时加固\n\n## 风险提示\n\n- 泄洪将导致下游临河干流流量增加约200m³/s\n- 需与临河水库泄洪协调，避免洪峰叠加',
  CURRENT_TIMESTAMP - INTERVAL '12 hour',
  CURRENT_TIMESTAMP - INTERVAL '12 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET
  plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status,
  summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-DEMO-20260403-002';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status, created_at) VALUES
  ('EP-DEMO-20260403-002', 'ACT-001', 'gate_control', '开启东湖泄洪闸站，泄洪流量300-400m³/s', 1, '东湖防汛科', 30, 'pending', CURRENT_TIMESTAMP - INTERVAL '12 hour'),
  ('EP-DEMO-20260403-002', 'ACT-002', 'notification', '提前2小时通知下游临河市做好防范', 1, '预警调度处', 120, 'pending', CURRENT_TIMESTAMP - INTERVAL '12 hour'),
  ('EP-DEMO-20260403-002', 'ACT-003', 'engineering', '对泄洪道两侧堤防实施临时加固', 2, '东湖防汛科', 180, 'pending', CURRENT_TIMESTAMP - INTERVAL '12 hour');

DELETE FROM resource_allocation WHERE plan_id = 'EP-DEMO-20260403-002';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes, created_at) VALUES
  ('EP-DEMO-20260403-002', '物资', '编织袋', 8000, '东湖区防汛仓库', '东湖水库泄洪道两侧', 30, CURRENT_TIMESTAMP - INTERVAL '12 hour'),
  ('EP-DEMO-20260403-002', '人员', '抢险队员', 40, '东湖区应急救援队', '东湖水库大坝段', 25, CURRENT_TIMESTAMP - INTERVAL '12 hour');

DELETE FROM notification_record WHERE plan_id = 'EP-DEMO-20260403-002';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at, created_at) VALUES
  ('EP-DEMO-20260403-002', '临河市防汛办', 'sms', '【紧急通知】东湖水库将于2小时内实施泄洪，泄洪流量300-400m³/s，请做好下游防范', 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '12 hour'),
  ('EP-DEMO-20260403-002', '东湖防汛科', 'radio', '请立即安排人员到位，准备开闸泄洪，注意安全', 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '12 hour');

-- ────────────────────────────────────────────────────────────
-- Plan 5: Latest AI draft (moderate risk)
-- ────────────────────────────────────────────────────────────

INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, created_at, updated_at)
VALUES (
  'EP-DEMO-20260404-001',
  '青山城区内涝排水应急预案',
  'moderate',
  '持续暴雨导致青山城区多处积水，泵站满负荷运行',
  'draft',
  'session-demo-20260404-001',
  E'# 青山城区内涝排水应急预案\n\n## 风险研判\n\n受持续暴雨影响，青山城区出现多处积水点。青山城区泵站当前功率 **235kW**，接近250kW满载上限。\n\n**主要积水区域：**\n- 青山河河口涵洞段：积水深度约40cm\n- 城南低洼居民区：积水深度约25cm\n\n## 建议措施\n\n1. 调配移动排涝泵车增援主要积水点\n2. 疏通城区排水管网堵塞点\n\n## 预计恢复时间\n\n若降雨在6小时内停止，预计12小时内可基本排除积水。',
  CURRENT_TIMESTAMP - INTERVAL '2 hour',
  CURRENT_TIMESTAMP - INTERVAL '2 hour'
)
ON CONFLICT (plan_id) DO UPDATE SET
  plan_name=EXCLUDED.plan_name, risk_level=EXCLUDED.risk_level, status=EXCLUDED.status,
  summary=EXCLUDED.summary, updated_at=EXCLUDED.updated_at;

DELETE FROM emergency_action WHERE plan_id = 'EP-DEMO-20260404-001';
INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status, created_at) VALUES
  ('EP-DEMO-20260404-001', 'ACT-001', 'resource_deploy', '调配移动排涝泵车2台增援城区积水点', 2, '青山调度科', 60, 'pending', CURRENT_TIMESTAMP - INTERVAL '2 hour'),
  ('EP-DEMO-20260404-001', 'ACT-002', 'engineering', '疏通城区排水管网主要堵塞点', 2, '青山巡检组', 120, 'pending', CURRENT_TIMESTAMP - INTERVAL '2 hour');

DELETE FROM resource_allocation WHERE plan_id = 'EP-DEMO-20260404-001';
INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes, created_at) VALUES
  ('EP-DEMO-20260404-001', '设备', '移动排涝泵车', 2, '青山市设备仓库', '城区主要积水点', 30, CURRENT_TIMESTAMP - INTERVAL '2 hour');

DELETE FROM notification_record WHERE plan_id = 'EP-DEMO-20260404-001';
INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at, created_at) VALUES
  ('EP-DEMO-20260404-001', '城区社区网格员', 'wechat', '【通知】城区部分区域积水较深，请引导居民避开积水路段，注意出行安全', 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '2 hour');

COMMIT;
