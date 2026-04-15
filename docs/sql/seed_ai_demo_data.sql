-- ============================================================
-- AI Service Demo Data: Cuiping Lake (翠屏湖) emergency plans
-- Creates tables if not exist, then seeds 3 demo plans.
-- NOTE: V7__cuiping_lake_demo_data.sql seeds the same data via
--       Flyway. Use this file only for independent AI-table reseeds.
-- ============================================================

BEGIN;

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

CREATE INDEX IF NOT EXISTS idx_emergency_plan_status ON emergency_plan(status);
CREATE INDEX IF NOT EXISTS idx_emergency_plan_risk_level ON emergency_plan(risk_level);
CREATE INDEX IF NOT EXISTS idx_emergency_action_plan_id ON emergency_action(plan_id);
CREATE INDEX IF NOT EXISTS idx_resource_allocation_plan_id ON resource_allocation(plan_id);
CREATE INDEX IF NOT EXISTS idx_notification_record_plan_id ON notification_record(plan_id);

TRUNCATE notification_record, resource_allocation, emergency_action, emergency_plan RESTART IDENTITY CASCADE;

-- ────────────────────────────────────────────────────────────
-- Plan 1: Completed historical plan (moderate risk)
-- ────────────────────────────────────────────────────────────

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
);

INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status) VALUES
  ('EP-CP-20260410-001', 'ACT-001', 'monitoring', '加密翠屏湖心水位站监测频次至每30分钟', 2, '监测调度科', 30, 'completed'),
  ('EP-CP-20260410-001', 'ACT-002', 'patrol', '安排堤防巡查人员8人，重点巡查翠屏湖北岸堤段', 2, '防汛巡检组', 60, 'completed');

INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes) VALUES
  ('EP-CP-20260410-001', '物资', '防汛沙袋', 2000, '翠屏市防汛物资仓库', '翠屏湖北岸', 40);

INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at) VALUES
  ('EP-CP-20260410-001', '监测调度科', 'sms', '【黄色预警】翠屏湖水位超过预警线3.6m，请启动III级应急响应', 'sent', CURRENT_TIMESTAMP - INTERVAL '119 hour');

-- ────────────────────────────────────────────────────────────
-- Plan 2: Currently executing (high risk) — main showcase
-- ────────────────────────────────────────────────────────────

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
);

INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status) VALUES
  ('EP-CP-20260414-001', 'ACT-001', 'evacuation', '组织翠屏湖北岸低洼地区约1500名居民转移至安全地带', 1, '监测调度科', 120, 'completed'),
  ('EP-CP-20260414-001', 'ACT-002', 'gate_control', '翠屏闸全开泄洪，最大泄量约560m³/s', 1, '监测调度科', 30, 'completed'),
  ('EP-CP-20260414-001', 'ACT-003', 'resource_deploy', '调运移动排涝泵车2台增援城区积水点', 1, '监测调度科', 60, 'in_progress'),
  ('EP-CP-20260414-001', 'ACT-004', 'patrol', '抢险队伍60人在翠屏湖北岸堤段24小时值守', 1, '防汛巡检组', 180, 'in_progress'),
  ('EP-CP-20260414-001', 'ACT-005', 'notification', '通过短信、微信发布橙色预警', 2, '监测调度科', 30, 'pending');

INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes) VALUES
  ('EP-CP-20260414-001', '设备', '移动排涝泵车', 2, '翠屏市设备调配中心', '翠屏湖北岸涵洞段', 25),
  ('EP-CP-20260414-001', '物资', '防汛沙袋', 15000, '翠屏市防汛物资储备库', '翠屏湖北岸堤段沿线', 40),
  ('EP-CP-20260414-001', '设备', '冲锋舟', 3, '翠屏市消防救援支队', '翠屏闸附近水域', 30),
  ('EP-CP-20260414-001', '人员', '抢险队员', 60, '翠屏市应急管理局', '翠屏湖北岸堤段', 45);

INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at) VALUES
  ('EP-CP-20260414-001', '翠屏湖北岸社区网格员', 'sms', '【橙色预警】翠屏湖水位超危险线4.15m，请立即组织低洼地区居民转移', 'sent', CURRENT_TIMESTAMP - INTERVAL '35 hour'),
  ('EP-CP-20260414-001', '排涝值班组', 'sms', '请立即启动排涝泵车部署，翠屏湖北岸涵洞段为重点排涝区域', 'sent', CURRENT_TIMESTAMP - INTERVAL '35 hour'),
  ('EP-CP-20260414-001', '翠屏市防汛指挥部', 'wechat', '翠屏湖流域Ⅱ级响应预案已启动执行，5项应急行动中2项已完成、2项执行中', 'pending', NULL);

-- ────────────────────────────────────────────────────────────
-- Plan 3: AI-generated draft — urban waterlogging
-- ────────────────────────────────────────────────────────────

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
);

INSERT INTO emergency_action (plan_id, action_id, action_type, description, priority, responsible_dept, deadline_minutes, status) VALUES
  ('EP-CP-20260415-001', 'ACT-001', 'resource_deploy', '调配移动排涝泵车2台增援城区积水点', 2, '监测调度科', 60, 'pending'),
  ('EP-CP-20260415-001', 'ACT-002', 'engineering', '疏通城区排水管网主要堵塞点', 2, '防汛巡检组', 120, 'pending');

INSERT INTO resource_allocation (plan_id, resource_type, resource_name, quantity, source_location, target_location, eta_minutes) VALUES
  ('EP-CP-20260415-001', '设备', '移动排涝泵车', 2, '翠屏市设备仓库', '城区主要积水点', 30);

INSERT INTO notification_record (plan_id, target, channel, content, status, sent_at) VALUES
  ('EP-CP-20260415-001', '城区社区网格员', 'wechat', '【通知】翠屏城区部分区域积水较深，请引导居民避开积水路段，注意出行安全', 'pending', NULL);

COMMIT;
