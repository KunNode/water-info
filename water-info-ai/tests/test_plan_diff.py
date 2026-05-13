"""Unit tests for plan_diff.py — field-level diff generator."""

import json

from app.services.plan_diff import (
    ActionItem,
    ChangeEntry,
    NotificationItem,
    PlanSnapshot,
    ResourceItem,
    diff_plan,
)


class TestDiffSummary:
    def test_no_change(self):
        old = PlanSnapshot(summary="hello")
        new = PlanSnapshot(summary="hello")
        assert diff_plan(old, new) == []

    def test_modify(self):
        old = PlanSnapshot(summary="old text")
        new = PlanSnapshot(summary="new text")
        changes = diff_plan(old, new)
        assert len(changes) == 1
        c = changes[0]
        assert c.field_path == "summary"
        assert c.change_type == "modify"
        assert c.old_value == "old text"
        assert c.new_value == "new text"

    def test_empty_to_nonempty(self):
        old = PlanSnapshot(summary="")
        new = PlanSnapshot(summary="content")
        changes = diff_plan(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "modify"


class TestDiffActions:
    def test_add_action(self):
        old = PlanSnapshot()
        new = PlanSnapshot(actions=[
            ActionItem(action_id="a-001", description="do something", priority=1),
        ])
        changes = diff_plan(old, new)
        assert len(changes) == 1
        c = changes[0]
        assert c.field_path == "actions[a-001]"
        assert c.change_type == "add"
        assert c.old_value is None
        assert c.new_index == 0
        # new_value should be a JSON serialization of the action
        parsed = json.loads(c.new_value)
        assert parsed["action_id"] == "a-001"
        assert parsed["description"] == "do something"

    def test_delete_action(self):
        old = PlanSnapshot(actions=[
            ActionItem(action_id="a-001", description="task"),
        ])
        new = PlanSnapshot()
        changes = diff_plan(old, new)
        assert len(changes) == 1
        c = changes[0]
        assert c.field_path == "actions[a-001]"
        assert c.change_type == "delete"
        assert c.new_value is None
        assert c.old_index == 0

    def test_modify_field(self):
        old = PlanSnapshot(actions=[
            ActionItem(action_id="a-001", description="old desc", priority=1),
        ])
        new = PlanSnapshot(actions=[
            ActionItem(action_id="a-001", description="new desc", priority=2),
        ])
        changes = diff_plan(old, new)
        assert len(changes) == 2
        paths = {c.field_path for c in changes}
        assert "actions[a-001].description" in paths
        assert "actions[a-001].priority" in paths
        for c in changes:
            assert c.change_type == "modify"

    def test_order_only_change(self):
        old = PlanSnapshot(actions=[
            ActionItem(action_id="a-001", description="first"),
            ActionItem(action_id="a-002", description="second"),
        ])
        new = PlanSnapshot(actions=[
            ActionItem(action_id="a-002", description="second"),
            ActionItem(action_id="a-001", description="first"),
        ])
        changes = diff_plan(old, new)
        # Both items changed position
        assert len(changes) == 2
        for c in changes:
            assert c.change_type == "modify"
            assert c.old_value is None
            assert c.new_value is None
            assert c.old_index is not None
            assert c.new_index is not None
            assert c.old_index != c.new_index


class TestDiffResources:
    def test_add_resource(self):
        old = PlanSnapshot()
        new = PlanSnapshot(resources=[
            ResourceItem(resource_id=1, type="sandbag", name="沙袋", quantity=100),
        ])
        changes = diff_plan(old, new)
        assert len(changes) == 1
        c = changes[0]
        assert c.field_path == "resources[1]"
        assert c.change_type == "add"

    def test_modify_resource_field(self):
        old = PlanSnapshot(resources=[
            ResourceItem(resource_id=1, type="sandbag", name="沙袋", quantity=100),
        ])
        new = PlanSnapshot(resources=[
            ResourceItem(resource_id=1, type="sandbag", name="沙袋", quantity=200),
        ])
        changes = diff_plan(old, new)
        assert len(changes) == 1
        c = changes[0]
        assert c.field_path == "resources[1].quantity"
        assert c.change_type == "modify"
        assert c.old_value == "100"
        assert c.new_value == "200"


class TestDiffNotifications:
    def test_add_notification(self):
        old = PlanSnapshot()
        new = PlanSnapshot(notifications=[
            NotificationItem(notification_id=5, channel="sms", target="13800000000"),
        ])
        changes = diff_plan(old, new)
        assert len(changes) == 1
        c = changes[0]
        assert c.field_path == "notifications[5]"
        assert c.change_type == "add"

    def test_delete_notification(self):
        old = PlanSnapshot(notifications=[
            NotificationItem(notification_id=5, channel="sms", target="13800000000"),
        ])
        new = PlanSnapshot()
        changes = diff_plan(old, new)
        assert len(changes) == 1
        c = changes[0]
        assert c.field_path == "notifications[5]"
        assert c.change_type == "delete"


class TestDiffCombined:
    def test_no_changes_empty_snapshots(self):
        assert diff_plan(PlanSnapshot(), PlanSnapshot()) == []

    def test_multiple_sections_changed(self):
        old = PlanSnapshot(
            summary="old",
            actions=[ActionItem(action_id="a-001", description="task")],
            resources=[ResourceItem(resource_id=1, type="pump", name="水泵", quantity=5)],
        )
        new = PlanSnapshot(
            summary="new",
            actions=[ActionItem(action_id="a-001", description="updated task")],
            resources=[ResourceItem(resource_id=1, type="pump", name="水泵", quantity=10)],
        )
        changes = diff_plan(old, new)
        paths = {c.field_path for c in changes}
        assert "summary" in paths
        assert "actions[a-001].description" in paths
        assert "resources[1].quantity" in paths
