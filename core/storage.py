from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.models import RunAudit


INDEX_FILENAME = "index.json"
RUNS_DIRNAME = "runs"


def _project_root() -> Path:
    return Path.cwd()


def get_runs_dir() -> Path:
    runs_dir = _project_root() / RUNS_DIRNAME
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def ensure_run_dir(run_id: str) -> Path:
    run_dir = get_runs_dir() / run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    return run_dir


def get_audit_path(run_id: str) -> Path:
    return ensure_run_dir(run_id) / "audit.json"


def _index_path() -> Path:
    return get_runs_dir() / INDEX_FILENAME


def load_index() -> List[Dict[str, Any]]:
    index_path = _index_path()
    if not index_path.exists():
        return []
    with index_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_index(entries: List[Dict[str, Any]]) -> None:
    index_path = _index_path()
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2, ensure_ascii=True)


def upsert_index_entry(
    run_id: str,
    demo_type: str,
    started_at: datetime,
    finished_at: datetime | None = None,
) -> None:
    entries = load_index()
    updated = False
    for entry in entries:
        if entry.get("run_id") == run_id:
            entry.update(
                {
                    "demo_type": demo_type,
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat() if finished_at else None,
                }
            )
            updated = True
            break
    if not updated:
        entries.append(
            {
                "run_id": run_id,
                "demo_type": demo_type,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat() if finished_at else None,
            }
        )
    save_index(entries)


def list_runs() -> List[Dict[str, Any]]:
    entries = load_index()

    def _sort_key(entry: Dict[str, Any]) -> str:
        return entry.get("started_at") or ""

    return sorted(entries, key=_sort_key, reverse=True)


def load_run(run_id: str) -> RunAudit:
    audit_path = get_audit_path(run_id)
    with audit_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return RunAudit.model_validate(payload)


def delete_run(run_id: str) -> None:
    run_dir = get_runs_dir() / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    entries = [entry for entry in load_index() if entry.get("run_id") != run_id]
    save_index(entries)


def clear_runs() -> None:
    runs_dir = get_runs_dir()
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    save_index([])


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def cleanup_old_runs(ttl_days: int) -> None:
    if ttl_days <= 0:
        return
    threshold = datetime.now(timezone.utc).timestamp() - (ttl_days * 86400)
    entries = load_index()
    remaining: List[Dict[str, Any]] = []
    for entry in entries:
        finished = _parse_timestamp(entry.get("finished_at"))
        started = _parse_timestamp(entry.get("started_at"))
        timestamp = finished or started
        if timestamp and timestamp.timestamp() < threshold:
            run_id = entry.get("run_id")
            if run_id:
                run_dir = get_runs_dir() / run_id
                if run_dir.exists():
                    shutil.rmtree(run_dir)
            continue
        remaining.append(entry)
    if remaining != entries:
        save_index(remaining)
