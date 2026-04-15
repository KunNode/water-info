-- ============================================================
-- AI Service Demo Data: Cuiping Lake emergency plans
-- Creates tables if not exist, then seeds a compact single-basin
-- demo scenario for PostgreSQL init and manual reseeding.
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

-- ============================================================
-- Plan 1: Historical completed plan
-- ============================================================

INSERT INTO emergency_plan (
    plan_id, plan_name, risk_level, trigger_conditions, status,
    session_id, summary, created_at, updated_at
)
VALUES (
    'EP-CP-DEMO-001',
    '翠屏湖春季防汛预案',
    'moderate',
    '翠屏湖流域进入春季主汛前演练窗口，湖区水位较基准线抬升并需完成防汛准备。',
    'completed',
    'session-cuiping-001',
    E'# 翠屏湖春季防汛预案\n\n## 场景概述\n\n针对翠屏湖流域春季首轮明显降雨过程，预案以**预警前置、物资前置、巡查前置**为核心目标，确保湖区、水库、闸站和城区泵站协同准备到位。\n\n## 已完成措施\n\n1. 完成翠屏北溪、南溪两处上游雨量站巡检\n2. 对翠屏闸启闭设备进行空载联调\n3. 将防汛沙袋、照明设备、移动泵车前置到北岸城区仓位\n\n## 结果\n\n本预案已按演练流程闭环完成，作为历史预案保留供查看和复盘。',
    CURRENT_TIMESTAMP - INTERVAL '120 hour',
    CURRENT_TIMESTAMP - INTERVAL '90 hour'
);

INSERT INTO emergency_action (
    plan_id, action_id, action_type, description, priority,
    responsible_dept, deadline_minutes, status, created_at
)
VALUES
    ('EP-CP-DEMO-001', 'ACT-CP-001', 'inspection', '完成翠屏湖流域 8 个监测站汛前巡检与通信联调', 2, '监测调度科', 180, 'completed', CURRENT_TIMESTAMP - INTERVAL '120 hour'),
    ('EP-CP-DEMO-001', 'ACT-CP-002', 'resource_preposition', '将北岸城区防汛物资和移动泵车前置到预设点位', 2, '防汛巡检组', 240, 'completed', CURRENT_TIMESTAMP - INTERVAL '118 hour');

INSERT INTO resource_allocation (
    plan_id, resource_type, resource_name, quantity,
    source_location, target_location, eta_minutes, created_at
)
VALUES
    ('EP-CP-DEMO-001', '物资', '防汛沙袋', 2400, '翠屏市水务局仓库', '翠屏湖北岸前置点', 35, CURRENT_TIMESTAMP - INTERVAL '119 hour'),
    ('EP-CP-DEMO-001', '设备', '移动排涝泵车', 1, '翠屏市机动设备库', '翠屏城区泵站值守点', 25, CURRENT_TIMESTAMP - INTERVAL '118 hour');

INSERT INTO notification_record (
    plan_id, target, channel, content, status, sent_at, created_at
)
VALUES
    ('EP-CP-DEMO-001', '监测调度科', 'sms', '【演练通知】翠屏湖春季防汛预案已按计划完成，请归档演练记录。', 'sent', CURRENT_TIMESTAMP - INTERVAL '116 hour', CURRENT_TIMESTAMP - INTERVAL '120 hour');

-- ============================================================
-- Plan 2: Current main showcase plan
-- ============================================================

INSERT INTO emergency_plan (
    plan_id, plan_name, risk_level, trigger_conditions, status,
    session_id, summary, created_at, updated_at
)
VALUES (
    'EP-CP-DEMO-002',
    '翠屏湖暴雨Ⅱ级响应预案',
    'high',
    '翠屏湖心水位突破危险线、出湖流量持续高位、上游南溪与北溪出现持续暴雨。',
    'executing',
    'session-cuiping-002',
    E'# 翠屏湖暴雨Ⅱ级响应预案\n\n## 风险研判\n\n当前翠屏湖流域处于本轮过程的洪峰阶段，湖心水位、出湖流量和城区排涝压力同步抬升，综合风险等级为 **高风险（Ⅱ级响应）**。\n\n### 关键观测\n\n| 站点 | 指标 | 当前状态 |\n|------|------|----------|\n| 翠屏湖心水位站 | 湖区水位 | 超危险线，仍在高位运行 |\n| 翠屏出湖流量站 | 出湖流量 | 持续高位泄放 |\n| 翠屏城区泵站 | 泵站功率 | 长时间高负荷运行 |\n| 翠屏南溪雨量站 | 1h 降雨量 | 维持暴雨量级 |\n\n## 执行重点\n\n1. 维持翠屏闸控泄节奏，避免下游行洪压力突增\n2. 对北岸城区低洼片区持续排涝，必要时追加移动泵车\n3. 对湖区、水库、闸站实施滚动会商，每小时更新一次处置态势\n\n> 当前预案为主展示预案，处于执行中状态。',
    CURRENT_TIMESTAMP - INTERVAL '22 hour',
    CURRENT_TIMESTAMP - INTERVAL '1 hour'
);

