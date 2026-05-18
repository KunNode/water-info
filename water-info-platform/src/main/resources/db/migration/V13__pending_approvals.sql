-- Human-in-the-loop (HITL) approvals durable store for the AI service.
-- Owned by the platform Flyway pipeline; written by the AI service via
-- app/platform/approvals.py. See design.md §Data Models.

CREATE TABLE IF NOT EXISTS pending_approvals (
    approval_id      UUID PRIMARY KEY,
    session_id       VARCHAR(64) NOT NULL,
    thread_id        VARCHAR(64) NOT NULL,
    checkpoint_id    VARCHAR(64) NOT NULL,
    action_type      VARCHAR(64) NOT NULL,
    action_payload   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    status           VARCHAR(16) NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','approved','rejected','modified')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ,
    resolution       JSONB
);

CREATE INDEX IF NOT EXISTS idx_pending_approvals_session
    ON pending_approvals(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pending_approvals_status
    ON pending_approvals(status) WHERE status = 'pending';
