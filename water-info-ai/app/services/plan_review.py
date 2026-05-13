"""Plan review service — transactional edit/approve with buffered audit.

Implements the human-review workflow for emergency plans:
- edit_draft(): edit a draft plan with buffered audit trail
- edit_approved(): edit an approved plan with direct audit write
- approve(): promote draft → approved with audit record
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg

from app.services.plan_diff import (
    ActionItem,
    ChangeEntry,
    NotificationItem,
    PlanSnapshot,
    ResourceItem,
    diff_plan,
)

logger = logging.getLogger(__name__)


# ── Application exceptions ────────────────────────────────────────────────────


class PlanReviewError(Exception):
    """Base for plan review business errors."""

    def __init__(self, error_code: str, message: str, status_code: int = 400, details: Any = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details


class VersionConflictError(PlanReviewError):
    def __init__(self, current_version: int, submitted_version: int):
        super().__init__(
            error_code="VERSION_CONFLICT",
            message="预案已被他人更新，请刷新后重试",
            status_code=409,
            details={"currentVersion": current_version, "submittedVersion": submitted_version},
        )


class StateConflictError(PlanReviewError):
    def __init__(self, current_status: str, allowed: list[str]):
        super().__init__(
            error_code="STATE_CONFLICT",
            message=f"当前状态 '{current_status}' 不允许该操作",
            status_code=409,
            details={"currentStatus": current_status, "allowedStatuses": allowed},
        )


class EntryNotFoundError(PlanReviewError):
    def __init__(self, entry_type: str, entry_id: str | int):
        super().__init__(
            error_code="ENTRY_NOT_FOUND",
            message=f"{entry_type} '{entry_id}' 不存在",
            status_code=404,
            details={"entryType": entry_type, "entryId": str(entry_id)},
        )


class ValidationFailedError(PlanReviewError):
    def __init__(self, fields: list[dict]):
        super().__init__(
            error_code="VALIDATION_FAILED",
            message="字段校验失败",
            status_code=422,
            details={"fields": fields},
        )


# ── Reviewer dataclass ────────────────────────────────────────────────────────


@dataclass
class Reviewer:
    user_id: str
    username: str


# ── Service ───────────────────────────────────────────────────────────────────


class PlanReviewService:
    """Transactional plan review operations with audit trail."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def edit_draft(
        self,
        plan_id: str,
        version: int,
        patch: dict[str, Any],
        reviewer: Reviewer,
    ) -> dict[str, Any]:
        """Edit a draft plan with buffered audit.

        Transaction: BEGIN → SELECT FOR UPDATE → validate version & status →
        apply patch → diff_plan → INSERT plan_audit_draft → version += 1 → COMMIT.

        Returns the updated plan detail dict with new version.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Lock the plan row
                row = await conn.fetchrow(
                    "SELECT plan_id, status, version, summary FROM emergency_plan "
                    "WHERE plan_id = $1 FOR UPDATE",
                    plan_id,
                )
                if row is None:
                    raise PlanReviewError(
                        error_code="PLAN_NOT_FOUND",
                        message="预案不存在",
                        status_code=404,
                    )

                current_status = row["status"]
                current_version = row["version"]

                # State gate: only draft allowed
                if current_status != "draft":
                    raise StateConflictError(current_status, ["draft"])

                # Version check
                if current_version != version:
                    raise VersionConflictError(current_version, version)

                # Build old snapshot
                old_snapshot = await self._build_snapshot(conn, plan_id, row["summary"])

                # Validate and apply patch, get new snapshot
                new_snapshot = await self._apply_patch(conn, plan_id, old_snapshot, patch)

                # Compute diff
                changes = diff_plan(old_snapshot, new_snapshot)

                # Buffer audit entries
                if changes:
                    await self._insert_audit_draft(conn, plan_id, reviewer, changes)

                # Bump version
                new_version = current_version + 1
                await conn.execute(
                    "UPDATE emergency_plan SET version = $1, summary = $2, updated_at = NOW() "
                    "WHERE plan_id = $3",
                    new_version, new_snapshot.summary, plan_id,
                )

                # Build response
                return await self._build_plan_response(conn, plan_id, new_version)

    async def edit_approved(
        self,
        plan_id: str,
        version: int,
        patch: dict[str, Any],
        reviewer: Reviewer,
    ) -> dict[str, Any]:
        """Edit an approved plan with direct audit write.

        Transaction: BEGIN → SELECT FOR UPDATE → validate version & status ∈ {approved}
        & role (defense in depth) → apply patch → diff_plan → INSERT plan_audit_record
        (action='edit_after_approve', opinion=NULL) + plan_audit_change rows
        (NOT via plan_audit_draft) → version += 1 → COMMIT.

        Returns the updated plan detail dict with new version.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Lock the plan row
                row = await conn.fetchrow(
                    "SELECT plan_id, status, version, summary FROM emergency_plan "
                    "WHERE plan_id = $1 FOR UPDATE",
                    plan_id,
                )
                if row is None:
                    raise PlanReviewError(
                        error_code="PLAN_NOT_FOUND",
                        message="预案不存在",
                        status_code=404,
                    )

                current_status = row["status"]
                current_version = row["version"]

                # State gate: only approved allowed
                if current_status != "approved":
                    raise StateConflictError(current_status, ["approved"])

                # Version check
                if current_version != version:
                    raise VersionConflictError(current_version, version)

                # Build old snapshot
                old_snapshot = await self._build_snapshot(conn, plan_id, row["summary"])

                # Validate and apply patch, get new snapshot
                new_snapshot = await self._apply_patch(conn, plan_id, old_snapshot, patch)

                # Compute diff
                changes = diff_plan(old_snapshot, new_snapshot)

                # Bump version
                new_version = current_version + 1
                await conn.execute(
                    "UPDATE emergency_plan SET version = $1, summary = $2, updated_at = NOW() "
                    "WHERE plan_id = $3",
                    new_version, new_snapshot.summary, plan_id,
                )

                # Write directly to plan_audit_record + plan_audit_change
                # (NOT via plan_audit_draft)
                audit_id = await conn.fetchval(
                    "INSERT INTO plan_audit_record "
                    "(plan_id, action, reviewer_user_id, reviewer_username, "
                    "opinion, from_status, to_status, from_version, to_version) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id",
                    plan_id,
                    "edit_after_approve",
                    reviewer.user_id,
                    reviewer.username,
                    None,  # opinion is NULL for edit_after_approve
                    "approved",
                    "approved",
                    current_version,
                    new_version,
                )

                # Insert change entries
                for change in changes:
                    await conn.execute(
                        "INSERT INTO plan_audit_change "
                        "(audit_id, field_path, change_type, old_value, new_value, "
                        "old_index, new_index) "
                        "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                        audit_id,
                        change.field_path,
                        change.change_type,
                        change.old_value,
                        change.new_value,
                        change.old_index,
                        change.new_index,
                    )

                logger.info(
                    "[plan-review] action=edit_after_approve plan=%s user=%s version=%d->%d changes=%d",
                    plan_id, reviewer.user_id, current_version, new_version, len(changes),
                )

                # Build response
                return await self._build_plan_response(conn, plan_id, new_version)

    async def approve(
        self,
        plan_id: str,
        version: int,
        opinion: str,
        reviewer: Reviewer,
    ) -> dict:
        """Approve a draft plan (draft → approved) with audit record.

        Transaction: BEGIN → SELECT FOR UPDATE → validate status=='draft' + version
        + opinion.strip() length ∈ [1,500] → read all plan_audit_draft entries →
        INSERT plan_audit_record(action='approve') → migrate draft entries to
        plan_audit_change → DELETE plan_audit_draft → status='approved' + version+=1
        → COMMIT.

        Even if there are zero draft entries, still creates the plan_audit_record (Req 7.1).

        Returns {plan_id, status, version, audit_record_id}.
        """
        # Validate opinion before entering transaction
        stripped_opinion = opinion.strip()
        if len(stripped_opinion) == 0:
            raise ValidationFailedError([{
                "field": "opinion",
                "reason": "审核意见必填",
            }])
        if len(stripped_opinion) > 500:
            raise ValidationFailedError([{
                "field": "opinion",
                "reason": "审核意见超出最大长度（500 字符）",
            }])

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Lock the plan row
                row = await conn.fetchrow(
                    "SELECT plan_id, status, version FROM emergency_plan "
                    "WHERE plan_id = $1 FOR UPDATE",
                    plan_id,
                )
                if row is None:
                    raise PlanReviewError(
                        error_code="PLAN_NOT_FOUND",
                        message="预案不存在",
                        status_code=404,
                    )

                current_status = row["status"]
                current_version = row["version"]

                # State gate: only draft allowed
                if current_status != "draft":
                    raise StateConflictError(current_status, ["draft"])

                # Version check
                if current_version != version:
                    raise VersionConflictError(current_version, version)

                # Read all plan_audit_draft entries for this plan (ordered by buffered_at)
                draft_entries = await conn.fetch(
                    "SELECT field_path, change_type, old_value, new_value, old_index, new_index "
                    "FROM plan_audit_draft WHERE plan_id = $1 ORDER BY buffered_at ASC",
                    plan_id,
                )

                # Insert one plan_audit_record (even if draft_entries is empty — Req 7.1)
                new_version = current_version + 1
                audit_id = await conn.fetchval(
                    "INSERT INTO plan_audit_record "
                    "(plan_id, action, reviewer_user_id, reviewer_username, "
                    "opinion, from_status, to_status, from_version, to_version) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id",
                    plan_id,
                    "approve",
                    reviewer.user_id,
                    reviewer.username,
                    stripped_opinion,
                    "draft",
                    "approved",
                    current_version,
                    new_version,
                )

                # Migrate draft entries to plan_audit_change rows
                for entry in draft_entries:
                    await conn.execute(
                        "INSERT INTO plan_audit_change "
                        "(audit_id, field_path, change_type, old_value, new_value, "
                        "old_index, new_index) "
                        "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                        audit_id,
                        entry["field_path"],
                        entry["change_type"],
                        entry["old_value"],
                        entry["new_value"],
                        entry["old_index"],
                        entry["new_index"],
                    )

                # Delete all draft entries for this plan
                await conn.execute(
                    "DELETE FROM plan_audit_draft WHERE plan_id = $1",
                    plan_id,
                )

                # Update plan status to approved and bump version
                await conn.execute(
                    "UPDATE emergency_plan SET status = 'approved', version = $1, "
                    "updated_at = NOW() WHERE plan_id = $2",
                    new_version, plan_id,
                )

                logger.info(
                    "[plan-review] action=approve plan=%s user=%s version=%d->%d draft_entries=%d",
                    plan_id, reviewer.user_id, current_version, new_version, len(draft_entries),
                )

                return {
                    "plan_id": plan_id,
                    "status": "approved",
                    "version": new_version,
                    "audit_record_id": audit_id,
                }

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _build_snapshot(
        self, conn: asyncpg.Connection, plan_id: str, summary: str
    ) -> PlanSnapshot:
        """Build a PlanSnapshot from current DB state."""
        actions_rows = await conn.fetch(
            "SELECT action_id, description, priority, responsible_dept, status "
            "FROM emergency_action WHERE plan_id = $1 ORDER BY priority ASC",
            plan_id,
        )
        resources_rows = await conn.fetch(
            "SELECT id, resource_type, resource_name, quantity, source_location "
            "FROM resource_allocation WHERE plan_id = $1 ORDER BY id ASC",
            plan_id,
        )
        notifications_rows = await conn.fetch(
            "SELECT id, channel, target, content, status "
            "FROM notification_record WHERE plan_id = $1 ORDER BY id ASC",
            plan_id,
        )

        actions = [
            ActionItem(
                action_id=r["action_id"],
                description=r["description"],
                priority=r["priority"],
                assignee=r.get("responsible_dept") or "",
                status=r["status"],
            )
            for r in actions_rows
        ]
        resources = [
            ResourceItem(
                resource_id=r["id"],
                type=r["resource_type"],
                name=r["resource_name"],
                quantity=r["quantity"],
                location=r.get("source_location") or "",
            )
            for r in resources_rows
        ]
        notifications = [
            NotificationItem(
                notification_id=r["id"],
                channel=r["channel"],
                target=r["target"],
                message=r.get("content") or "",
                status=r["status"],
            )
            for r in notifications_rows
        ]

        return PlanSnapshot(
            summary=summary or "",
            actions=actions,
            resources=resources,
            notifications=notifications,
        )

    async def _apply_patch(
        self,
        conn: asyncpg.Connection,
        plan_id: str,
        old_snapshot: PlanSnapshot,
        patch: dict[str, Any],
    ) -> PlanSnapshot:
        """Apply patch to the plan and return the new snapshot.

        Mutates DB rows for actions/resources/notifications.
        Returns the new PlanSnapshot reflecting the applied changes.
        """
        new_summary = old_snapshot.summary
        new_actions = list(old_snapshot.actions)
        new_resources = list(old_snapshot.resources)
        new_notifications = list(old_snapshot.notifications)

        # ── Summary ───────────────────────────────────────────────────────────
        if "summary" in patch:
            summary_val = patch["summary"]
            if summary_val is not None:
                if not isinstance(summary_val, str):
                    raise ValidationFailedError([{"field": "summary", "reason": "必须为字符串"}])
                if len(summary_val) > 50000:
                    raise ValidationFailedError([{"field": "summary", "reason": "长度不能超过50000字符"}])
                new_summary = summary_val

        # ── Actions ───────────────────────────────────────────────────────────
        if "actions" in patch and patch["actions"]:
            actions_patch = patch["actions"]
            new_actions = await self._apply_actions_patch(
                conn, plan_id, old_snapshot.actions, actions_patch
            )

        # ── Resources ─────────────────────────────────────────────────────────
        if "resources" in patch and patch["resources"]:
            resources_patch = patch["resources"]
            new_resources = await self._apply_resources_patch(
                conn, plan_id, old_snapshot.resources, resources_patch
            )

        # ── Notifications ─────────────────────────────────────────────────────
        if "notifications" in patch and patch["notifications"]:
            notifications_patch = patch["notifications"]
            new_notifications = await self._apply_notifications_patch(
                conn, plan_id, old_snapshot.notifications, notifications_patch
            )

        return PlanSnapshot(
            summary=new_summary,
            actions=new_actions,
            resources=new_resources,
            notifications=new_notifications,
        )

    async def _apply_actions_patch(
        self,
        conn: asyncpg.Connection,
        plan_id: str,
        current_actions: list[ActionItem],
        actions_patch: dict[str, Any],
    ) -> list[ActionItem]:
        """Apply upsert/delete to actions. Returns new action list."""
        actions_by_id = {a.action_id: a for a in current_actions}
        result = list(current_actions)

        # Process deletes first
        for action_id in actions_patch.get("delete") or []:
            if action_id not in actions_by_id:
                raise EntryNotFoundError("action", action_id)
            await conn.execute(
                "DELETE FROM emergency_action WHERE plan_id = $1 AND action_id = $2",
                plan_id, action_id,
            )
            result = [a for a in result if a.action_id != action_id]
            del actions_by_id[action_id]

        # Process upserts
        for item in actions_patch.get("upsert") or []:
            action_id = item.get("actionId") or item.get("action_id")
            description = item.get("description", "")
            priority = item.get("priority", 3)
            assignee = item.get("assignee", "")
            status = item.get("status", "pending")

            # Validate required fields for new items
            errors = []
            if not description:
                errors.append({"field": f"actions.description", "reason": "description 必填"})
            if priority is None:
                errors.append({"field": f"actions.priority", "reason": "priority 必填"})
            if errors:
                raise ValidationFailedError(errors)

            # Validate priority range
            if not isinstance(priority, int) or priority < 1 or priority > 5:
                raise ValidationFailedError([{
                    "field": "actions.priority",
                    "reason": "priority 必须为 1-5 的整数",
                }])

            if action_id is None or action_id not in actions_by_id:
                # New action — generate ID if not provided
                new_id = action_id or str(uuid.uuid4())[:8]
                await conn.execute(
                    "INSERT INTO emergency_action "
                    "(plan_id, action_id, description, priority, responsible_dept, status) "
                    "VALUES ($1, $2, $3, $4, $5, $6)",
                    plan_id, new_id, description, priority, assignee, status,
                )
                new_action = ActionItem(
                    action_id=new_id,
                    description=description,
                    priority=priority,
                    assignee=assignee,
                    status=status,
                )
                result.append(new_action)
                actions_by_id[new_id] = new_action
            else:
                # Update existing
                await conn.execute(
                    "UPDATE emergency_action SET description = $1, priority = $2, "
                    "responsible_dept = $3, status = $4 WHERE plan_id = $5 AND action_id = $6",
                    description, priority, assignee, status, plan_id, action_id,
                )
                updated = ActionItem(
                    action_id=action_id,
                    description=description,
                    priority=priority,
                    assignee=assignee,
                    status=status,
                )
                result = [updated if a.action_id == action_id else a for a in result]
                actions_by_id[action_id] = updated

        return result

    async def _apply_resources_patch(
        self,
        conn: asyncpg.Connection,
        plan_id: str,
        current_resources: list[ResourceItem],
        resources_patch: dict[str, Any],
    ) -> list[ResourceItem]:
        """Apply upsert/delete to resources. Returns new resource list."""
        resources_by_id = {r.resource_id: r for r in current_resources}
        result = list(current_resources)

        # Process deletes first
        for resource_id in resources_patch.get("delete") or []:
            rid = int(resource_id)
            if rid not in resources_by_id:
                raise EntryNotFoundError("resource", rid)
            await conn.execute(
                "DELETE FROM resource_allocation WHERE plan_id = $1 AND id = $2",
                plan_id, rid,
            )
            result = [r for r in result if r.resource_id != rid]
            del resources_by_id[rid]

        # Process upserts
        for item in resources_patch.get("upsert") or []:
            resource_id = item.get("resourceId") or item.get("resource_id")
            rtype = item.get("type", "")
            name = item.get("name", "")
            quantity = item.get("quantity", 0)
            location = item.get("location", "")

            # Validate required fields
            errors = []
            if not rtype:
                errors.append({"field": "resources.type", "reason": "type 必填"})
            if not name:
                errors.append({"field": "resources.name", "reason": "name 必填"})
            if quantity is None:
                errors.append({"field": "resources.quantity", "reason": "quantity 必填"})
            if errors:
                raise ValidationFailedError(errors)

            if not isinstance(quantity, int) or quantity < 0:
                raise ValidationFailedError([{
                    "field": "resources.quantity",
                    "reason": "quantity 必须为非负整数",
                }])

            if resource_id is not None and int(resource_id) in resources_by_id:
                # Update existing
                rid = int(resource_id)
                await conn.execute(
                    "UPDATE resource_allocation SET resource_type = $1, resource_name = $2, "
                    "quantity = $3, source_location = $4 WHERE plan_id = $5 AND id = $6",
                    rtype, name, quantity, location, plan_id, rid,
                )
                updated = ResourceItem(
                    resource_id=rid, type=rtype, name=name, quantity=quantity, location=location,
                )
                result = [updated if r.resource_id == rid else r for r in result]
                resources_by_id[rid] = updated
            else:
                # New resource
                new_id = await conn.fetchval(
                    "INSERT INTO resource_allocation "
                    "(plan_id, resource_type, resource_name, quantity, source_location) "
                    "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                    plan_id, rtype, name, quantity, location,
                )
                new_resource = ResourceItem(
                    resource_id=new_id, type=rtype, name=name, quantity=quantity, location=location,
                )
                result.append(new_resource)
                resources_by_id[new_id] = new_resource

        return result

    async def _apply_notifications_patch(
        self,
        conn: asyncpg.Connection,
        plan_id: str,
        current_notifications: list[NotificationItem],
        notifications_patch: dict[str, Any],
    ) -> list[NotificationItem]:
        """Apply upsert/delete to notifications. Returns new notification list."""
        notifs_by_id = {n.notification_id: n for n in current_notifications}
        result = list(current_notifications)

        # Process deletes first
        for notif_id in notifications_patch.get("delete") or []:
            nid = int(notif_id)
            if nid not in notifs_by_id:
                raise EntryNotFoundError("notification", nid)
            await conn.execute(
                "DELETE FROM notification_record WHERE plan_id = $1 AND id = $2",
                plan_id, nid,
            )
            result = [n for n in result if n.notification_id != nid]
            del notifs_by_id[nid]

        # Process upserts
        for item in notifications_patch.get("upsert") or []:
            notif_id = item.get("notificationId") or item.get("notification_id")
            channel = item.get("channel", "")
            target = item.get("target", "")
            message = item.get("message", "")
            status = item.get("status", "pending")

            # Validate required fields
            errors = []
            if not channel:
                errors.append({"field": "notifications.channel", "reason": "channel 必填"})
            if not target:
                errors.append({"field": "notifications.target", "reason": "target 必填"})
            if errors:
                raise ValidationFailedError(errors)

            if notif_id is not None and int(notif_id) in notifs_by_id:
                # Update existing
                nid = int(notif_id)
                await conn.execute(
                    "UPDATE notification_record SET channel = $1, target = $2, "
                    "content = $3, status = $4 WHERE plan_id = $5 AND id = $6",
                    channel, target, message, status, plan_id, nid,
                )
                updated = NotificationItem(
                    notification_id=nid, channel=channel, target=target,
                    message=message, status=status,
                )
                result = [updated if n.notification_id == nid else n for n in result]
                notifs_by_id[nid] = updated
            else:
                # New notification
                new_id = await conn.fetchval(
                    "INSERT INTO notification_record "
                    "(plan_id, channel, target, content, status) "
                    "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                    plan_id, channel, target, message, status,
                )
                new_notif = NotificationItem(
                    notification_id=new_id, channel=channel, target=target,
                    message=message, status=status,
                )
                result.append(new_notif)
                notifs_by_id[new_id] = new_notif

        return result

    async def _insert_audit_draft(
        self,
        conn: asyncpg.Connection,
        plan_id: str,
        reviewer: Reviewer,
        changes: list[ChangeEntry],
    ) -> None:
        """Batch insert change entries into plan_audit_draft."""
        for change in changes:
            await conn.execute(
                "INSERT INTO plan_audit_draft "
                "(plan_id, reviewer_user_id, reviewer_username, field_path, "
                "change_type, old_value, new_value, old_index, new_index) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                plan_id,
                reviewer.user_id,
                reviewer.username,
                change.field_path,
                change.change_type,
                change.old_value,
                change.new_value,
                change.old_index,
                change.new_index,
            )

    async def _build_plan_response(
        self, conn: asyncpg.Connection, plan_id: str, version: int
    ) -> dict[str, Any]:
        """Build the full plan detail response dict."""
        plan_row = await conn.fetchrow(
            "SELECT plan_id, plan_name, risk_level, trigger_conditions, status, "
            "session_id, summary, version, created_at, updated_at "
            "FROM emergency_plan WHERE plan_id = $1",
            plan_id,
        )
        actions = await conn.fetch(
            "SELECT action_id, action_type, description, priority, "
            "responsible_dept, deadline_minutes, status, created_at "
            "FROM emergency_action WHERE plan_id = $1 ORDER BY priority ASC",
            plan_id,
        )
        resources = await conn.fetch(
            "SELECT id, resource_type, resource_name, quantity, "
            "source_location, target_location, eta_minutes, created_at "
            "FROM resource_allocation WHERE plan_id = $1 ORDER BY id ASC",
            plan_id,
        )
        notifications = await conn.fetch(
            "SELECT id, target, channel, content, status, sent_at, created_at "
            "FROM notification_record WHERE plan_id = $1 ORDER BY id ASC",
            plan_id,
        )

        return {
            "plan_id": plan_row["plan_id"],
            "plan_name": plan_row["plan_name"],
            "risk_level": plan_row["risk_level"],
            "trigger_conditions": plan_row["trigger_conditions"],
            "status": plan_row["status"],
            "session_id": plan_row["session_id"],
            "summary": plan_row["summary"],
            "version": plan_row["version"],
            "created_at": plan_row["created_at"].isoformat() if plan_row["created_at"] else None,
            "updated_at": plan_row["updated_at"].isoformat() if plan_row["updated_at"] else None,
            "actions": [
                {
                    "action_id": a["action_id"],
                    "action_type": a.get("action_type") or "",
                    "description": a["description"],
                    "priority": a["priority"],
                    "responsible_dept": a.get("responsible_dept") or "",
                    "assignee": a.get("responsible_dept") or "",
                    "deadline_minutes": a.get("deadline_minutes"),
                    "status": a["status"],
                    "created_at": a["created_at"].isoformat() if a.get("created_at") else None,
                }
                for a in actions
            ],
            "resources": [
                {
                    "id": r["id"],
                    "resource_type": r["resource_type"],
                    "resource_name": r["resource_name"],
                    "quantity": r["quantity"],
                    "source_location": r.get("source_location") or "",
                    "target_location": r.get("target_location") or "",
                    "eta_minutes": r.get("eta_minutes"),
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                }
                for r in resources
            ],
            "notifications": [
                {
                    "id": n["id"],
                    "target": n["target"],
                    "channel": n["channel"],
                    "content": n.get("content") or "",
                    "status": n["status"],
                    "sent_at": n["sent_at"].isoformat() if n.get("sent_at") else None,
                    "created_at": n["created_at"].isoformat() if n.get("created_at") else None,
                }
                for n in notifications
            ],
        }
