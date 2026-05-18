"""In-memory idempotency cache for ``POST /api/v1/flood/sessions/{id}/resume``.

Decision (design §Error Handling — E10, Requirement 5.11, Property P15)
-----------------------------------------------------------------------
We chose option (a) — a process-local ``set[tuple[str, str]]`` of
``(checkpoint_id, state_sha1)`` keyed entries — over the two alternatives:

* (b) **Postgres advisory lock keyed on** ``sha1(checkpoint_id || state_hash)``:
  correct across workers, but couples a request-path latency budget to a
  database round-trip and a lock-release lifecycle that has to survive
  client disconnects. Kept as the documented upgrade path.
* (c) **A new ``resume_idempotency`` table**: persists state we don't need
  beyond the lifetime of an in-flight resumed run, costs another Flyway
  migration, and adds a periodic-cleanup chore. Rejected as overkill.

Multi-worker limitation
-----------------------
This cache is **per FastAPI worker process**. With more than one Uvicorn
worker, an identical replay can land on a different worker and slip past
this gate; Property P15's guarantee then degrades to "best-effort within
a single worker". The supported upgrade path (without changing this
module's public surface) is to swap the body of :meth:`try_acquire` for a
``pg_try_advisory_xact_lock(hashtext(checkpoint_id || state_sha1))`` call
inside the same transaction that begins the resumed run.
"""

from __future__ import annotations

import asyncio


class ResumeIdempotencyCache:
    """Process-local guard against duplicate ``POST /resume`` calls.

    The resume handler (Phase F task 22) calls :meth:`try_acquire` before
    starting the resumed graph run; on ``True`` it proceeds and emits a
    fresh ``run_id``, on ``False`` it returns HTTP 409
    ``{error_code: "resume_already_in_progress"}``. Once the resumed run
    finishes (success or failure) the handler calls :meth:`release` so a
    future identical replay can succeed.
    """

    def __init__(self) -> None:
        self._inflight: set[tuple[str, str]] = set()
        self._lock = asyncio.Lock()

    async def try_acquire(self, checkpoint_id: str, state_sha1: str) -> bool:
        """Atomically claim the ``(checkpoint_id, state_sha1)`` slot.

        Returns ``True`` when the caller now owns the slot (caller must
        eventually call :meth:`release`), or ``False`` when a prior call
        already owns it.
        """
        key = (checkpoint_id, state_sha1)
        async with self._lock:
            if key in self._inflight:
                return False
            self._inflight.add(key)
            return True

    async def release(self, checkpoint_id: str, state_sha1: str) -> None:
        """Release a previously-acquired slot. Idempotent."""
        key = (checkpoint_id, state_sha1)
        async with self._lock:
            self._inflight.discard(key)


_cache: ResumeIdempotencyCache | None = None


def get_resume_idempotency_cache() -> ResumeIdempotencyCache:
    """Return the process-local singleton cache."""
    global _cache
    if _cache is None:
        _cache = ResumeIdempotencyCache()
    return _cache
