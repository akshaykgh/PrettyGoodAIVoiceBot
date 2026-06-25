from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_artifact_dirs() -> None:
    for name in ("events", "transcripts", "recordings", "reports"):
        (settings.artifacts_dir / name).mkdir(parents=True, exist_ok=True)


def call_slug(call_sid: str, scenario_id: str) -> str:
    return f"{scenario_id}-{call_sid}"


def events_path(slug: str) -> Path:
    ensure_artifact_dirs()
    return settings.artifacts_dir / "events" / f"{slug}.jsonl"


def transcript_path(slug: str) -> Path:
    ensure_artifact_dirs()
    return settings.artifacts_dir / "transcripts" / f"{slug}.txt"


def recording_path(slug: str, suffix: str = "mp3") -> Path:
    ensure_artifact_dirs()
    return settings.artifacts_dir / "recordings" / f"{slug}.{suffix}"


def call_index_path() -> Path:
    ensure_artifact_dirs()
    return settings.artifacts_dir / "calls.jsonl"


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def scenario_for_call(call_sid: str) -> str | None:
    path = call_index_path()
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("call_sid") == call_sid:
            return event.get("scenario_id")
    return None


class TranscriptWriter:
    def __init__(self, slug: str, scenario_id: str) -> None:
        self.path = transcript_path(slug)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(f"Scenario: {scenario_id}\nCall: {slug}\n\n", encoding="utf-8")

    def add_turn(self, speaker: str, text: str) -> None:
        cleaned = " ".join(text.split())
        if not cleaned:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{speaker}: {cleaned}\n\n")
