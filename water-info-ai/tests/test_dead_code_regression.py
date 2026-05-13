"""Dead-code & contract regression grep checks.

Verifies that removed endpoints, dead functions, and forbidden imports
do not reappear in the codebase.

Validates: Requirements 8.5, 9.1
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Repository root (two levels up from this test file)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

WATER_INFO_AI = REPO_ROOT / "water-info-ai"
WATER_INFO_ADMIN_SRC = REPO_ROOT / "water-info-admin" / "src"
WATER_INFO_AI_APP = WATER_INFO_AI / "app"


THIS_FILE = Path(__file__).resolve()


def _grep(pattern: str, search_path: Path, *, include: str | None = None) -> list[str]:
    """Run grep -r and return matching lines, excluding this test file itself."""
    cmd = [
        "grep", "-r", "-n",
        "--include", include or "*",
        f"--exclude={THIS_FILE.name}",
        "--exclude-dir=__pycache__",
        "--exclude-dir=.egg-info",
        "--exclude-dir=water_info_ai.egg-info",
        pattern,
        str(search_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # grep returns 1 when no matches found, 0 when matches found
    if result.returncode == 0:
        return [line for line in result.stdout.strip().splitlines() if line]
    return []


class TestDeadCodeRemoval:
    """Req 9.1: Removed endpoint and dead functions must not reappear."""

    def test_no_update_plan_status_endpoint_in_python(self):
        """update_plan_status_endpoint must not exist in water-info-ai Python source."""
        matches = _grep(
            "update_plan_status_endpoint",
            WATER_INFO_AI,
            include="*.py",
        )
        assert matches == [], (
            f"Found 'update_plan_status_endpoint' in water-info-ai Python files:\n"
            + "\n".join(matches)
        )

    def test_no_patch_plan_status_route_in_python(self):
        """PATCH /api/v1/plans/{{plan_id}}/status literal must not exist in water-info-ai Python source."""
        matches = _grep(
            "PATCH /api/v1/plans/{plan_id}/status",
            WATER_INFO_AI,
            include="*.py",
        )
        assert matches == [], (
            f"Found 'PATCH /api/v1/plans/{{plan_id}}/status' in water-info-ai Python files:\n"
            + "\n".join(matches)
        )

    def test_no_updatePlanStatus_in_admin_src(self):
        """updatePlanStatus must not exist in water-info-admin/src."""
        if not WATER_INFO_ADMIN_SRC.exists():
            pytest.skip("water-info-admin/src not found")
        matches = _grep("updatePlanStatus", WATER_INFO_ADMIN_SRC)
        assert matches == [], (
            f"Found 'updatePlanStatus' in water-info-admin/src:\n"
            + "\n".join(matches)
        )

    def test_no_handleStatusChange_in_admin_src(self):
        """handleStatusChange must not exist in water-info-admin/src."""
        if not WATER_INFO_ADMIN_SRC.exists():
            pytest.skip("water-info-admin/src not found")
        matches = _grep("handleStatusChange", WATER_INFO_ADMIN_SRC)
        assert matches == [], (
            f"Found 'handleStatusChange' in water-info-admin/src:\n"
            + "\n".join(matches)
        )


class TestNoJwtImportRegression:
    """Req 8.5: Plan_Service must not directly parse JWT tokens."""

    def test_no_import_jwt(self):
        """'import jwt' must not appear in water-info-ai/app/."""
        if not WATER_INFO_AI_APP.exists():
            pytest.skip("water-info-ai/app not found")
        matches = _grep("import jwt", WATER_INFO_AI_APP, include="*.py")
        assert matches == [], (
            f"Found 'import jwt' in water-info-ai/app:\n"
            + "\n".join(matches)
        )

    def test_no_from_jose(self):
        """'from jose' must not appear in water-info-ai/app/."""
        if not WATER_INFO_AI_APP.exists():
            pytest.skip("water-info-ai/app not found")
        matches = _grep("from jose", WATER_INFO_AI_APP, include="*.py")
        assert matches == [], (
            f"Found 'from jose' in water-info-ai/app:\n"
            + "\n".join(matches)
        )

    def test_no_pyjwt(self):
        """'PyJWT' must not appear in water-info-ai/app/."""
        if not WATER_INFO_AI_APP.exists():
            pytest.skip("water-info-ai/app not found")
        matches = _grep("PyJWT", WATER_INFO_AI_APP, include="*.py")
        assert matches == [], (
            f"Found 'PyJWT' in water-info-ai/app:\n"
            + "\n".join(matches)
        )
