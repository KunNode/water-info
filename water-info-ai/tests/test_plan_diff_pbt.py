"""Property-based tests for plan diff completeness & roundtrip.

Feature: plan-human-review, Property 3: read-back consistency

Validates: Requirements 7.3, 7.4

Property 3 (diff portion): For any (old, patch) pair where patch is field-level
valid, apply(old, patch) produces a result where diff_plan(old, applied)
accurately covers the patch's upsert/delete set without extra entries.

Property 5 (portion): The diff captures all changes completely — no missing
entries, no spurious entries.
"""

from __future__ import annotations

import json
from copy import deepcopy

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.plan_diff import (
    ActionItem,
    ChangeEntry,
    NotificationItem,
    PlanSnapshot,
    ResourceItem,
    diff_plan,
)


# ── Apply helper (simulates server-side patch application) ────────────────────


def apply_patch(old: PlanSnapshot, patch: dict) -> PlanSnapshot:
    """Apply a patch dict to a PlanSnapshot, returning the new snapshot.

    Patch format mirrors the API's PATCH body:
    - summary: optional str replacement
    - actions: {upsert: [...], delete: [...]}
    - resources: {upsert: [...], delete: [...]}
    - notifications: {upsert: [...], delete: [...]}
    """
    result = deepcopy(old)

    if "summary" in patch:
        result.summary = patch["summary"]

    if "actions" in patch:
        actions_patch = patch["actions"]
        # Delete first
        delete_ids = set(actions_patch.get("delete", []))
        result.actions = [a for a in result.actions if a.action_id not in delete_ids]
        # Upsert: update existing or append new
        for item in actions_patch.get("upsert", []):
            existing = next(
                (a for a in result.actions if a.action_id == item["action_id"]),
                None,
            )
            if existing:
                existing.description = item.get("description", existing.description)
                existing.priority = item.get("priority", existing.priority)
                existing.assignee = item.get("assignee", existing.assignee)
                existing.status = item.get("status", existing.status)
            else:
                result.actions.append(ActionItem(
                    action_id=item["action_id"],
                    description=item.get("description", ""),
                    priority=item.get("priority", 3),
                    assignee=item.get("assignee", ""),
                    status=item.get("status", "pending"),
                ))

    if "resources" in patch:
        res_patch = patch["resources"]
        delete_ids = set(res_patch.get("delete", []))
        result.resources = [r for r in result.resources if r.resource_id not in delete_ids]
        for item in res_patch.get("upsert", []):
            existing = next(
                (r for r in result.resources if r.resource_id == item["resource_id"]),
                None,
            )
            if existing:
                existing.type = item.get("type", existing.type)
                existing.name = item.get("name", existing.name)
                existing.quantity = item.get("quantity", existing.quantity)
                existing.location = item.get("location", existing.location)
            else:
                result.resources.append(ResourceItem(
                    resource_id=item["resource_id"],
                    type=item.get("type", ""),
                    name=item.get("name", ""),
                    quantity=item.get("quantity", 0),
                    location=item.get("location", ""),
                ))

    if "notifications" in patch:
        notif_patch = patch["notifications"]
        delete_ids = set(notif_patch.get("delete", []))
        result.notifications = [
            n for n in result.notifications if n.notification_id not in delete_ids
        ]
        for item in notif_patch.get("upsert", []):
            existing = next(
                (n for n in result.notifications if n.notification_id == item["notification_id"]),
                None,
            )
            if existing:
                existing.channel = item.get("channel", existing.channel)
                existing.target = item.get("target", existing.target)
                existing.message = item.get("message", existing.message)
                existing.status = item.get("status", existing.status)
            else:
                result.notifications.append(NotificationItem(
                    notification_id=item["notification_id"],
                    channel=item.get("channel", ""),
                    target=item.get("target", ""),
                    message=item.get("message", ""),
                    status=item.get("status", "pending"),
                ))

    return result


# ── Hypothesis strategies ─────────────────────────────────────────────────────

# Summary with boundary lengths: 0, 1, moderate, and 50000 boundary
_summary_st = st.one_of(
    st.just(""),
    st.text(min_size=1, max_size=1),
    st.text(min_size=2, max_size=200),
    st.just("A" * 50000),
)

_action_id_st = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
    min_size=1,
    max_size=10,
).map(lambda s: f"a-{s}")

_resource_id_st = st.integers(min_value=1, max_value=1000)
_notification_id_st = st.integers(min_value=1, max_value=1000)
_priority_st = st.integers(min_value=1, max_value=5)
_short_text_st = st.text(min_size=0, max_size=50)


