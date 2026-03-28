BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS water_info;
SET LOCAL search_path TO water_info, public;

-- Ensure trigger function exists for updated_at maintenance.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS organization (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(128) NOT NULL,
  parent_id UUID NULL REFERENCES organization(id) ON DELETE SET NULL,
  org_type VARCHAR(32) NOT NULL DEFAULT 'DEPARTMENT',
  region_id UUID NULL REFERENCES station_region(id),
  contact_phone VARCHAR(32) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive','suspended')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "user" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(64) UNIQUE NOT NULL,
  password_hash VARCHAR(256) NOT NULL,
  real_name VARCHAR(64) NOT NULL,
  phone VARCHAR(32) NULL,
  email VARCHAR(128) NULL,
  org_id UUID NULL REFERENCES organization(id),
  position VARCHAR(64) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive','locked','resigned')),
  last_login_at TIMESTAMPTZ NULL,
  mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(64) NOT NULL,
  description TEXT NULL,
  role_type VARCHAR(32) NOT NULL DEFAULT 'BUSINESS'
    CHECK (role_type IN ('SYSTEM','BUSINESS','CUSTOM')),
  level INT NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permission (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(128) UNIQUE NOT NULL,
  name VARCHAR(64) NOT NULL,
  permission_type VARCHAR(32) NOT NULL
    CHECK (permission_type IN ('MENU','API','DATA')),
  category VARCHAR(64) NULL,
  api_path VARCHAR(512) NULL,
  http_method VARCHAR(16) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','inactive')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_role (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  role_id UUID NOT NULL REFERENCES role(id) ON DELETE CASCADE,
  scope_type VARCHAR(32) NOT NULL DEFAULT 'ALL'
    CHECK (scope_type IN ('ALL','REGION','STATION')),
  scope_value UUID[] NULL,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  granted_by VARCHAR(128) NULL,
  expires_at TIMESTAMPTZ NULL,
  CONSTRAINT chk_user_role_scope_consistency CHECK (
    (scope_type = 'ALL' AND scope_value IS NULL)
    OR
    (
      scope_type IN ('REGION', 'STATION')
      AND scope_value IS NOT NULL
      AND COALESCE(array_length(scope_value, 1), 0) > 0
    )
  ),
  UNIQUE (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS role_permission (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id UUID NOT NULL REFERENCES role(id) ON DELETE CASCADE,
  permission_id UUID NOT NULL REFERENCES permission(id) ON DELETE CASCADE,
  UNIQUE (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_session (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id VARCHAR(128) UNIQUE NOT NULL,
  user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  access_token_hash VARCHAR(256) NOT NULL,
  refresh_token_hash VARCHAR(256) NULL,
  ip_address VARCHAR(45) NULL,
  user_agent VARCHAR(512) NULL,
  device_type VARCHAR(32) NULL,
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','expired','revoked')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operation_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NULL REFERENCES "user"(id) ON DELETE SET NULL,
  username VARCHAR(64) NULL,
  module VARCHAR(64) NOT NULL,
  action VARCHAR(64) NOT NULL,
  resource_type VARCHAR(64) NULL,
  resource_id VARCHAR(128) NULL,
  request_path VARCHAR(512) NULL,
  client_ip VARCHAR(45) NULL,
  status VARCHAR(16) NULL,
  error_message TEXT NULL,
  operated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_organization_parent_id ON organization (parent_id);
CREATE INDEX IF NOT EXISTS idx_organization_region_id ON organization (region_id);

CREATE INDEX IF NOT EXISTS idx_user_org_id ON "user" (org_id);
CREATE INDEX IF NOT EXISTS idx_user_status ON "user" (status);

CREATE INDEX IF NOT EXISTS idx_role_type ON role (role_type);

CREATE INDEX IF NOT EXISTS idx_permission_type ON permission (permission_type);

CREATE INDEX IF NOT EXISTS idx_user_role_user_id ON user_role (user_id);
CREATE INDEX IF NOT EXISTS idx_user_role_role_id ON user_role (role_id);

CREATE INDEX IF NOT EXISTS idx_role_permission_role_id ON role_permission (role_id);
CREATE INDEX IF NOT EXISTS idx_role_permission_permission_id ON role_permission (permission_id);

CREATE INDEX IF NOT EXISTS idx_user_session_user_id ON user_session (user_id);
CREATE INDEX IF NOT EXISTS idx_user_session_status ON user_session (status);
CREATE INDEX IF NOT EXISTS idx_user_session_expires_at ON user_session (expires_at);

CREATE INDEX IF NOT EXISTS idx_operation_log_user_id ON operation_log (user_id);
CREATE INDEX IF NOT EXISTS idx_operation_log_operated_at ON operation_log (operated_at DESC);

DROP TRIGGER IF EXISTS trg_organization_set_updated_at ON organization;
CREATE TRIGGER trg_organization_set_updated_at
  BEFORE UPDATE ON organization
  FOR EACH ROW
  EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_user_set_updated_at ON "user";
CREATE TRIGGER trg_user_set_updated_at
  BEFORE UPDATE ON "user"
  FOR EACH ROW
  EXECUTE FUNCTION set_updated_at();

COMMIT;



