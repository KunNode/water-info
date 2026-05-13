"""Pure field-level diff generator for emergency plan snapshots.

Computes a list of ChangeEntry records describing the differences between
two plan snapshots across summary, actions, resources, and notifications.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionItem:
    action_id: str
    description: str = ""
    priority: int = 3
    assignee: str = ""
    status: str = "pending"


@dataclass
class ResourceItem:
    resource_id: int
    type: str = ""
    name: str = ""
    quantity: int = 0
    location: str = ""


@dataclass
class NotificationItem:
    notification_id: int
    channel: str = ""
    target: str = ""
    message: str = ""
    status: str = "pending"


@dataclass
class PlanSnapshot:
    summary: str = ""
    actions: list[ActionItem] = field(default_factory=list)
    resources: list[ResourceItem] = field(default_factory=list)
    notifications: list[NotificationItem] = field(default_factory=list)


@dataclass
class ChangeEntry:
    field_path: str
    change_type: str  # 'add' | 'delete' | 'modify'
    old_value: str | None = None
    new_value: str | None = None
    old_index: int | None = None
    new_index: int | None = None


def _serialize(value: Any) -> str:
    """Serialize a value to its canonical string representation."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _action_to_dict(item: ActionItem) -> dict:
    return {
        "action_id": item.action_id,
        "description": item.description,
        "priority": item.priority,
        "assignee": item.assignee,
        "status": item.status,
    }


def _resource_to_dict(item: ResourceItem) -> dict:
    return {
        "resource_id": item.resource_id,
        "type": item.type,
        "name": item.name,
        "quantity": item.quantity,
        "location": item.location,
    }


def _notification_to_dict(item: NotificationItem) -> dict:
    return {
        "notification_id": item.notification_id,
        "channel": item.channel,
        "target": item.target,
        "message": item.message,
        "status": item.status,
    }


def _diff_summary(old: str, new: str) -> list[ChangeEntry]:
    if old == new:
        return []
    return [ChangeEntry(
        field_path="summary",
        change_type="modify",
        old_value=old,
        new_value=new,
    )]


def _diff_list_section(
    old_items: list,
    new_items: list,
    key_field: str,
    path_prefix: str,
    comparable_fields: list[str],
    to_dict_fn,
) -> list[ChangeEntry]:
    """Diff a list section by aligning on business key.

    Produces add/delete/modify entries. For items present in both old and new,
    field-level changes are emitted. If only the position changed, a single
    modify entry with old_index/new_index is emitted.
    """
    changes: list[ChangeEntry] = []

    # Build index maps: key -> (index, item)
    old_map: dict[Any, tuple[int, Any]] = {}
    for idx, item in enumerate(old_items):
        key = getattr(item, key_field)
        old_map[key] = (idx, item)

    new_map: dict[Any, tuple[int, Any]] = {}
    for idx, item in enumerate(new_items):
        key = getattr(item, key_field)
        new_map[key] = (idx, item)

    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())

    # Deleted items
    for key in sorted(old_keys - new_keys, key=lambda k: old_map[k][0]):
        old_idx, old_item = old_map[key]
        changes.append(ChangeEntry(
            field_path=f"{path_prefix}[{key}]",
            change_type="delete",
            old_value=_serialize(to_dict_fn(old_item)),
            new_value=None,
            old_index=old_idx,
            new_index=None,
        ))

    # Added items
    for key in sorted(new_keys - old_keys, key=lambda k: new_map[k][0]):
        new_idx, new_item = new_map[key]
        changes.append(ChangeEntry(
            field_path=f"{path_prefix}[{key}]",
            change_type="add",
            old_value=None,
            new_value=_serialize(to_dict_fn(new_item)),
            old_index=None,
            new_index=new_idx,
        ))

    # Common items: check field-level changes and order changes
    for key in sorted(old_keys & new_keys, key=lambda k: old_map[k][0]):
        old_idx, old_item = old_map[key]
        new_idx, new_item = new_map[key]

        field_changes: list[ChangeEntry] = []
        for f in comparable_fields:
            old_val = getattr(old_item, f)
            new_val = getattr(new_item, f)
            if old_val != new_val:
                field_changes.append(ChangeEntry(
                    field_path=f"{path_prefix}[{key}].{f}",
                    change_type="modify",
                    old_value=_serialize(old_val),
                    new_value=_serialize(new_val),
                ))

        if field_changes:
            changes.extend(field_changes)
        elif old_idx != new_idx:
            # Only order changed — emit a single modify with index info
            changes.append(ChangeEntry(
                field_path=f"{path_prefix}[{key}]",
                change_type="modify",
                old_value=None,
                new_value=None,
                old_index=old_idx,
                new_index=new_idx,
            ))

    return changes


def diff_plan(old: PlanSnapshot, new: PlanSnapshot) -> list[ChangeEntry]:
    """Compute field-level diff between two plan snapshots.

    Pure function — no database access. Compares summary, actions, resources,
    and notifications sections independently.

    For list items, alignment is by business key:
    - actions: action_id
    - resources: resource_id
    - notifications: notification_id

    Order-only changes produce change_type='modify' with old_index/new_index set.
    """
    changes: list[ChangeEntry] = []

    # Summary
    changes.extend(_diff_summary(old.summary, new.summary))

    # Actions
    changes.extend(_diff_list_section(
        old_items=old.actions,
        new_items=new.actions,
        key_field="action_id",
        path_prefix="actions",
        comparable_fields=["description", "priority", "assignee", "status"],
        to_dict_fn=_action_to_dict,
    ))

    # Resources
    changes.extend(_diff_list_section(
        old_items=old.resources,
        new_items=new.resources,
        key_field="resource_id",
        path_prefix="resources",
        comparable_fields=["type", "name", "quantity", "location"],
        to_dict_fn=_resource_to_dict,
    ))

    # Notifications
    changes.extend(_diff_list_section(
        old_items=old.notifications,
        new_items=new.notifications,
        key_field="notification_id",
        path_prefix="notifications",
        comparable_fields=["channel", "target", "message", "status"],
        to_dict_fn=_notification_to_dict,
    ))

    return changes