@st.composite
def action_item_st(draw) -> ActionItem:
    return ActionItem(
        action_id=draw(_action_id_st),
        description=draw(_short_text_st),
        priority=draw(_priority_st),
        assignee=draw(_short_text_st),
        status=draw(st.sampled_from(["pending", "in_progress", "done"])),
    )


@st.composite
def resource_item_st(draw) -> ResourceItem:
    return ResourceItem(
        resource_id=draw(_resource_id_st),
        type=draw(_short_text_st),
        name=draw(_short_text_st),
        quantity=draw(st.integers(min_value=0, max_value=10000)),
        location=draw(_short_text_st),
    )


@st.composite
def notification_item_st(draw) -> NotificationItem:
    return NotificationItem(
        notification_id=draw(_notification_id_st),
        channel=draw(st.sampled_from(["sms", "email", "wechat"])),
        target=draw(_short_text_st),
        message=draw(_short_text_st),
        status=draw(st.sampled_from(["pending", "sent", "failed"])),
    )


def _unique_by_key(items: list, key_attr: str) -> list:
    """Deduplicate items by key attribute, keeping last occurrence."""
    seen = {}
    for item in items:
        seen[getattr(item, key_attr)] = item
    return list(seen.values())


@st.composite
def plan_snapshot_st(draw) -> PlanSnapshot:
    actions = _unique_by_key(
        draw(st.lists(action_item_st(), min_size=0, max_size=10)),
        "action_id",
    )
    resources = _unique_by_key(
        draw(st.lists(resource_item_st(), min_size=0, max_size=10)),
        "resource_id",
    )
    notifications = _unique_by_key(
        draw(st.lists(notification_item_st(), min_size=0, max_size=10)),
        "notification_id",
    )
    return PlanSnapshot(
        summary=draw(_summary_st),
        actions=actions,
        resources=resources,
        notifications=notifications,
    )


@st.composite
def patch_for_snapshot_st(draw, old: PlanSnapshot) -> dict:
    """Generate a valid patch for a given snapshot.

    The patch may include:
    - summary replacement
    - actions upsert/delete (reusing existing ids or adding new ones)
    - resources upsert/delete
    - notifications upsert/delete
    """
    patch = {}

    # Optionally change summary
    if draw(st.booleans()):
        patch["summary"] = draw(_summary_st)

    # Actions patch
    if draw(st.booleans()):
        existing_ids = [a.action_id for a in old.actions]
        # Delete subset of existing
        delete_ids = draw(st.lists(
            st.sampled_from(existing_ids) if existing_ids else st.nothing(),
            max_size=min(len(existing_ids), 5),
            unique=True,
        ))
        # Upsert: mix of existing (modify) and new (add)
        upsert_items = []
        remaining_ids = [aid for aid in existing_ids if aid not in delete_ids]
        # Modify some existing
        modify_ids = draw(st.lists(
            st.sampled_from(remaining_ids) if remaining_ids else st.nothing(),
            max_size=min(len(remaining_ids), 3),
            unique=True,
        ))
        for aid in modify_ids:
            upsert_items.append({
                "action_id": aid,
                "description": draw(_short_text_st),
                "priority": draw(_priority_st),
                "assignee": draw(_short_text_st),
                "status": draw(st.sampled_from(["pending", "in_progress", "done"])),
            })
        # Add new
        new_count = draw(st.integers(min_value=0, max_value=3))
        for _ in range(new_count):
            new_id = draw(_action_id_st.filter(lambda x: x not in existing_ids))
            upsert_items.append({
                "action_id": new_id,
                "description": draw(_short_text_st),
                "priority": draw(_priority_st),
                "assignee": draw(_short_text_st),
                "status": draw(st.sampled_from(["pending", "in_progress", "done"])),
            })
        if delete_ids or upsert_items:
            patch["actions"] = {"upsert": upsert_items, "delete": delete_ids}

    # Resources patch
    if draw(st.booleans()):
        existing_ids = [r.resource_id for r in old.resources]
        delete_ids = draw(st.lists(
            st.sampled_from(existing_ids) if existing_ids else st.nothing(),
            max_size=min(len(existing_ids), 5),
            unique=True,
        ))
        upsert_items = []
        remaining_ids = [rid for rid in existing_ids if rid not in delete_ids]
        modify_ids = draw(st.lists(
            st.sampled_from(remaining_ids) if remaining_ids else st.nothing(),
            max_size=min(len(remaining_ids), 3),
            unique=True,
        ))
        for rid in modify_ids:
            upsert_items.append({
                "resource_id": rid,
                "type": draw(_short_text_st),
                "name": draw(_short_text_st),
                "quantity": draw(st.integers(min_value=0, max_value=10000)),
                "location": draw(_short_text_st),
            })
        new_count = draw(st.integers(min_value=0, max_value=3))
        for _ in range(new_count):
            new_id = draw(_resource_id_st.filter(lambda x: x not in existing_ids))
            upsert_items.append({
                "resource_id": new_id,
                "type": draw(_short_text_st),
                "name": draw(_short_text_st),
                "quantity": draw(st.integers(min_value=0, max_value=10000)),
                "location": draw(_short_text_st),
            })
        if delete_ids or upsert_items:
            patch["resources"] = {"upsert": upsert_items, "delete": delete_ids}

    # Notifications patch
    if draw(st.booleans()):
        existing_ids = [n.notification_id for n in old.notifications]
        delete_ids = draw(st.lists(
            st.sampled_from(existing_ids) if existing_ids else st.nothing(),
            max_size=min(len(existing_ids), 5),
            unique=True,
        ))
        upsert_items = []
        remaining_ids = [nid for nid in existing_ids if nid not in delete_ids]
        modify_ids = draw(st.lists(
            st.sampled_from(remaining_ids) if remaining_ids else st.nothing(),
            max_size=min(len(remaining_ids), 3),
            unique=True,
        ))
        for nid in modify_ids:
            upsert_items.append({
                "notification_id": nid,
                "channel": draw(st.sampled_from(["sms", "email", "wechat"])),
                "target": draw(_short_text_st),
                "message": draw(_short_text_st),
                "status": draw(st.sampled_from(["pending", "sent", "failed"])),
            })
        new_count = draw(st.integers(min_value=0, max_value=3))
        for _ in range(new_count):
            new_id = draw(_notification_id_st.filter(lambda x: x not in existing_ids))
            upsert_items.append({
                "notification_id": new_id,
                "channel": draw(st.sampled_from(["sms", "email", "wechat"])),
                "target": draw(_short_text_st),
                "message": draw(_short_text_st),
                "status": draw(st.sampled_from(["pending", "sent", "failed"])),
            })
        if delete_ids or upsert_items:
            patch["notifications"] = {"upsert": upsert_items, "delete": delete_ids}

    return patch


