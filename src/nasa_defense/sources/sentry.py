from __future__ import annotations

from typing import Any

from .. import config
from ..models import SentryObject
from .http import get_json


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _to_int(value: Any) -> int:
    f = _to_float(value)
    return 0 if f is None else int(f)


def parse(raw: dict) -> list[SentryObject]:
    objects: list[SentryObject] = []
    for row in raw.get("data", []):
        des = row.get("des")
        if not des:
            continue
        ps_cum = _to_float(row.get("ps_cum"))
        objects.append(
            SentryObject(
                des=des,
                ts_max=_to_int(row.get("ts_max")),
                ps_cum=-99.0 if ps_cum is None else ps_cum,
                ip=_to_float(row.get("ip")) or 0.0,
                diameter_km=_to_float(row.get("diameter")),
                last_obs=row.get("last_obs") or "",
            )
        )
    return objects


def fetch() -> list[SentryObject]:
    return parse(get_json(config.SENTRY_API))