INSERT INTO emergency_action (
    plan_id, action_id, action_type, description, priority,
    responsible_dept, deadline_minutes, status, created_at
)
VALUES
    ('EP-CP-DEMO-002', 'ACT-CP-101', 'gate_control', '维持翠屏闸高位启闭，按会商结果动态控制出湖流量', 1, '监测调度科', 30, 'in_progress', CURRENT_TIMESTAMP - INTERVAL '22 hour'),
    ('EP-CP-DEMO-002', 'ACT-CP-102', 'drainage', '翠屏城区泵站满负荷运行并对北岸低洼区实施持续排涝', 1, '监测调度科', 60, 'in_progress', CURRENT_TIMESTAMP - INTERVAL '21 hour'),
    ('EP-CP-DEMO-002', 'ACT-CP-103', 'patrol', '防汛巡检组对北岸堤线、水库连接段、闸站设备开展滚动巡查', 2, '防汛巡检组', 90, 'pending', CURRENT_TIMESTAMP - INTERVAL '20 hour');

INSERT INTO resource_allocation (
    plan_id, resource_type, resource_name, quantity,
    source_location, target_location, eta_minutes, created_at
)
VALUES
    ('EP-CP-DEMO-002', '设备', '移动排涝泵车', 2, '翠屏市机动设备库', '翠屏湖北岸城区段', 20, CURRENT_TIMESTAMP - INTERVAL '20 hour'),
    ('EP-CP-DEMO-002', '物资', '防汛挡板', 180, '翠屏市防汛仓库', '北岸低洼街区', 25, CURRENT_TIMESTAMP - INTERVAL '20 hour'),
    ('EP-CP-DEMO-002', '人员', '抢险巡检人员', 24, '翠屏市水务局', '翠屏湖环湖巡查线', 15, CURRENT_TIMESTAMP - INTERVAL '19 hour');

INSERT INTO notification_record (
    plan_id, target, channel, content, status, sent_at, created_at
)
VALUES
    ('EP-CP-DEMO-002', '翠屏市防汛值班群', 'wechat', '【Ⅱ级响应】翠屏湖暴雨处置正在执行，请各值守岗位按小时更新现场情况。', 'sent', CURRENT_TIMESTAMP - INTERVAL '19 hour', CURRENT_TIMESTAMP - INTERVAL '20 hour'),
    ('EP-CP-DEMO-002', '北岸社区网格员', 'sms', '【排涝提示】翠屏湖北岸低洼路段存在积水，请引导居民避开施工与泄洪区域。', 'sent', CURRENT_TIMESTAMP - INTERVAL '18 hour', CURRENT_TIMESTAMP - INTERVAL '20 hour');

-- ============================================================
-- Plan 3: Latest AI draft
-- ============================================================

INSERT INTO emergency_plan (
    plan_id, plan_name, risk_level, trigger_conditions, status,
    session_id, summary, created_at, updated_at
)
VALUES (
    'EP-CP-DEMO-003',
    '翠屏城区内涝排水预案',
    'moderate',
    '翠屏城区北岸泵站持续高负荷运行，局部道路积水超过 20cm。',
    'draft',
    'session-cuiping-003',
    E'# 翠屏城区内涝排水预案\n\n## 风险研判\n\n当前风险集中在翠屏湖北岸城区段。湖区高水位叠加地表汇流，使北岸低洼区出现持续积水，城区泵站接近高负荷上限。\n\n## AI 建议措施\n\n1. 对北岸两处主要积水点追加移动泵车\n2. 采用单向交通管制，预留抢险通道\n3. 对重点地下空间开展排查并同步下发提示通知\n\n> 该预案为 AI 生成草稿，待人工审核后执行。',
    CURRENT_TIMESTAMP - INTERVAL '4 hour',
    CURRENT_TIMESTAMP - INTERVAL '4 hour'
);

INSERT INTO emergency_action (
    plan_id, action_id, action_type, description, priority,
    responsible_dept, deadline_minutes, status, created_at
)
VALUES
    ('EP-CP-DEMO-003', 'ACT-CP-201', 'resource_deploy', '向北岸两处主要积水点增派移动排涝泵车与便携发电设备', 2, '监测调度科', 45, 'pending', CURRENT_TIMESTAMP - INTERVAL '4 hour'),
    ('EP-CP-DEMO-003', 'ACT-CP-202', 'traffic_control', '对北岸积水街区实施单向交通管制，保留抢险通道', 2, '防汛巡检组', 60, 'pending', CURRENT_TIMESTAMP - INTERVAL '4 hour');

INSERT INTO resource_allocation (
    plan_id, resource_type, resource_name, quantity,
    source_location, target_location, eta_minutes, created_at
)
VALUES
    ('EP-CP-DEMO-003', '设备', '便携式排水泵', 4, '翠屏城区应急仓位', '北岸积水点 A / B', 18, CURRENT_TIMESTAMP - INTERVAL '4 hour');

INSERT INTO notification_record (
    plan_id, target, channel, content, status, sent_at, created_at
)
VALUES
    ('EP-CP-DEMO-003', '翠屏城区社区网格员', 'wechat', '【草案提示】如北岸积水继续扩大，请准备开展社区提醒与绕行引导。', 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '4 hour');

COMMIT;
