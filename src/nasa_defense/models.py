from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import config

SEVERITY_RANK = {"info": 0, "high": 1, "critical": 2}


def severity_at_least(sev: str, floor: str) -> bool:
    return SEVERITY_RANK[sev] >= SEVERITY_RANK[floor]


@dataclass(frozen=True)
class SentryObject:
    des: str
    ts_max: int
    ps_cum: float
    ip: float
    diameter_km: float | None
    last_obs: str

    @property
    def diameter_m(self) -> float | None:
        return None if self.diameter_km is None else self.diameter_km * 1000.0

    @property
    def noteworthy(self) -> bool:
        d = self.diameter_m
        return (
            self.ps_cum >= config.PALERMO_FLOOR
            or self.ts_max >= 1
            or (d is not None and d >= config.NOTEWORTHY_DIAMETER_M)
            or self.ip >= config.IP_FLOOR
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "ts_max": self.ts_max,
            "ps_cum": self.ps_cum,
            "ip": self.ip,
            "diameter_km": self.diameter_km,
            "last_obs": self.last_obs,
            "noteworthy": self.noteworthy,
        }


@dataclass(frozen=True)
class Event:
    type: str
    key: str
    severity: str
    payload: dict[str, Any]
