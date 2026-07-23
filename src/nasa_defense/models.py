"""Dataclasses for the tracked near-Earth-object records and the events derived from them."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from . import config

SEVERITY_RANK = {"info": 0, "high": 1, "critical": 2}


def severity_at_least(sev: str, floor: str) -> bool:
    """True when `sev` ranks at least as high as `floor` on the info < high < critical scale."""
    return SEVERITY_RANK[sev] >= SEVERITY_RANK[floor]


def parse_cad_date(cd: str) -> date | None:
    """Parse a CNEOS CAD calendar-date string (e.g. '2029-Apr-13 21:46') to a date."""
    for fmt in ("%Y-%b-%d %H:%M", "%Y-%b-%d"):
        try:
            return datetime.strptime(cd.strip(), fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class SentryObject:
    """Asteroid or comet object from Sentry."""

    des: str
    ts_max: int
    ps_cum: float
    ip: float
    diameter_km: float | None
    last_obs: str

    @property
    def diameter_m(self) -> float | None:
        """Estimated diameter in metres, or None when Sentry publishes no size estimate."""
        return None if self.diameter_km is None else self.diameter_km * 1000.0

    @property
    def noteworthy(self) -> bool:
        """Whether this object clears any single materiality threshold.

        Deliberately an OR rather than an AND: an object earns attention if it is large, or rated
        on the Torino scale, or has a high cumulative Palermo score, or a non-trivial impact
        probability. Any one of those alone justifies alerting.
        """
        d = self.diameter_m
        return (
            self.ps_cum >= config.PALERMO_FLOOR
            or self.ts_max >= 1
            or (d is not None and d >= config.NOTEWORTHY_DIAMETER_M)
            or self.ip >= config.IP_FLOOR
        )

    def to_state(self) -> dict[str, Any]:
        """Serialise the fields that change detection compares between runs."""
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
    """Event record for change detection."""

    type: str
    key: str
    severity: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CloseApproach:
    """A near-Earth close approach from CNEOS CAD."""

    des: str
    cd: str  # calendar date/time, e.g. "2029-Apr-13 21:46"
    dist_au: float
    dist_ld: float  # miss distance in lunar distances
    v_rel_kms: float
    h: float | None  # absolute magnitude (size proxy)

    def to_state(self) -> dict[str, Any]:
        """Serialise the fields that change detection compares between runs."""
        return {
            "dist_au": self.dist_au,
            "dist_ld": self.dist_ld,
            "v_rel_kms": self.v_rel_kms,
            "h": self.h,
        }


@dataclass(frozen=True)
class Fireball:
    """An atmospheric bolide event from CNEOS Fireballs."""

    date: str  # full timestamp (UTC), unique key
    impact_e_kt: float  # calculated total impact energy, kilotons
    energy: float | None  # total radiated energy (x10^10 J)
    lat: float | None  # signed degrees (N positive, S negative)
    lon: float | None  # signed degrees (E positive, W negative)

    def to_state(self) -> dict[str, Any]:
        """Serialise the fields that change detection compares between runs."""
        return {
            "impact_e_kt": self.impact_e_kt,
            "energy": self.energy,
            "lat": self.lat,
            "lon": self.lon,
        }