# ── Property tests ────────────────────────────────────────────────────────────


@given(data=st.data())
@settings(max_examples=20, deadline=None)
def test_diff_completeness_covers_patch(data):
    """Feature: plan-human-review, Property 3: read-back consistency

    Validates: Requirements 7.3, 7.4

    For any (old, patch) pair where patch is field-level valid,
    apply(old, patch) produces a result where diff_plan(old, applied)
    accurately covers the patch's upsert/delete set without extra entries.
    """
    old = data.draw(plan_snapshot_st())
    patch = data.draw(patch_for_snapshot_st(old))

    # Skip trivially empty patches (no changes expected)
    if not patch:
        return

    applied = apply_patch(old, patch)
    changes = diff_plan(old, applied)

    # Build expected change field_paths from the patch
    expected_paths: set[str] = set()

    # Summary change
    if "summary" in patch and patch["summary"] != old.summary:
        expected_paths.add("summary")

    # Actions
    if "actions" in patch:
        actions_patch = patch["actions"]
        old_action_map = {a.action_id: a for a in old.actions}

        for aid in actions_patch.get("delete", []):
            if aid in old_action_map:
                expected_paths.add(f"actions[{aid}]")

        for item in actions_patch.get("upsert", []):
            aid = item["action_id"]
            if aid not in old_action_map:
                # New item added
                expected_paths.add(f"actions[{aid}]")
            else:
                # Existing item modified — check which fields changed
                existing = old_action_map[aid]
                for field_name in ["description", "priority", "assignee", "status"]:
                    if field_name in item and item[field_name] != getattr(existing, field_name):
                        expected_paths.add(f"actions[{aid}].{field_name}")

    # Resources
    if "resources" in patch:
        res_patch = patch["resources"]
        old_res_map = {r.resource_id: r for r in old.resources}

        for rid in res_patch.get("delete", []):
            if rid in old_res_map:
                expected_paths.add(f"resources[{rid}]")

        for item in res_patch.get("upsert", []):
            rid = item["resource_id"]
            if rid not in old_res_map:
                expected_paths.add(f"resources[{rid}]")
            else:
                existing = old_res_map[rid]
                for field_name in ["type", "name", "quantity", "location"]:
                    if field_name in item and item[field_name] != getattr(existing, field_name):
                        expected_paths.add(f"resources[{rid}].{field_name}")

    # Notifications
    if "notifications" in patch:
        notif_patch = patch["notifications"]
        old_notif_map = {n.notification_id: n for n in old.notifications}

        for nid in notif_patch.get("delete", []):
            if nid in old_notif_map:
                expected_paths.add(f"notifications[{nid}]")

        for item in notif_patch.get("upsert", []):
            nid = item["notification_id"]
            if nid not in old_notif_map:
                expected_paths.add(f"notifications[{nid}]")
            else:
                existing = old_notif_map[nid]
                for field_name in ["channel", "target", "message", "status"]:
                    if field_name in item and item[field_name] != getattr(existing, field_name):
                        expected_paths.add(f"notifications[{nid}].{field_name}")

    actual_paths = {c.field_path for c in changes}

    # The diff must cover all expected paths from the patch
    missing = expected_paths - actual_paths
    assert not missing, (
        f"Diff missing entries for patch changes: {missing}\n"
        f"Expected: {sorted(expected_paths)}\n"
        f"Actual:   {sorted(actual_paths)}"
    )

    # The diff must not produce entries beyond what the patch implies
    # (accounting for order changes which are legitimate extra entries)
    order_change_paths = {
        c.field_path for c in changes
        if c.change_type == "modify"
        and c.old_value is None
        and c.new_value is None
        and c.old_index is not None
        and c.new_index is not None
    }
    spurious = actual_paths - expected_paths - order_change_paths
    assert not spurious, (
        f"Diff produced spurious entries not in patch: {spurious}\n"
        f"Expected: {sorted(expected_paths)}\n"
        f"Actual:   {sorted(actual_paths)}"
    )


