"""CNEOS Sentry impact-risk table: fetch and parse into SentryObject records."""

from __future__ import annotations

from typing import Any

from .. import config
from ..models import SentryObject
from .http import get_json
from .parsing import finite_float


def _to_int(value: Any) -> int:
    f = finite_float(value)
    return 0 if f is None else int(f)


def parse(raw: dict) -> list[SentryObject]:
    """Convert a raw Sentry payload into records, skipping rows carrying no designation.

    A missing cumulative Palermo score becomes -99.0 rather than None so the value stays
    orderable against the configured floor, instead of forcing every comparison to guard
    for None.
    """
    objects: list[SentryObject] = []
    for row in raw.get("data", []):
        des = row.get("des")
        if not des:
            continue
        ps_cum = finite_float(row.get("ps_cum"))
        objects.append(
            SentryObject(
                des=des,
                ts_max=_to_int(row.get("ts_max")),
                ps_cum=-99.0 if ps_cum is None else ps_cum,
                ip=finite_float(row.get("ip")) or 0.0,
                diameter_km=finite_float(row.get("diameter")),
                last_obs=row.get("last_obs") or "",
            )
        )
    return objects


def fetch() -> list[SentryObject]:
    """Fetch and parse the current Sentry risk table."""
    return parse(get_json(config.SENTRY_API))
