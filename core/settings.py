from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


SETTINGS_PATH = Path("settings.json")


@dataclass
class Settings:
    max_rows: int | None = None
    chunk_size: int | None = None
    ttl_days: int | None = None
    use_openai: bool = False


def load_settings() -> Settings:
    if not SETTINGS_PATH.exists():
        return Settings()
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return Settings()

    if not isinstance(payload, dict):
        return Settings()

    def _get_int(name: str) -> int | None:
        value = payload.get(name)
        if value is None:
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _get_bool(name: str) -> bool:
        value = payload.get(name)
        if isinstance(value, bool):
            return value
        return False

    return Settings(
        max_rows=_get_int("max_rows"),
        chunk_size=_get_int("chunk_size"),
        ttl_days=_get_int("ttl_days"),
        use_openai=_get_bool("use_openai"),
    )


def save_settings(settings: Settings) -> None:
    payload = {
        "max_rows": settings.max_rows,
        "chunk_size": settings.chunk_size,
        "ttl_days": settings.ttl_days,
        "use_openai": settings.use_openai,
    }
    with SETTINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
