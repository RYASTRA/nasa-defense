"""Static HTML dashboard generated from the committed state snapshots."""
# pylint: disable=line-too-long
from __future__ import annotations

import html
import json
import math
from datetime import date
from pathlib import Path

from . import config, state
from .models import parse_cad_date

_STYLE = """
:root{color-scheme:dark}
body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;max-width:880px;margin:2rem auto;padding:0 1rem;color:#c9d1d9;background:#0d1117;line-height:1.5}
h1{font-size:1.6rem;color:#e6edf3}
h2{margin-top:2rem;border-bottom:1px solid #30363d;padding-bottom:.3rem;color:#e6edf3}
.hero{background:#11233f;border:1px solid #1f3a5f;color:#e6edf3;padding:1.2rem 1.4rem;border-radius:10px}
.hero .days{font-size:2.4rem;font-weight:700;line-height:1.1;color:#58a6ff}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th{color:#8b949e}
th,td{text-align:left;padding:.35rem .5rem;border-bottom:1px solid #21262d}
.sev-critical{color:#ff7b72;font-weight:700}.sev-high{color:#ffa657}.sev-info{color:#8b949e}
.muted{color:#8b949e;font-size:.85rem}a{color:#58a6ff}
"""


def _esc(value: object) -> str:
    return html.escape(str(value))


def _format_size(diameter_km: float | None) -> str:
    if diameter_km is None:
        return "—"
    metres = diameter_km * 1000
    return f"~{diameter_km:.1f} km" if metres >= 1000 else f"~{metres:.0f} m"


_CAD_ALBEDO = 0.14  # standard assumed NEO geometric albedo (p_v): H=22 -> ~140 m, the PHA threshold


def _estimate_size_from_h(h: float | None) -> str:
    """Estimate a diameter string from absolute magnitude H (a size proxy).

    Close approaches carry no measured diameter, so size is derived from H via
    D_km = (1329 / sqrt(albedo)) * 10 ** (-0.2 * H), then formatted identically
    to measured Sentry diameters by delegating to _format_size. Non-real or
    non-finite H yields the em dash.
    """
    if isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h):
        return _format_size(None)
    diameter_km = 1329 / math.sqrt(_CAD_ALBEDO) * 10 ** (-0.2 * h)
    return _format_size(diameter_km)


def _format_ip_pct(ip: float | None) -> str:
    if (
        isinstance(ip, bool)
        or not isinstance(ip, (int, float))
        or not math.isfinite(ip)
        or ip <= 0.0
    ):
        return "—"
    pct = ip * 100
    if pct >= 10:
        return f"{pct:.0f}%"
    if pct >= 1:
        return f"{pct:.1f}%"
    if pct >= 0.1:
        return f"{pct:.2f}%"
    if pct >= 0.001:
        return f"{pct:.3f}%"
    return "<0.001%"


def _sentry_rows(sentry: dict) -> str:
    objs = [(des, d) for des, d in sentry.items() if d.get("noteworthy")]
    objs.sort(key=lambda kv: kv[1].get("ps_cum", -99.0), reverse=True)
    rows = [
        f"<tr><td>{_esc(des)}</td><td>{_esc(_format_size(d.get('diameter_km')))}</td>"
        f"<td>{_esc(d.get('ts_max', 0))}</td>"
        f"<td>{_esc(d.get('ps_cum'))}</td><td>{d.get('ip', 0.0):.2e}</td>"
        f"<td>{_esc(_format_ip_pct(d.get('ip', 0.0)))}</td></tr>"
        for des, d in objs[:15]
    ]
    return "".join(rows) or "<tr><td colspan='6' class='muted'>none</td></tr>"


def _cad_rows(cad: dict) -> str:
    today = date.today()
    upcoming = []
    for key, d in cad.items():
        des, _, cd = key.partition(":")  # split on the FIRST colon (cd itself contains colons)
        when = parse_cad_date(cd)
        if when is not None and when < today:
            continue  # already happened — this section is "upcoming" only
        upcoming.append((when or date.max, des, cd, d))
    upcoming.sort(key=lambda row: row[0])  # soonest first
    rows = [
        f"<tr><td>{_esc(des)}</td><td>{_esc(cd)}</td>"
        f"<td>{d.get('dist_ld', 0.0):.2f} LD</td>"
        f"<td>{_esc(_estimate_size_from_h(d.get('h')))}</td>"
        f"<td>{d.get('v_rel_kms', 0.0):.1f} km/s</td>"
        f"<td class='sev-{_esc(d.get('severity', 'info'))}'>{_esc(d.get('severity', 'info'))}</td></tr>"
        for _when, des, cd, d in upcoming[:15]
    ]
    return "".join(rows) or "<tr><td colspan='6' class='muted'>none upcoming</td></tr>"


def _fireball_rows(fireballs: dict) -> str:
    items = sorted(fireballs.items(), key=lambda kv: kv[0], reverse=True)
    rows = [
        f"<tr><td>{_esc(when)}</td><td>{d.get('impact_e_kt', 0.0):.2g} kt</td></tr>"
        for when, d in items[:15]
    ]
    return "".join(rows) or "<tr><td colspan='2' class='muted'>none</td></tr>"


def render(state_dir: Path) -> str:
    """Build the dashboard HTML from the state snapshots in `state_dir`."""
    sentry = state.load(state_dir / "sentry.json")
    cad = state.load(state_dir / "close_approaches.json")
    fireballs = state.load(state_dir / "fireballs.json")
    meta = state.load(state_dir / "meta.json")
    days = (date.fromisoformat(config.APOPHIS_DATE) - date.today()).days
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Planetary-Defense Watch</title><style>{_STYLE}</style></head>
<body>
<h1>🛰️ Planetary-Defense Watch</h1>
<p class="muted">Material changes in NASA/JPL near-Earth-object data. Last run: {_esc(meta.get("last_run_utc", "never"))}</p>
<div class="hero"><div>Apophis 2029 close approach</div>
<div class="days">{days} days</div>
<div>until 2029-04-13 — naked-eye visible (~mag 3), and <strong>not</strong> a threat.</div></div>
<h2>Sentry — noteworthy impact-risk objects</h2>
<table><tr><th>Object</th><th>Size</th><th>Torino</th><th>Palermo (cum.)</th><th>Impact prob.</th><th>Impact prob. (%)</th></tr>
{_sentry_rows(sentry)}</table>
<h2>Upcoming close approaches</h2>
<table><tr><th>Object</th><th>Date (UTC)</th><th>Miss distance</th><th>Size</th><th>Speed</th><th>Severity</th></tr>
{_cad_rows(cad)}</table>
<h2>Recent fireballs</h2>
<table><tr><th>Date (UTC)</th><th>Impact energy</th></tr>
{_fireball_rows(fireballs)}</table>
<p class="muted">Sources: CNEOS Sentry, CAD &amp; Fireball APIs · generated by <a href="https://github.com/ryroeu/nasa-defense">nasa-defense</a></p>
</body></html>
"""


def write(state_dir: Path, out_dir: Path) -> None:
    # imported here, not at module top: status uses this module's size formatter
    """Write index.html and status.json for the Pages site into `out_dir`."""
    from . import status  # pylint: disable=import-outside-toplevel,cyclic-import

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render(state_dir), encoding="utf-8")
    (out_dir / "status.json").write_text(
        json.dumps(status.build(state_dir), indent=1) + "\n", encoding="utf-8"
    )
