"""Engine version stamps for runs. ENGINE_VERSION is the first 12 hex chars of a
sha256 over the engine-affecting source files; any change to prompts,
orchestrator, truth, or paradigms bumps it. Runs are stamped per scenario with
scenario_engine_version() — the engine hash combined with that scenario's
definition — and /api/demo only serves runs stamped with the scenario's current
version, so editing a sample pool invalidates only that scenario's demos."""

from __future__ import annotations

import hashlib
import json
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

    Fields that don't affect run validity (validation results, provenance,
    title — never shown to agents) are excluded, so recording a validation or
    retitling a scenario doesn't orphan seeded demo runs. The JSON is
    canonicalised (sorted keys) so a scenario round-tripped through Postgres
    jsonb, which reorders object keys, stamps identically."""
    h = hashlib.sha256()
    h.update(ENGINE_VERSION.encode())
    payload = scenario.model_dump(
        mode="json", exclude={"validation", "created_at", "is_sample", "title"}
    )
    h.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()[:12]
