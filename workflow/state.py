"""
state.py — Workflow State lifecycle + pluggable storage backend.

Storage abstraction (STEP 2 requirement 2.3):
    `StateStore` is an ABC. `JsonStateStore` implements it as
    storage/runs/{run_id}/state.json. To switch to PostgreSQL/Redis later,
    implement `StateStore` again (e.g. `PostgresStateStore`) and change
    `get_store()` — nothing else changes.

State is persisted after EVERY step (not just at the end) via `save_state()`.
"""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import config
from .schemas import LlmCall, WorkflowState


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def new_run_id() -> str:
    """run_id = YYYYMMDD-HHMMSS-<6 hex>."""
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


# =========================================================================== #
# Storage backend abstraction
# =========================================================================== #
class StateStore(ABC):
    """Pluggable persistence for workflow state. Swap the impl to change backend."""

    @abstractmethod
    def save(self, state: WorkflowState) -> Path:
        """Persist state. Returns the location/path it was written to."""

    @abstractmethod
    def load(self, run_id: str) -> WorkflowState:
        """Load state for a run_id. Raises FileNotFoundError if missing."""

    @abstractmethod
    def list_runs(self) -> list[str]:
        """Return available run_ids, newest first."""

    @abstractmethod
    def run_dir(self, run_id: str) -> Path:
        """Directory holding this run's artifacts (state.json + artifacts/)."""


class JsonStateStore(StateStore):
    """JSON-on-disk backend under config.RUNS_DIR/{run_id}/state.json."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or config.RUNS_DIR)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "state.json"

    def save(self, state: WorkflowState) -> Path:
        state.updated_at = _utcnow()
        d = self.run_dir(state.run_id)
        (d / "artifacts").mkdir(parents=True, exist_ok=True)
        p = self.path(state.run_id)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state.model_dump(mode="json"), indent=2, ensure_ascii=False))
        tmp.replace(p)  # atomic-ish replace
        return p

    def load(self, run_id: str) -> WorkflowState:
        p = self.path(run_id)
        if not p.exists():
            raise FileNotFoundError(f"No state for run_id={run_id} at {p}")
        return WorkflowState.model_validate(json.loads(p.read_text()))

    def list_runs(self) -> list[str]:
        runs = [d.name for d in self.root.iterdir() if d.is_dir() and (d / "state.json").exists()]
        return sorted(runs, reverse=True)


# -- module-level store singleton ----------------------------------------- #
_store: Optional[StateStore] = None


def get_store() -> StateStore:
    global _store
    if _store is None:
        _store = JsonStateStore()
    return _store


# =========================================================================== #
# State lifecycle helpers
# =========================================================================== #
def create_state(original_input: str, run_id: Optional[str] = None) -> WorkflowState:
    """Create (and persist) a fresh state for a run."""
    st = WorkflowState(
        run_id=run_id or new_run_id(),
        status="created",
        created_at=_utcnow(),
        updated_at=_utcnow(),
        original_input=original_input,
        current_step="created",
    )
    save_state(st)
    return st


def save_state(state: WorkflowState) -> Path:
    """Persist state (recalculating token totals first). Returns the path."""
    state.recalc_token_totals()
    return get_store().save(state)


def load_state(run_id: str) -> WorkflowState:
    return get_store().load(run_id)


def record_call(state: WorkflowState, call: LlmCall, persist: bool = True) -> LlmCall:
    """Append a call to the token ledger, recalc totals, and persist."""
    state.token_usage.calls.append(call)
    state.recalc_token_totals()
    if persist:
        save_state(state)
    return call
