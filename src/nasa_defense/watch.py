from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import config, detect, render, state
from .models import Event
from .sources import sentry


def labels_for(event: Event) -> list[str]:
    labels = ["planetary-defense", "sentry", f"severity-{event.severity}"]
    if event.payload.get("ts_now", event.payload.get("ts_max", 0)) and event.severity == "critical":
        labels.append("torino-ge-1")
    return labels


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_state(state_dir: Path, snapshot: dict) -> None:
    state.save(state_dir / "sentry.json", snapshot)
    state.save(state_dir / "meta.json",
               {"schema_version": config.SCHEMA_VERSION, "last_run_utc": _now(),
                "cold_start": False})


def run(*, state_dir: Path, sink, dry_run: bool = False, fetch_sentry=sentry.fetch) -> list[Event]:
    meta = state.load(state_dir / "meta.json")
    cold = not meta or meta.get("cold_start", True)

    current = fetch_sentry()
    snapshot = detect.sentry_snapshot(current)

    if cold:
        if not dry_run:
            _save_state(state_dir, snapshot)
        return []

    previous = state.load(state_dir / "sentry.json")
    events = detect.detect_sentry(previous, current)

    for event in events:
        title, body = render.render(event)
        if dry_run:
            print(f"[{event.severity}] {event.type}: {title}")
        else:
            sink.upsert(event.key, title, body, labels_for(event))

    if not dry_run:
        _save_state(state_dir, snapshot)
    return events
