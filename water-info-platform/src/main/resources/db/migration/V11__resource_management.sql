-- Resource management tables for emergency resource tracking and dispatch

CREATE TABLE resource (
    id           VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    type         VARCHAR(20)  NOT NULL,
    name         VARCHAR(100) NOT NULL,
    quantity     INTEGER      NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    unit         VARCHAR(20)  NOT NULL,
    location     VARCHAR(200) NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'AVAILABLE',
    attributes   JSONB        NOT NULL DEFAULT '{}',
    description  TEXT,
    created_at   TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP    NOT NULL DEFAULT now(),
    deleted      BOOLEAN      NOT NULL DEFAULT false
);

CREATE INDEX idx_resource_type ON resource (type);
CREATE INDEX idx_resource_status ON resource (status);
CREATE INDEX idx_resource_name ON resource (name);
CREATE INDEX idx_resource_attributes ON resource USING gin (attributes);

COMMENT ON TABLE resource IS '应急资源台账';
COMMENT ON COLUMN resource.type IS '资源类型: MATERIAL/PERSONNEL/VEHICLE';
COMMENT ON COLUMN resource.status IS '状态: AVAILABLE/IN_USE/MAINTENANCE/DEPLETED';
COMMENT ON COLUMN resource.attributes IS '类型特有属性(JSONB)';

CREATE TABLE resource_dispatch (
    id             VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    resource_id    VARCHAR(36)  NOT NULL REFERENCES resource(id),
    plan_id        VARCHAR(50),
    quantity       INTEGER      NOT NULL CHECK (quantity > 0),
    from_location  VARCHAR(200) NOT NULL,
    to_location    VARCHAR(200) NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
    dispatched_at  TIMESTAMP,
    arrived_at     TIMESTAMP,
    returned_at    TIMESTAMP,
    operator       VARCHAR(50),
    source         VARCHAR(20)  NOT NULL DEFAULT 'MANUAL',
    notes          TEXT,
    created_at     TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at     TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX idx_dispatch_resource_id ON resource_dispatch (resource_id);
CREATE INDEX idx_dispatch_status ON resource_dispatch (status);
CREATE INDEX idx_dispatch_plan_id ON resource_dispatch (plan_id);
CREATE INDEX idx_dispatch_dispatched_at ON resource_dispatch (dispatched_at);

COMMENT ON TABLE resource_dispatch IS '资源调度记录';
COMMENT ON COLUMN resource_dispatch.status IS '状态: PENDING/DISPATCHED/ARRIVED/RETURNED/CANCELLED';
COMMENT ON COLUMN resource_dispatch.source IS '来源: AI/MANUAL';
