-- ==============================================================
-- 智慧水务管理系统 — 数据库表结构（ER 图用）
-- 共两个 Schema：
--   public          — Java 后端实际使用的业务表（主）
--   water_info      — 新版标准化 Schema（扩展/分析用）
-- ==============================================================


-- ==============================================================
-- SCHEMA: public（Java 后端主用表）
-- ==============================================================


-- 机构表
CREATE TABLE sys_org (
    id          VARCHAR(36) PRIMARY KEY,
    name        VARCHAR(128) NOT NULL,
    code        VARCHAR(64)  NOT NULL UNIQUE,
    region      VARCHAR(128),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 部门表
CREATE TABLE sys_dept (
    id          VARCHAR(36) PRIMARY KEY,
    org_id      VARCHAR(36)  NOT NULL REFERENCES sys_org(id) ON DELETE CASCADE,
    name        VARCHAR(128) NOT NULL,
    parent_id   VARCHAR(36)  REFERENCES sys_dept(id) ON DELETE SET NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 用户表
CREATE TABLE sys_user (
    id                  VARCHAR(36) PRIMARY KEY,
    username            VARCHAR(64)  NOT NULL UNIQUE,
    password_hash       VARCHAR(256) NOT NULL,
    real_name           VARCHAR(64),
    phone               VARCHAR(32),
    email               VARCHAR(128),
    org_id              VARCHAR(36)  REFERENCES sys_org(id)  ON DELETE SET NULL,
    dept_id             VARCHAR(36)  REFERENCES sys_dept(id) ON DELETE SET NULL,
    status              VARCHAR(16)  NOT NULL DEFAULT 'ACTIVE'
                            CHECK (status IN ('ACTIVE','DISABLED','LOCKED')),
    last_login_at       TIMESTAMP,
    password_updated_at TIMESTAMP,
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted             INTEGER      NOT NULL DEFAULT 0
);

-- 角色表（ADMIN / OPERATOR / VIEWER）
CREATE TABLE sys_role (
    id          VARCHAR(36) PRIMARY KEY,
    code        VARCHAR(32)  NOT NULL UNIQUE
                    CHECK (code IN ('ADMIN','OPERATOR','VIEWER')),
    name        VARCHAR(64)  NOT NULL,
    description TEXT,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 用户-角色关联
CREATE TABLE sys_user_role (
    id         VARCHAR(36) PRIMARY KEY,
    user_id    VARCHAR(36) NOT NULL REFERENCES sys_user(id) ON DELETE CASCADE,
    role_id    VARCHAR(36) NOT NULL REFERENCES sys_role(id) ON DELETE CASCADE,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_role UNIQUE (user_id, role_id)
);

-- 操作审计日志
CREATE TABLE sys_audit_log (
    id             VARCHAR(36) PRIMARY KEY,
    actor_user_id  VARCHAR(36) REFERENCES sys_user(id) ON DELETE SET NULL,
    actor_username VARCHAR(64),
    action         VARCHAR(64)  NOT NULL,
    target_type    VARCHAR(64),
    target_id      VARCHAR(36),
    detail         JSONB,
    ip             VARCHAR(64),
    user_agent     VARCHAR(512),
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 监测站
CREATE TABLE station (
    id           VARCHAR(36) PRIMARY KEY,
    code         VARCHAR(64)  NOT NULL UNIQUE,
    name         VARCHAR(128) NOT NULL,
    type         VARCHAR(32)  NOT NULL
                     CHECK (type IN ('RAIN_GAUGE','WATER_LEVEL','FLOW',
                                     'RESERVOIR','GATE','PUMP_STATION','OTHER')),
    river_basin  VARCHAR(128),
    admin_region VARCHAR(128),
    lat          DECIMAL(10,7),
    lon          DECIMAL(10,7),
    elevation    DECIMAL(10,2),
    status       VARCHAR(16)  NOT NULL DEFAULT 'ACTIVE'
                     CHECK (status IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 传感器
CREATE TABLE sensor (
    id                   VARCHAR(36) PRIMARY KEY,
    station_id           VARCHAR(36) NOT NULL REFERENCES station(id) ON DELETE CASCADE,
    type                 VARCHAR(32) NOT NULL,
    unit                 VARCHAR(32),
    sampling_interval_sec INTEGER   DEFAULT 300,
    status               VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
                             CHECK (status IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    last_seen_at         TIMESTAMP,
    meta                 JSONB,
    created_at           TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 水文观测数据
CREATE TABLE observation (
    id           VARCHAR(36) PRIMARY KEY,
    station_id   VARCHAR(36)    NOT NULL REFERENCES station(id) ON DELETE CASCADE,
    metric_type  VARCHAR(32)    NOT NULL
                     CHECK (metric_type IN ('RAINFALL','WATER_LEVEL','FLOW',
                                            'RESERVOIR_LEVEL','GATE_OPENING','PUMP_POWER')),
    value        DECIMAL(18,6)  NOT NULL,
    unit         VARCHAR(32),
    observed_at  TIMESTAMP      NOT NULL,
    quality_flag VARCHAR(16)    NOT NULL DEFAULT 'GOOD'
                     CHECK (quality_flag IN ('GOOD','BAD','SUSPECT','MISSING')),
    source       VARCHAR(64),
    request_id   VARCHAR(64),
    created_at   TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 阈值规则
CREATE TABLE threshold_rule (
    id               VARCHAR(36) PRIMARY KEY,
    station_id       VARCHAR(36)    NOT NULL REFERENCES station(id) ON DELETE CASCADE,
    metric_type      VARCHAR(32)    NOT NULL
                         CHECK (metric_type IN ('RAINFALL','WATER_LEVEL','FLOW',
                                                'RESERVOIR_LEVEL','GATE_OPENING','PUMP_POWER')),
    level            VARCHAR(16)    NOT NULL CHECK (level IN ('INFO','WARNING','CRITICAL')),
    threshold_value  DECIMAL(18,6)  NOT NULL,
    duration_min     INTEGER,
    rate_threshold   DECIMAL(18,6),
    enabled          BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 告警事件
CREATE TABLE alarm (
    id                VARCHAR(36) PRIMARY KEY,
    station_id        VARCHAR(36) NOT NULL REFERENCES station(id) ON DELETE CASCADE,
    metric_type       VARCHAR(32) NOT NULL
                          CHECK (metric_type IN ('RAINFALL','WATER_LEVEL','FLOW',
                                                 'RESERVOIR_LEVEL','GATE_OPENING','PUMP_POWER')),
    level             VARCHAR(16) NOT NULL CHECK (level IN ('INFO','WARNING','CRITICAL')),
    start_at          TIMESTAMP   NOT NULL,
    last_trigger_at   TIMESTAMP   NOT NULL,
    end_at            TIMESTAMP,
    status            VARCHAR(16) NOT NULL DEFAULT 'OPEN'
                          CHECK (status IN ('OPEN','ACK','CLOSED')),
    message           TEXT,
    acknowledged_by   VARCHAR(36) REFERENCES sys_user(id) ON DELETE SET NULL,
    acknowledged_at   TIMESTAMP,
    closed_by         VARCHAR(36) REFERENCES sys_user(id) ON DELETE SET NULL,
    closed_at         TIMESTAMP,
    created_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ==============================================================
-- SCHEMA: water_info（标准化扩展 Schema）
-- ==============================================================

-- 行政/流域区域层级
CREATE TABLE water_info.station_region (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(32) NOT NULL UNIQUE,
    name        VARCHAR(128) NOT NULL,
    parent_id   UUID        REFERENCES water_info.station_region(id) ON DELETE SET NULL,
    region_type VARCHAR(32) DEFAULT 'ADMIN'
                    CHECK (region_type IN ('ADMIN','BASIN','CUSTOM')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 监测站（标准化）
CREATE TABLE water_info.station (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(64) NOT NULL UNIQUE,
    name            VARCHAR(128) NOT NULL,
    station_type    VARCHAR(32) NOT NULL
                        CHECK (station_type IN ('RIVER','RESERVOIR','GATE','RAIN')),
    status          VARCHAR(16) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive','maintenance')),
    latitude        NUMERIC(10,7),
    longitude       NUMERIC(10,7),
    address         VARCHAR(255),
    region_id       UUID        REFERENCES water_info.station_region(id),
    station_profile JSONB,
    sort_order      INT         DEFAULT 0,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 站点联系人
CREATE TABLE water_info.station_contact (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id UUID        NOT NULL REFERENCES water_info.station(id) ON DELETE CASCADE,
    name       VARCHAR(64) NOT NULL,
    role       VARCHAR(32),
    phone      VARCHAR(32),
    email      VARCHAR(128),
    is_primary BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 传感器类型
CREATE TABLE water_info.sensor_type (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(64) NOT NULL UNIQUE,
    name        VARCHAR(128) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 传感器（标准化）
CREATE TABLE water_info.sensor (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id       UUID        NOT NULL REFERENCES water_info.station(id)      ON DELETE CASCADE,
    sensor_type_id   UUID        NOT NULL REFERENCES water_info.sensor_type(id),
    code             VARCHAR(64) NOT NULL UNIQUE,
    name             VARCHAR(128) NOT NULL,
    status           VARCHAR(16) NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active','inactive','maintenance')),
    installed_at     TIMESTAMPTZ,
    removed_at       TIMESTAMPTZ,
    calibration_date TIMESTAMPTZ,
    metadata         JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 计量单位
CREATE TABLE water_info.unit (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code       VARCHAR(16) NOT NULL UNIQUE,
    name       VARCHAR(64) NOT NULL,
    symbol     VARCHAR(16),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 指标定义
CREATE TABLE water_info.metric (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code                 VARCHAR(32) NOT NULL UNIQUE,
    name                 VARCHAR(64) NOT NULL,
    unit_id              UUID        NOT NULL REFERENCES water_info.unit(id),
    value_type           VARCHAR(16) NOT NULL DEFAULT 'number'
                             CHECK (value_type IN ('number','integer')),
    precision            SMALLINT,
    valid_min            NUMERIC(18,6),
    valid_max            NUMERIC(18,6),
    aggregatable         BOOLEAN     NOT NULL DEFAULT TRUE,
    default_aggregation  VARCHAR(16)
                             CHECK (default_aggregation IN ('sum','avg','max','min','last','count')),
    description          TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 数据质量等级
CREATE TABLE water_info.data_quality (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(32) NOT NULL UNIQUE,
    name        VARCHAR(64) NOT NULL,
    description TEXT,
    severity    VARCHAR(16) DEFAULT 'info'
                    CHECK (severity IN ('info','warning','error')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 数据接入源
CREATE TABLE water_info.ingest_source (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code                  VARCHAR(64) NOT NULL UNIQUE,
    name                  VARCHAR(128) NOT NULL,
    type                  VARCHAR(16) NOT NULL
                              CHECK (type IN ('api','batch','manual','sensor')),
    auth_type             VARCHAR(32) DEFAULT 'none'
                              CHECK (auth_type IN ('none','api_key','oauth2','basic','signature')),
    credentials_encrypted TEXT,
    rate_limit_per_minute INT,
    contact_name          VARCHAR(128),
    contact_phone         VARCHAR(32),
    contact_email         VARCHAR(128),
    status                VARCHAR(16) NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active','inactive','suspended')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 批量导入批次
CREATE TABLE water_info.observation_batch (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id               UUID        NOT NULL REFERENCES water_info.ingest_source(id),
    idempotency_key         VARCHAR(128),
    source_request_id       VARCHAR(128),
    payload_hash            VARCHAR(128),
    received_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_started_at   TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    record_count            INT         NOT NULL DEFAULT 0,
    accepted_count          INT         NOT NULL DEFAULT 0,
    rejected_count          INT         NOT NULL DEFAULT 0,
    status                  VARCHAR(16) NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','processing','accepted',
                                                  'rejected','partial','failed')),
    error_summary           JSONB,
    source_ip               VARCHAR(45),
    user_agent              VARCHAR(512),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 批次明细（逐行结果）
CREATE TABLE water_info.observation_batch_item (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id      UUID        NOT NULL REFERENCES water_info.observation_batch(id) ON DELETE CASCADE,
    item_index    INT         NOT NULL,
    station_code  VARCHAR(64) NOT NULL,
    metric_code   VARCHAR(32) NOT NULL,
    observed_at   TIMESTAMPTZ,
    value         NUMERIC(18,6),
    quality_code  VARCHAR(32),
    sensor_code   VARCHAR(64),
    status        VARCHAR(16) NOT NULL
                      CHECK (status IN ('accepted','rejected','skipped')),
    error_code    VARCHAR(64),
    error_message TEXT,
    station_id    UUID        REFERENCES water_info.station(id),
    metric_id     UUID        REFERENCES water_info.metric(id),
    sensor_id     UUID        REFERENCES water_info.sensor(id),
    observation_id UUID,           -- 无 FK 避免批处理循环依赖
    raw_payload   JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, item_index)
);

-- 观测数据（时序）
CREATE TABLE water_info.observation (
    id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id   UUID          NOT NULL REFERENCES water_info.station(id),
    sensor_id    UUID          REFERENCES water_info.sensor(id),
    metric_id    UUID          NOT NULL REFERENCES water_info.metric(id),
    observed_at  TIMESTAMPTZ   NOT NULL,
    value        NUMERIC(18,6) NOT NULL,
    quality_id   UUID          NOT NULL REFERENCES water_info.data_quality(id),
    batch_id     UUID          REFERENCES water_info.observation_batch(id),
    ingested_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    qc_flags     JSONB,
    anomaly_score NUMERIC(5,2),
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (station_id, metric_id, observed_at)
);

-- 告警规则
CREATE TABLE water_info.alert_rule (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code                        VARCHAR(64) NOT NULL UNIQUE,
    name                        VARCHAR(128) NOT NULL,
    description                 TEXT,
    status                      VARCHAR(16) NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active','inactive','draft')),
    severity                    VARCHAR(16) NOT NULL
                                    CHECK (severity IN ('info','yellow','orange','red')),
    expression_json             JSONB       NOT NULL,
    window_minutes              INT,
    evaluation_interval_seconds INT         DEFAULT 300,
    cooldown_minutes            INT         DEFAULT 5,
    is_global                   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by                  VARCHAR(128),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 告警规则作用域（对应哪些站/指标）
CREATE TABLE water_info.alert_rule_scope (
    id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id    UUID    NOT NULL REFERENCES water_info.alert_rule(id) ON DELETE CASCADE,
    station_id UUID    REFERENCES water_info.station(id),
    metric_id  UUID    REFERENCES water_info.metric(id),
    priority   INT     DEFAULT 0,
    CHECK (station_id IS NOT NULL OR metric_id IS NOT NULL),
    UNIQUE (rule_id, station_id, metric_id)
);

-- 告警规则动作（通知渠道）
CREATE TABLE water_info.alert_rule_action (
    id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id                UUID        NOT NULL REFERENCES water_info.alert_rule(id) ON DELETE CASCADE,
    type                   VARCHAR(32) NOT NULL
                               CHECK (type IN ('sms','email','webhook','dingtalk','wechat','custom')),
    target                 VARCHAR(512) NOT NULL,
    payload_template       JSONB,
    max_retries            INT         DEFAULT 3,
    retry_interval_seconds INT         DEFAULT 60,
    enabled                BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 告警事件（规则触发实例）
CREATE TABLE water_info.alert_event (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id         UUID          NOT NULL REFERENCES water_info.alert_rule(id),
    rule_code       VARCHAR(64)   NOT NULL,
    rule_name       VARCHAR(128)  NOT NULL,
    station_id      UUID          NOT NULL REFERENCES water_info.station(id),
    metric_id       UUID          NOT NULL REFERENCES water_info.metric(id),
    observed_at     TIMESTAMPTZ   NOT NULL,
    value           NUMERIC(18,6) NOT NULL,
    severity        VARCHAR(16)   NOT NULL
                        CHECK (severity IN ('info','yellow','orange','red')),
    status          VARCHAR(16)   NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','acknowledged','closed','expired')),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(128),
    closed_at       TIMESTAMPTZ,
    closed_by       VARCHAR(128),
    close_reason    VARCHAR(256),
    message         TEXT,
    context_json    JSONB,
    fingerprint     VARCHAR(128),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- 告警事件 ↔ 观测数据关联（证据追溯）
CREATE TABLE water_info.alert_event_observation (
    event_id       UUID NOT NULL REFERENCES water_info.alert_event(id)  ON DELETE CASCADE,
    observation_id UUID NOT NULL REFERENCES water_info.observation(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, observation_id)
);

-- 告警通知（推送记录）
CREATE TABLE water_info.alert_notification (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id       UUID        NOT NULL REFERENCES water_info.alert_event(id)      ON DELETE CASCADE,
    action_id      UUID        NOT NULL REFERENCES water_info.alert_rule_action(id),
    status         VARCHAR(16) NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','sending','sent','failed','skipped')),
    attempt_count  INT         NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    next_retry_at  TIMESTAMPTZ,
    sent_at        TIMESTAMPTZ,
    response_code  INT,
    response_body  TEXT,
    error          TEXT,
    payload_sent   JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 组织（water_info schema RBAC）
CREATE TABLE water_info.organization (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code          VARCHAR(64) NOT NULL UNIQUE,
    name          VARCHAR(128) NOT NULL,
    parent_id     UUID        REFERENCES water_info.organization(id) ON DELETE SET NULL,
    org_type      VARCHAR(32) NOT NULL DEFAULT 'DEPARTMENT',
    region_id     UUID        REFERENCES water_info.station_region(id),
    contact_phone VARCHAR(32),
    status        VARCHAR(16) NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active','inactive','suspended')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 用户（water_info schema）
CREATE TABLE water_info."user" (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    real_name     VARCHAR(64) NOT NULL,
    phone         VARCHAR(32),
    email         VARCHAR(128),
    org_id        UUID        REFERENCES water_info.organization(id),
    position      VARCHAR(64),
    status        VARCHAR(16) NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active','inactive','locked','resigned')),
    last_login_at TIMESTAMPTZ,
    mfa_enabled   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 角色（water_info schema）
CREATE TABLE water_info.role (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(64) NOT NULL UNIQUE,
    name        VARCHAR(64) NOT NULL,
    description TEXT,
    role_type   VARCHAR(32) NOT NULL DEFAULT 'BUSINESS'
                    CHECK (role_type IN ('SYSTEM','BUSINESS','CUSTOM')),
    level       INT         NOT NULL DEFAULT 0,
    status      VARCHAR(16) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','inactive')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 权限（water_info schema）
CREATE TABLE water_info.permission (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(128) NOT NULL UNIQUE,
    name            VARCHAR(64) NOT NULL,
    permission_type VARCHAR(32) NOT NULL
                        CHECK (permission_type IN ('MENU','API','DATA')),
    category        VARCHAR(64),
    api_path        VARCHAR(512),
    http_method     VARCHAR(16),
    status          VARCHAR(16) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 用户-角色（water_info schema）
CREATE TABLE water_info.user_role (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES water_info."user"(id) ON DELETE CASCADE,
    role_id     UUID        NOT NULL REFERENCES water_info.role(id)   ON DELETE CASCADE,
    scope_type  VARCHAR(32) NOT NULL DEFAULT 'ALL'
                    CHECK (scope_type IN ('ALL','REGION','STATION')),
    scope_value UUID[],
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by  VARCHAR(128),
    expires_at  TIMESTAMPTZ,
    UNIQUE (user_id, role_id)
);

-- 角色-权限（water_info schema）
CREATE TABLE water_info.role_permission (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id       UUID NOT NULL REFERENCES water_info.role(id)       ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES water_info.permission(id) ON DELETE CASCADE,
    UNIQUE (role_id, permission_id)
);

-- 用户会话（water_info schema）
CREATE TABLE water_info.user_session (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id         VARCHAR(128) NOT NULL UNIQUE,
    user_id            UUID        NOT NULL REFERENCES water_info."user"(id) ON DELETE CASCADE,
    access_token_hash  VARCHAR(256) NOT NULL,
    refresh_token_hash VARCHAR(256),
    ip_address         VARCHAR(45),
    user_agent         VARCHAR(512),
    device_type        VARCHAR(32),
    last_activity_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at         TIMESTAMPTZ NOT NULL,
    status             VARCHAR(16) NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active','expired','revoked')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 操作日志（water_info schema）
CREATE TABLE water_info.operation_log (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        REFERENCES water_info."user"(id) ON DELETE SET NULL,
    username      VARCHAR(64),
    module        VARCHAR(64) NOT NULL,
    action        VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64),
    resource_id   VARCHAR(128),
    request_path  VARCHAR(512),
    client_ip     VARCHAR(45),
    status        VARCHAR(16),
    error_message TEXT,
    operated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
