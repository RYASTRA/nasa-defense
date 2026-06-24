from __future__ import annotations

from typing import Any

from . import config
from .models import Event, SentryObject


def _sev(event_type: str, obj: SentryObject) -> str:
    if event_type == "SENTRY_TORINO_UP" or obj.ts_max >= 1:
        return "critical"
    return "high"


def detect_sentry(
    previous: dict[str, dict[str, Any]], current: list[SentryObject]
) -> list[Event]:
    events: list[Event] = []
    current_by_des = {o.des: o for o in current}

    for obj in current:
        key = f"sentry:{obj.des}"
        prev = previous.get(obj.des)
        if prev is None:
            if obj.noteworthy:
                events.append(Event("SENTRY_NEW", key, _sev("SENTRY_NEW", obj), {
                    "des": obj.des, "ts_max": obj.ts_max, "ps_cum": obj.ps_cum,
                    "ip": obj.ip, "diameter_km": obj.diameter_km,
                }))
            continue

        if obj.ts_max > prev["ts_max"] and obj.ts_max >= 1:
            events.append(Event("SENTRY_TORINO_UP", key, "critical", {
                "des": obj.des, "ts_prev": prev["ts_max"], "ts_now": obj.ts_max,
                "ps_prev": prev["ps_cum"], "ps_now": obj.ps_cum,
                "ip_prev": prev["ip"], "ip_now": obj.ip,
            }))
        elif obj.ts_max < prev["ts_max"] and prev["ts_max"] >= 1:
            events.append(Event("SENTRY_TORINO_DOWN", key, _sev("SENTRY_TORINO_DOWN", obj), {
                "des": obj.des, "ts_prev": prev["ts_max"], "ts_now": obj.ts_max,
            }))

        if obj.ps_cum - prev["ps_cum"] >= config.PALERMO_STEP and obj.ps_cum >= config.PALERMO_FLOOR:
            events.append(Event("SENTRY_PALERMO_UP", key, _sev("SENTRY_PALERMO_UP", obj), {
                "des": obj.des, "ps_prev": prev["ps_cum"], "ps_now": obj.ps_cum,
            }))

        if prev["ip"] > 0 and obj.ip >= prev["ip"] * config.IP_JUMP_FACTOR and obj.ip >= config.IP_FLOOR:
            events.append(Event("SENTRY_IP_JUMP", key, _sev("SENTRY_IP_JUMP", obj), {
                "des": obj.des, "ip_prev": prev["ip"], "ip_now": obj.ip,
            }))

    for des, prev in previous.items():
        if des not in current_by_des and prev.get("noteworthy"):
            events.append(Event("SENTRY_REMOVED", f"sentry:{des}", "info", {
                "des": des, "ts_prev": prev["ts_max"],
            }))

    return events


def sentry_snapshot(current: list[SentryObject]) -> dict[str, dict]:
    return {o.des: o.to_state() for o in current}
