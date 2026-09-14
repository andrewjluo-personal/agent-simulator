"""Engine version stamps for runs. ENGINE_VERSION is the first 12 hex chars of a
sha256 over the engine-affecting source files; any change to prompts,
orchestrator, truth, or paradigms bumps it. Runs are stamped per scenario with
scenario_engine_version() — the engine hash combined with that scenario's
definition — and /api/demo only serves runs stamped with the scenario's current
version, so editing a sample pool invalidates only that scenario's demos."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .models import Scenario

_STAMPED_FILES = (
    "prompts.py",
    "orchestrator.py",
    "truth.py",
    "paradigms.py",
)


def _compute() -> str:
    h = hashlib.sha256()
    base = Path(__file__).parent
    for name in _STAMPED_FILES:
        h.update((base / name).read_bytes())
    return h.hexdigest()[:12]


ENGINE_VERSION: str = _compute()


def scenario_engine_version(scenario: Scenario) -> str:
    """Per-scenario run stamp: engine hash plus the scenario definition.

    Fields that don't affect run validity (validation results, provenance) are
    excluded, so recording a validation doesn't orphan seeded demo runs."""
    h = hashlib.sha256()
    h.update(ENGINE_VERSION.encode())
    h.update(
        scenario.model_dump_json(exclude={"validation", "created_at", "is_sample"}).encode()
    )
    return h.hexdigest()[:12]
