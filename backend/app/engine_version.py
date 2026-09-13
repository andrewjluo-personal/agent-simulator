"""Engine version stamp for runs. ENGINE_VERSION is the first 12 hex chars of a
sha256 over the engine-affecting source files; any change to prompts,
orchestrator, truth, paradigms, or samples bumps it. Demo runs are stamped at
creation and /api/demo only serves runs stamped with the current version, so
stale demos must be reseeded after any deploy that touches those files."""

from __future__ import annotations

import hashlib
from pathlib import Path

_STAMPED_FILES = (
    "prompts.py",
    "orchestrator.py",
    "truth.py",
    "paradigms.py",
    "samples.py",
)


def _compute() -> str:
    h = hashlib.sha256()
    base = Path(__file__).parent
    for name in _STAMPED_FILES:
        h.update((base / name).read_bytes())
    return h.hexdigest()[:12]


ENGINE_VERSION: str = _compute()