@given(data=st.data())
@settings(max_examples=20, deadline=None)
def test_diff_roundtrip_old_to_new(data):
    """Feature: plan-human-review, Property 3: read-back consistency

    Validates: Requirements 7.3, 7.4

    For any two snapshots old and new, diff_plan(old, new) produces a complete
    set of changes such that applying those changes to old reconstructs new.
    This verifies the roundtrip: diff is both complete and sufficient.
    """
    old = data.draw(plan_snapshot_st())
    new = data.draw(plan_snapshot_st())

    changes = diff_plan(old, new)

    # Reconstruct new from old + changes
    reconstructed = deepcopy(old)

    # Apply summary changes
    for c in changes:
        if c.field_path == "summary" and c.change_type == "modify":
            reconstructed.summary = c.new_value

    # Apply action changes
    action_deletes = [c for c in changes if c.field_path.startswith("actions[") and c.change_type == "delete"]
    action_adds = [c for c in changes if c.field_path.startswith("actions[") and c.change_type == "add"]
    action_modifies = [
        c for c in changes
        if c.field_path.startswith("actions[") and c.change_type == "modify"
    ]

    # Process deletes
    delete_action_ids = set()
    for c in action_deletes:
        aid = c.field_path.split("[")[1].split("]")[0]
        delete_action_ids.add(aid)
    reconstructed.actions = [a for a in reconstructed.actions if a.action_id not in delete_action_ids]

    # Process adds
    for c in action_adds:
        item_dict = json.loads(c.new_value)
        reconstructed.actions.insert(
            c.new_index if c.new_index is not None else len(reconstructed.actions),
            ActionItem(**item_dict),
        )

    # Process field-level modifies
    for c in action_modifies:
        if "." in c.field_path:
            # Field-level: actions[id].field
            parts = c.field_path.split(".")
            aid = parts[0].split("[")[1].split("]")[0]
            field_name = parts[1]
            for a in reconstructed.actions:
                if a.action_id == aid:
                    val = c.new_value
                    # Deserialize if needed
                    if field_name == "priority":
                        val = json.loads(val)
                    setattr(a, field_name, val)
                    break

    # Reorder actions to match new
    new_action_map = {a.action_id: idx for idx, a in enumerate(new.actions)}
    reconstructed.actions.sort(
        key=lambda a: new_action_map.get(a.action_id, 999)
    )

    # Apply resource changes
    res_deletes = [c for c in changes if c.field_path.startswith("resources[") and c.change_type == "delete"]
    res_adds = [c for c in changes if c.field_path.startswith("resources[") and c.change_type == "add"]
    res_modifies = [c for c in changes if c.field_path.startswith("resources[") and c.change_type == "modify"]

    delete_res_ids = set()
    for c in res_deletes:
        rid = int(c.field_path.split("[")[1].split("]")[0])
        delete_res_ids.add(rid)
    reconstructed.resources = [r for r in reconstructed.resources if r.resource_id not in delete_res_ids]

    for c in res_adds:
        item_dict = json.loads(c.new_value)
        reconstructed.resources.insert(
            c.new_index if c.new_index is not None else len(reconstructed.resources),
            ResourceItem(**item_dict),
        )

    for c in res_modifies:
        if "." in c.field_path:
            parts = c.field_path.split(".")
            rid = int(parts[0].split("[")[1].split("]")[0])
            field_name = parts[1]
            for r in reconstructed.resources:
                if r.resource_id == rid:
                    val = c.new_value
                    if field_name == "quantity":
                        val = json.loads(val)
                    setattr(r, field_name, val)
                    break

    new_res_map = {r.resource_id: idx for idx, r in enumerate(new.resources)}
    reconstructed.resources.sort(
        key=lambda r: new_res_map.get(r.resource_id, 999)
    )

    # Apply notification changes
    notif_deletes = [c for c in changes if c.field_path.startswith("notifications[") and c.change_type == "delete"]
    notif_adds = [c for c in changes if c.field_path.startswith("notifications[") and c.change_type == "add"]
    notif_modifies = [c for c in changes if c.field_path.startswith("notifications[") and c.change_type == "modify"]

    delete_notif_ids = set()
    for c in notif_deletes:
        nid = int(c.field_path.split("[")[1].split("]")[0])
        delete_notif_ids.add(nid)
    reconstructed.notifications = [
        n for n in reconstructed.notifications if n.notification_id not in delete_notif_ids
    ]

    for c in notif_adds:
        item_dict = json.loads(c.new_value)
        reconstructed.notifications.insert(
            c.new_index if c.new_index is not None else len(reconstructed.notifications),
            NotificationItem(**item_dict),
        )

    for c in notif_modifies:
        if "." in c.field_path:
            parts = c.field_path.split(".")
            nid = int(parts[0].split("[")[1].split("]")[0])
            field_name = parts[1]
            for n in reconstructed.notifications:
                if n.notification_id == nid:
                    setattr(n, field_name, c.new_value)
                    break

    new_notif_map = {n.notification_id: idx for idx, n in enumerate(new.notifications)}
    reconstructed.notifications.sort(
        key=lambda n: new_notif_map.get(n.notification_id, 999)
    )

    # Verify roundtrip: reconstructed should equal new
    assert reconstructed.summary == new.summary, (
        f"Summary mismatch: {reconstructed.summary!r} != {new.summary!r}"
    )

    assert len(reconstructed.actions) == len(new.actions), (
        f"Actions count mismatch: {len(reconstructed.actions)} != {len(new.actions)}"
    )
    for i, (r, n) in enumerate(zip(reconstructed.actions, new.actions)):
        assert r.action_id == n.action_id, f"Action[{i}] id mismatch"
        assert r.description == n.description, f"Action[{i}] description mismatch"
        assert r.priority == n.priority, f"Action[{i}] priority mismatch"
        assert r.assignee == n.assignee, f"Action[{i}] assignee mismatch"
        assert r.status == n.status, f"Action[{i}] status mismatch"

    assert len(reconstructed.resources) == len(new.resources), (
        f"Resources count mismatch: {len(reconstructed.resources)} != {len(new.resources)}"
    )
    for i, (r, n) in enumerate(zip(reconstructed.resources, new.resources)):
        assert r.resource_id == n.resource_id, f"Resource[{i}] id mismatch"
        assert r.type == n.type, f"Resource[{i}] type mismatch"
        assert r.name == n.name, f"Resource[{i}] name mismatch"
        assert r.quantity == n.quantity, f"Resource[{i}] quantity mismatch"
        assert r.location == n.location, f"Resource[{i}] location mismatch"

    assert len(reconstructed.notifications) == len(new.notifications), (
        f"Notifications count mismatch: {len(reconstructed.notifications)} != {len(new.notifications)}"
    )
    for i, (r, n) in enumerate(zip(reconstructed.notifications, new.notifications)):
        assert r.notification_id == n.notification_id, f"Notification[{i}] id mismatch"
        assert r.channel == n.channel, f"Notification[{i}] channel mismatch"
        assert r.target == n.target, f"Notification[{i}] target mismatch"
        assert r.message == n.message, f"Notification[{i}] message mismatch"
        assert r.status == n.status, f"Notification[{i}] status mismatch"
