from __future__ import annotations

from datetime import date
from typing import Any

from . import config
from .models import CloseApproach, Event, Fireball, SentryObject, parse_cad_date


def _sev(event_type: str, obj: SentryObject) -> str:
    if event_type == "SENTRY_TORINO_UP" or obj.ts_max >= 1:
        return "critical"
    return "high"


def detect_sentry(previous: dict[str, dict[str, Any]], current: list[SentryObject]) -> list[Event]:
    events: list[Event] = []
    current_by_des = {o.des: o for o in current}

    for obj in current:
        key = f"sentry:{obj.des}"
        prev = previous.get(obj.des)
        if prev is None:
            if obj.noteworthy:
                events.append(
                    Event(
                        "SENTRY_NEW",
                        key,
                        _sev("SENTRY_NEW", obj),
                        {
                            "des": obj.des,
                            "ts_max": obj.ts_max,
                            "ps_cum": obj.ps_cum,
                            "ip": obj.ip,
                            "diameter_km": obj.diameter_km,
                        },
                    )
                )
            continue

        if obj.ts_max > prev["ts_max"] and obj.ts_max >= 1:
            events.append(
                Event(
                    "SENTRY_TORINO_UP",
                    key,
                    "critical",
                    {
                        "des": obj.des,
                        "ts_prev": prev["ts_max"],
                        "ts_now": obj.ts_max,
                        "ps_prev": prev["ps_cum"],
                        "ps_now": obj.ps_cum,
                        "ip_prev": prev["ip"],
                        "ip_now": obj.ip,
                    },
                )
            )
        elif obj.ts_max < prev["ts_max"] and prev["ts_max"] >= 1:
            events.append(
                Event(
                    "SENTRY_TORINO_DOWN",
                    key,
                    _sev("SENTRY_TORINO_DOWN", obj),
                    {
                        "des": obj.des,
                        "ts_prev": prev["ts_max"],
                        "ts_now": obj.ts_max,
                    },
                )
            )

        if (
            obj.ps_cum - prev["ps_cum"] >= config.PALERMO_STEP
            and obj.ps_cum >= config.PALERMO_FLOOR
        ):
            events.append(
                Event(
                    "SENTRY_PALERMO_UP",
                    key,
                    _sev("SENTRY_PALERMO_UP", obj),
                    {
                        "des": obj.des,
                        "ps_prev": prev["ps_cum"],
                        "ps_now": obj.ps_cum,
                    },
                )
            )

        if (
            prev["ip"] > 0
            and obj.ip >= prev["ip"] * config.IP_JUMP_FACTOR
            and obj.ip >= config.IP_FLOOR
        ):
            events.append(
                Event(
                    "SENTRY_IP_JUMP",
                    key,
                    _sev("SENTRY_IP_JUMP", obj),
                    {
                        "des": obj.des,
                        "ip_prev": prev["ip"],
                        "ip_now": obj.ip,
                    },
                )
            )

    for des, prev in previous.items():
        if des not in current_by_des and prev.get("noteworthy"):
            events.append(
                Event(
                    "SENTRY_REMOVED",
                    f"sentry:{des}",
                    "info",
                    {
                        "des": des,
                        "ts_prev": prev["ts_max"],
                    },
                )
            )

    return events


def sentry_snapshot(current: list[SentryObject]) -> dict[str, dict]:
    return {o.des: o.to_state() for o in current}


def cad_severity(approach: CloseApproach) -> str:
    if approach.dist_ld < 1.0:
        return "critical"
    if approach.dist_ld < config.CAD_HIGH_LD or (
        approach.h is not None and approach.h <= config.CAD_NOTEWORTHY_H_MAX
    ):
        return "high"
    return "info"


def _cad_payload(approach: CloseApproach) -> dict[str, Any]:
    return {
        "des": approach.des,
        "cd": approach.cd,
        "dist_au": approach.dist_au,
        "dist_ld": approach.dist_ld,
        "v_rel_kms": approach.v_rel_kms,
        "h": approach.h,
    }


def detect_cad(previous: dict[str, dict[str, Any]], current: list[CloseApproach]) -> list[Event]:
    events: list[Event] = []
    today = date.today()
    for approach in current:
        approach_date = parse_cad_date(approach.cd)
        if approach_date is not None and approach_date < today:
            continue  # already happened — don't alert on past approaches
        state_key = f"{approach.des}:{approach.cd}"
        if state_key in previous:
            continue  # already-known pass; never re-alert
        severity = cad_severity(approach)
        event_key = f"cad:{approach.des}:{approach.cd}"
        payload = _cad_payload(approach)
        if config.CAD_SUBLUNAR_ALWAYS and approach.dist_ld < 1.0:
            events.append(Event("CAD_SUBLUNAR", event_key, severity, payload))
        elif approach.dist_ld <= config.CAD_MAX_LUNAR_DISTANCES:
            events.append(Event("CAD_NEW_CLOSE", event_key, severity, payload))
    return events


def cad_snapshot(current: list[CloseApproach]) -> dict[str, dict]:
    return {f"{a.des}:{a.cd}": {**a.to_state(), "severity": cad_severity(a)} for a in current}


def fireball_severity(fireball: Fireball) -> str:
    return "high" if fireball.impact_e_kt >= config.FIREBALL_HIGH_KT else "info"


def detect_fireball(previous: dict[str, dict[str, Any]], current: list[Fireball]) -> list[Event]:
    events: list[Event] = []
    for fireball in current:
        if fireball.date in previous:
            continue  # already seen this bolide
        if fireball.impact_e_kt < config.FIREBALL_ENERGY_MIN_KT:
            continue  # below the reporting floor
        events.append(
            Event(
                "FIREBALL_NEW",
                f"fireball:{fireball.date}",
                fireball_severity(fireball),
                {
                    "date": fireball.date,
                    "impact_e_kt": fireball.impact_e_kt,
                    "energy": fireball.energy,
                    "lat": fireball.lat,
                    "lon": fireball.lon,
                },
            )
        )
    return events


def fireball_snapshot(current: list[Fireball]) -> dict[str, dict]:
    return {fb.date: fb.to_state() for fb in current}
