from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import config, detect, render, site, state
from .models import Event
from .sinks import fanout
from .sources import apophis, close_approaches, fireballs, neows, sentry

_BASE_LABEL = "planetary-defense"


def labels_for(event: Event) -> list[str]:
    labels = [_BASE_LABEL, "sentry", f"severity-{event.severity}"]
    # Label objects currently at Torino >= 1, read from the actual Torino value the
    # event carries (TORINO_UP/DOWN expose `ts_now`; SENTRY_NEW exposes `ts_max`).
    current_torino = max(event.payload.get("ts_now", 0), event.payload.get("ts_max", 0))
    if current_torino >= 1:
        labels.append("torino-ge-1")
    return labels


def labels_cad(event: Event) -> list[str]:
    labels = [_BASE_LABEL, "close-approach", f"severity-{event.severity}"]
    if event.type == "CAD_SUBLUNAR":
        labels.append("sub-lunar")
    return labels


def labels_fireball(event: Event) -> list[str]:
    return [_BASE_LABEL, "fireball", f"severity-{event.severity}"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_meta(state_dir: Path) -> None:
    state.save(
        state_dir / "meta.json",
        {"schema_version": config.SCHEMA_VERSION, "last_run_utc": _now(), "cold_start": False},
    )


def _sources():
    # (state filename, fetch, detect, snapshot, labels)
    return [
        ("sentry.json", sentry.fetch, detect.detect_sentry, detect.sentry_snapshot, labels_for),
        (
            "close_approaches.json",
            close_approaches.fetch,
            detect.detect_cad,
            detect.cad_snapshot,
            labels_cad,
        ),
        (
            "fireballs.json",
            fireballs.fetch,
            detect.detect_fireball,
            detect.fireball_snapshot,
            labels_fireball,
        ),
    ]


def _apply_enrichment(events: list[Event], enrichment: dict) -> None:
    """Add the NeoWs PHA flag + diameter to any event whose object matches a
    designation in the enrichment lookup (best-effort; missing keys are fine)."""
    for event in events:
        des = event.payload.get("des")
        if des and des in enrichment:
            event.payload["pha"] = enrichment[des]["pha"]
            event.payload["neows_diameter_m"] = enrichment[des].get("diameter_m")


def _seed(state_dir: Path, sources) -> None:
    """Cold start: write every source's current snapshot, emit nothing."""
    for filename, fetch_fn, _detect, snapshot_fn, _labels in sources:
        state.save(state_dir / filename, snapshot_fn(fetch_fn()))
    _save_meta(state_dir)


def _process_source(state_dir: Path, source, sink, dry_run: bool, enrichment: dict):
    # pylint: disable=too-many-locals
    """Run one source end to end. Returns (events, ok); ok=False means its state
    must NOT advance (so it re-detects next run)."""
    filename, fetch_fn, detect_fn, snapshot_fn, labels_fn = source
    try:
        current = fetch_fn()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"source {filename}: fetch failed: {exc}", file=sys.stderr)
        return [], False

    previous = state.load(state_dir / filename)
    events = detect_fn(previous, current)
    _apply_enrichment(events, enrichment)

    try:
        for event in events:
            title, body = render.render(event)
            if dry_run:
                print(f"[{event.severity}] {event.type}: {title}")
            else:
                sink.upsert(event.key, title, body, labels_fn(event))
                fanout.fan_out(event, title, body)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"sink {filename}: emit failed: {exc}", file=sys.stderr)
        return [], False

    if not dry_run:
        state.save(state_dir / filename, snapshot_fn(current))
    return events, True


def _update_apophis(sink, dry_run: bool) -> None:
    """Upsert the perpetual Apophis 2029 tracking Issue (best-effort, every run)."""
    days = (date.fromisoformat(config.APOPHIS_DATE) - date.today()).days
    payload: dict[str, object] = {"days_until": days}
    if not dry_run:
        approach = apophis.fetch_approach()
        if approach is not None:
            payload.update(
                {
                    "cd": approach.cd,
                    "dist_ld": approach.dist_ld,
                    "dist_au": approach.dist_au,
                    "v_rel_kms": approach.v_rel_kms,
                }
            )
    event = Event("APOPHIS_ANCHOR", "apophis:2029", "info", payload)
    title, body = render.render(event)
    if dry_run:
        print(f"[apophis] {title}")
        return
    try:
        sink.upsert(event.key, title, body, [_BASE_LABEL, "apophis"])
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"apophis update failed: {exc}", file=sys.stderr)


def _maybe_render_site(state_dir: Path) -> None:
    """Render the static Pages site from committed state (best-effort, non-blocking)."""
    if not config.SITE_ENABLED:
        return
    try:
        site.write(state_dir, config.SITE_DIR)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"site render failed: {exc}", file=sys.stderr)


def run(*, state_dir: Path, sink, dry_run: bool = False) -> list[Event]:
    meta = state.load(state_dir / "meta.json")
    cold = not meta or meta.get("cold_start", True)
    sources = _sources()

    if cold:
        if not dry_run:
            _seed(state_dir, sources)
        _update_apophis(sink, dry_run)
        if not dry_run:
            _maybe_render_site(state_dir)
        return []

    enrichment = neows.fetch_pha_lookup()  # best-effort; {} on failure
    all_events: list[Event] = []
    failures: list[str] = []
    for source in sources:
        events, ok = _process_source(state_dir, source, sink, dry_run, enrichment)
        all_events.extend(events)
        if not ok:
            failures.append(source[0])

    _update_apophis(sink, dry_run)
    if not dry_run:
        _save_meta(state_dir)
        _maybe_render_site(state_dir)
    if failures:
        raise RuntimeError(f"source(s) failed this run: {', '.join(failures)}")
    return all_events
