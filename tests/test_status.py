from __future__ import annotations

import json
from datetime import date, timedelta

from nasa_defense import state, status
from nasa_defense.models import parse_cad_date


def _cad(when: date, hhmm: str = "22:05") -> str:
    """A CNEOS CAD calendar-date string ('2029-Apr-13 22:05') for a given date."""
    return f"{when.strftime('%Y-%b-%d')} {hhmm}"


def _seed(tmp_path, *, failures: int = 0) -> None:
    today = date.today()
    state.save(
        tmp_path / "close_approaches.json",
        {
            # deliberately unsorted: the far approach first, a PAST one in the
            # middle — build() must drop the past one and sort soonest-first
            f"2026 FAR:{_cad(today + timedelta(days=60))}": {
                "dist_ld": 4.95,
                "h": 26.1,
                "severity": "info",
                "v_rel_kms": 9.6,
            },
            f"2010 PAST:{_cad(today - timedelta(days=30))}": {
                "dist_ld": 0.50,
                "h": 22.0,
                "severity": "critical",
                "v_rel_kms": 20.0,
            },
            f"2026 SOON:{_cad(today + timedelta(days=25))}": {
                "dist_ld": 2.19,
                "h": 22.75,
                "severity": "high",
                "v_rel_kms": 12.4,
            },
        },
    )
    state.save(
        tmp_path / "sentry.json",
        {
            "101955": {"noteworthy": True, "ps_cum": -1.4, "ts_max": 0, "ip": 5.7e-4},
            "1979 XB": {"noteworthy": False, "ps_cum": -2.7, "ts_max": 0, "ip": 8.5e-7},
        },
    )
    state.save(tmp_path / "fireballs.json", {})
    state.save(
        tmp_path / "meta.json",
        {
            "last_run_utc": "2026-07-22T12:00:00+00:00",
            "cold_start": False,
            "consecutive_failures": {
                "close_approaches.json": failures,
                "fireballs.json": 0,
                "sentry.json": 0,
            },
        },
    )


def test_build_contract_shape_and_ordering(tmp_path):
    _seed(tmp_path)
    doc = status.build(tmp_path)

    assert doc["schema"] == 1
    assert doc["project"] == "nasa-defense"
    assert doc["site"] == "https://ryastra.github.io/nasa-defense/"
    assert doc["fresh_for_hours"] == 36
    assert doc["ok"] is True
    assert doc["updated_utc"].endswith("Z")

    # headline names the SOONEST FUTURE approach — never the past one
    assert "2026 SOON" in doc["headline"]
    assert "2010 PAST" not in json.dumps(doc)
    assert "2.19 LD" in doc["headline"]
    assert len(doc["headline"]) <= 120

    labels = {m["label"]: m["value"] for m in doc["metrics"]}
    assert labels["Sentry noteworthy"] == "1"
    assert labels["Upcoming approaches"] == "2"
    assert 1 <= len(doc["metrics"]) <= 4

    assert len(doc["items"]) == 2  # past approach dropped
    assert [i["text"].split(" — ")[0] for i in doc["items"]] == ["2026 SOON", "2026 FAR"]
    for item in doc["items"]:
        assert len(item["text"]) <= 140
        assert "km/s" in item["text"]
        assert item["url"].startswith("https://ssd.jpl.nasa.gov/")
        assert parse_cad_date(item["when_utc"]) is None  # when_utc is ISO, not CAD format
        date.fromisoformat(item["when_utc"])  # ...and parses as a date


def test_upstream_failure_flips_ok(tmp_path):
    _seed(tmp_path, failures=3)
    assert status.build(tmp_path)["ok"] is False


def test_no_upcoming_approaches_headline(tmp_path):
    _seed(tmp_path)
    today = date.today()
    state.save(
        tmp_path / "close_approaches.json",
        {
            f"2010 PAST:{_cad(today - timedelta(days=30))}": {
                "dist_ld": 0.5,
                "h": 22.0,
                "severity": "info",
                "v_rel_kms": 20.0,
            }
        },
    )
    doc = status.build(tmp_path)
    assert doc["headline"] == "No upcoming close approaches on file"
    assert doc["items"] == []
