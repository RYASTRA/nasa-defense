"""Build the static Planetary-Defense Watch dashboard.

The watcher deliberately has no runtime backend. Python turns the committed source
snapshots into an accessible HTML overview plus small machine-readable datasets; the
browser only handles presentation, filtering, and the live Apophis countdown.
"""

from __future__ import annotations

import html
import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from . import config, state
from .models import parse_cad_datetime

_ASSET_SOURCE = Path(__file__).with_name("site_assets")
_ASSET_NAMES = ("site.css", "site.js")
_SITE_URL = "https://ryastra.github.io/nasa-defense/"
_REPOSITORY_URL = "https://github.com/RYASTRA/nasa-defense"
_SENTRY_URL = "https://cneos.jpl.nasa.gov/sentry/"
_SENTRY_DETAILS = "https://cneos.jpl.nasa.gov/sentry/details.html#?des="
_SBDB = "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr="
_FIREBALLS_URL = "https://cneos.jpl.nasa.gov/fireballs/"
_CAD_ALBEDO = 0.14
_RESULTS_PER_PAGE = 18
_SOURCE_FILES = ("sentry.json", "close_approaches.json", "fireballs.json")


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _finite_or(value: object, fallback: float) -> float:
    number = _finite_float(value)
    return fallback if number is None else number


def _format_size(diameter_km: float | None) -> str:
    value = _finite_float(diameter_km)
    if value is None or value < 0:
        return "—"
    metres = value * 1000
    return f"~{value:.1f} km" if metres >= 1000 else f"~{metres:.0f} m"


def _estimate_size_from_h(h: float | None) -> str:
    """Estimate a diameter from absolute magnitude using a conventional 0.14 albedo."""
    value = _finite_float(h)
    if value is None:
        return _format_size(None)
    diameter_km = 1329 / math.sqrt(_CAD_ALBEDO) * 10 ** (-0.2 * value)
    return _format_size(diameter_km)


def _format_ip_pct(ip: float | None) -> str:
    value = _finite_float(ip)
    if value is None or value <= 0:
        return "—"
    pct = value * 100
    if pct >= 10:
        return f"{pct:.0f}%"
    if pct >= 1:
        return f"{pct:.1f}%"
    if pct >= 0.1:
        return f"{pct:.2f}%"
    if pct >= 0.001:
        return f"{pct:.3f}%"
    return "<0.001%"


def _format_scientific(value: object) -> str:
    number = _finite_float(value)
    return "—" if number is None else f"{number:.2e}"


def _format_palermo(value: object) -> str:
    number = _finite_float(value)
    if number is None or number <= -90:
        return "—"
    return f"{number:.2f}"


def _format_run(value: object) -> str:
    if not value:
        return "not available"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return f"{parsed.day} {parsed:%B %Y · %H:%M} UTC"


def _display_cad_date(cd: str) -> str:
    when = parse_cad_datetime(cd)
    if when is None:
        return cd
    time = f" · {when:%H:%M} UTC" if ":" in cd else ""
    return f"{when.day} {when:%b %Y}{time}"


def _relative_date(when: date) -> str:
    days = (when - datetime.now(UTC).date()).days
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    return f"In {days} days"


def _format_location(lat: object, lon: object) -> str:
    latitude = _finite_float(lat)
    longitude = _finite_float(lon)
    if latitude is None or longitude is None:
        return "Location not published"
    north_south = "N" if latitude >= 0 else "S"
    east_west = "E" if longitude >= 0 else "W"
    return f"{abs(latitude):.1f}°{north_south}, {abs(longitude):.1f}°{east_west}"


def _sentry_items(sentry: dict) -> list[tuple[str, dict]]:
    objects = [(des, fields) for des, fields in sentry.items() if _state_noteworthy(fields)]
    objects.sort(
        key=lambda item: (
            _finite_or(item[1].get("ts_max"), 0),
            _finite_or(item[1].get("ps_cum"), -99),
            _finite_or(item[1].get("ip"), 0),
        ),
        reverse=True,
    )
    return objects


def _cad_items(cad: dict) -> list[tuple[date, str, str, dict]]:
    now = datetime.now(UTC)
    cutoff = now + timedelta(days=config.CAD_LOOKAHEAD_DAYS)
    upcoming = []
    for key, fields in cad.items():
        des, separator, cd = key.partition(":")
        if not separator:
            continue
        timestamp = parse_cad_datetime(cd)
        if timestamp is None:
            continue
        has_time = ":" in cd
        if has_time and (timestamp < now or timestamp.date() > cutoff.date()):
            continue
        if not has_time and not now.date() <= timestamp.date() <= cutoff.date():
            continue
        upcoming.append((timestamp.date(), des, cd, fields))
    upcoming.sort(
        key=lambda row: (
            parse_cad_datetime(row[2]) or datetime.max.replace(tzinfo=UTC),
            _finite_or(row[3].get("dist_ld"), math.inf),
        )
    )
    return upcoming


def _fireball_items(fireballs: dict) -> list[tuple[str, dict]]:
    return sorted(fireballs.items(), key=lambda item: item[0], reverse=True)


def _state_noteworthy(fields: dict) -> bool:
    """Trust the saved decision only while its numeric inputs are structurally valid."""
    values = (fields.get(key) for key in ("ts_max", "ps_cum", "ip", "diameter_km"))
    valid = all(value is None or _finite_float(value) is not None for value in values)
    return valid and fields.get("noteworthy") is True


def _sentry_rows(sentry: dict) -> str:
    rows = []
    for des, fields in _sentry_items(sentry)[:15]:
        rows.append(
            f"<tr><td>{_esc(des)}</td>"
            f"<td>{_esc(_format_size(fields.get('diameter_km')))}</td>"
            f"<td>{_esc(fields.get('ts_max', 0))}</td>"
            f"<td>{_esc(_format_palermo(fields.get('ps_cum')))}</td>"
            f"<td>{_esc(_format_scientific(fields.get('ip')))}</td>"
            f"<td>{_esc(_format_ip_pct(fields.get('ip')))}</td></tr>"
        )
    return "".join(rows) or "<tr><td colspan='6' class='muted'>No watch signals.</td></tr>"


def _risk_signals(fields: dict) -> list[str]:
    signals = []
    torino = _finite_float(fields.get("ts_max")) or 0
    palermo = _finite_float(fields.get("ps_cum"))
    probability = _finite_float(fields.get("ip")) or 0
    diameter = _finite_float(fields.get("diameter_km"))
    if torino >= 1:
        signals.append("torino")
    if palermo is not None and palermo >= config.PALERMO_FLOOR:
        signals.append("palermo")
    if probability >= config.IP_FLOOR:
        signals.append("probability")
    if diameter is not None and diameter * 1000 >= config.NOTEWORTHY_DIAMETER_M:
        signals.append("size")
    return signals


def _risk_records(sentry: dict) -> list[dict]:
    records = []
    for des, fields in sorted(sentry.items(), key=lambda item: item[0].casefold()):
        diameter = _finite_float(fields.get("diameter_km"))
        signals = _risk_signals(fields)
        records.append(
            {
                "des": des,
                "diameter_km": diameter,
                "ts_max": int(_finite_float(fields.get("ts_max")) or 0),
                "ps_cum": _finite_float(fields.get("ps_cum")),
                "ip": _finite_float(fields.get("ip")) or 0,
                "last_obs": str(fields.get("last_obs") or ""),
                "noteworthy": _state_noteworthy(fields),
                "signals": signals,
                "sentry_url": _SENTRY_DETAILS + quote(des, safe=""),
            }
        )
    return records


def _approach_records(cad: dict) -> list[dict]:
    records = []
    for when, des, cd, fields in _cad_items(cad):
        records.append(
            {
                "des": des,
                "date": when.isoformat(),
                "cd": cd,
                "dist_au": _finite_float(fields.get("dist_au")),
                "dist_ld": _finite_float(fields.get("dist_ld")),
                "v_rel_kms": _finite_float(fields.get("v_rel_kms")),
                "h": _finite_float(fields.get("h")),
                "severity": str(fields.get("severity", "info")),
                "sbdb_url": _SBDB + quote(des, safe=""),
            }
        )
    return records


def _fireball_records(fireballs: dict) -> list[dict]:
    records = []
    for when, fields in _fireball_items(fireballs):
        records.append(
            {
                "date": when,
                "impact_e_kt": _finite_float(fields.get("impact_e_kt")),
                "energy": _finite_float(fields.get("energy")),
                "lat": _finite_float(fields.get("lat")),
                "lon": _finite_float(fields.get("lon")),
            }
        )
    return records


def _header() -> str:
    return """
<header class="site-header">
  <div class="site-header__inner">
    <a class="brand" href="./" aria-label="Planetary-Defense Watch home">
      <span>Planetary-Defense <strong>Watch</strong></span>
    </a>
    <nav class="site-nav" aria-label="Primary navigation">
      <a href="#overview">Overview</a>
      <a href="#approaches">Approaches</a>
      <a href="#sentry">Sentry</a>
      <a href="#signals">Signals</a>
      <a href="#methodology">Method</a>
    </nav>
  </div>
</header>"""


def _source_streak(meta: dict, filename: str, available: dict[str, bool]) -> int | None:
    if not available.get(filename) or not meta.get("last_run_utc"):
        return None
    failures = meta.get("consecutive_failures")
    if not isinstance(failures, dict) or filename not in failures:
        return None
    value = _finite_float(failures[filename])
    if value is None or value < 0 or not value.is_integer():
        return None
    return int(value)


def _hero(sentry: dict, cad: dict, meta: dict, available: dict[str, bool]) -> str:
    noteworthy = _sentry_items(sentry)
    upcoming = _cad_items(cad)
    elevated = sum(1 for fields in sentry.values() if _finite_or(fields.get("ts_max"), 0) >= 1)
    streaks = [_source_streak(meta, filename, available) for filename in _SOURCE_FILES]
    healthy = all(value == 0 for value in streaks)
    health_class = "healthy" if healthy else "degraded"
    if healthy:
        health_text = "All sources reporting"
    elif any(value is None for value in streaks):
        health_text = "Source health incomplete"
    else:
        health_text = "One or more sources recovering"
    next_name = upcoming[0][1] if upcoming else "No pass queued"
    next_distance = (
        f"{(_finite_float(upcoming[0][3].get('dist_ld')) or 0):.2f} LD" if upcoming else "—"
    )
    return f"""
<section class="hero" id="overview">
  <div class="hero__content">
    <p class="eyebrow">NASA/JPL planetary defense · checked daily</p>
    <h1>Near-Earth space,<br><em>made legible.</em></h1>
    <p class="hero__lede">A calm, evidence-first view of close approaches, impact-risk
       changes, and atmospheric fireballs—without turning every asteroid into an alarm.</p>
    <div class="hero-actions">
      <a class="button button--primary" href="#approaches">See upcoming passes</a>
      <a class="button" href="#methodology">How risk is read</a>
    </div>
    <div class="hero__meta">
      <span class="health-label health-label--{health_class}">{_esc(health_text)}</span>
      <span>Last watch run: {_esc(_format_run(meta.get("last_run_utc")))}</span>
    </div>
  </div>

  <div class="hero-radar" aria-hidden="true">
    <span class="radar-orbit radar-orbit--one"></span>
    <span class="radar-orbit radar-orbit--two"></span>
    <span class="radar-orbit radar-orbit--three"></span>
    <span class="radar-earth"></span>
    <span class="radar-moon"></span>
    <span class="radar-object"></span>
    <span class="radar-sweep"></span>
    <span class="radar-readout"><small>Next tracked pass</small>
      <strong>{_esc(next_name)}</strong><b>{_esc(next_distance)}</b></span>
  </div>

  <dl class="metrics-grid">
    <div class="metric"><dt>Sentry catalog</dt><dd>{len(sentry):,}</dd>
      <span>Current risk-table objects</span></div>
    <div class="metric"><dt>Watch signals</dt><dd>{len(noteworthy):,}</dd>
      <span>Crossing an attention floor</span></div>
    <div class="metric"><dt>Upcoming passes</dt><dd>{len(upcoming):,}</dd>
      <span>Within {_esc(config.CAD_MAX_LUNAR_DISTANCES)} lunar distances</span></div>
    <div class="metric"><dt>Torino above zero</dt><dd>{elevated:,}</dd>
      <span>Public-concern rating</span></div>
  </dl>
</section>"""


def _posture_section(sentry: dict, cad: dict) -> str:
    elevated = [
        (des, fields)
        for des, fields in sentry.items()
        if (_finite_float(fields.get("ts_max")) or 0) >= 1
    ]
    if elevated:
        max_torino = max(int(_finite_or(fields.get("ts_max"), 0)) for _des, fields in elevated)
        posture_class = "attention"
        posture_label = "Attention"
        posture_title = f"Torino {max_torino} is the current high"
        posture_copy = (
            "An object has moved above Torino 0. That merits attention, not a conclusion; "
            "follow-up observations usually refine the estimate."
        )
    else:
        posture_class = "calm"
        posture_label = "Current posture"
        posture_title = "No elevated Torino ratings"
        posture_copy = (
            "Every object currently in the Sentry table is Torino 0: no unusual level of "
            "public concern. Tiny modeled probabilities can still appear in the catalog."
        )

    sentry_signals = _sentry_items(sentry)
    highest = (
        max(sentry_signals, key=lambda item: _finite_or(item[1].get("ps_cum"), -99))
        if sentry_signals
        else None
    )
    high_copy = "No watch signal is currently available."
    if highest:
        high_copy = (
            f"{highest[0]} has the highest displayed cumulative Palermo value "
            f"({_format_palermo(highest[1].get('ps_cum'))}). Negative values remain below "
            "the background hazard."
        )

    days = (date.fromisoformat(config.APOPHIS_DATE) - datetime.now(UTC).date()).days
    countdown_label = "days since closest approach" if days < 0 else "days to closest approach"
    next_pass = _cad_items(cad)
    next_copy = (
        f"{next_pass[0][1]} is next, at "
        f"{(_finite_float(next_pass[0][3].get('dist_ld')) or 0):.2f} lunar distances."
        if next_pass
        else "No future close approach is present in the current window."
    )
    return f"""
<section class="posture-section" aria-labelledby="posture-title">
  <div class="section-heading">
    <div><p class="eyebrow">Right now</p><h2 id="posture-title">The signal before the noise</h2></div>
    <p>Risk is more than a probability. These summaries keep distance, size, and the
       public communication scales in view together.</p>
  </div>
  <div class="posture-grid">
    <article class="posture-card posture-card--{posture_class}">
      <p class="card-kicker">{_esc(posture_label)}</p>
      <h3>{_esc(posture_title)}</h3>
      <p>{_esc(posture_copy)}</p>
      <div class="posture-detail">
        <span>Highest watch signal</span><strong>{_esc(high_copy)}</strong>
      </div>
      <div class="posture-detail">
        <span>Next close pass</span><strong>{_esc(next_copy)}</strong>
      </div>
    </article>

    <article class="apophis-card" data-apophis-date="{_esc(config.APOPHIS_DATE)}">
      <div>
        <p class="card-kicker">The 2029 anchor</p>
        <h3>99942 Apophis</h3>
        <p>A roughly 340 m asteroid will pass inside geostationary orbit on
           13 April 2029. NASA has ruled out an impact during this encounter.</p>
      </div>
      <div class="apophis-countdown">
        <strong id="apophis-days">{abs(days):,}</strong><span>{countdown_label}</span>
      </div>
      <div class="apophis-facts">
        <span><b>~32,000 km</b> above Earth</span>
        <span><b>~340 m</b> across</span>
        <span><b>Safe pass</b> impact ruled out</span>
      </div>
      <a href="{_SBDB}{config.APOPHIS_DESIGNATION}">Open the JPL record <span>→</span></a>
    </article>
  </div>
</section>"""


def _approach_card(row: tuple[date, str, str, dict]) -> str:
    when, des, cd, fields = row
    distance = _finite_float(fields.get("dist_ld")) or 0
    speed = _finite_float(fields.get("v_rel_kms")) or 0
    severity = str(fields.get("severity", "info"))
    if severity == "critical":
        badge = "Inside lunar distance"
    elif severity == "high":
        badge = "Closer watch"
    else:
        badge = "Tracked pass"
    width = min(100, max(1, distance / config.CAD_MAX_LUNAR_DISTANCES * 100))
    datetime_value = parse_cad_datetime(cd)
    datetime_attr = datetime_value.isoformat().replace("+00:00", "Z") if datetime_value else ""
    return f"""
<article class="approach-card approach-card--{_esc(severity)}">
  <div class="approach-card__header">
    <div><p class="card-kicker">{_esc(_relative_date(when))}</p>
      <h3><a href="{_SBDB}{quote(des, safe="")}">{_esc(des)}</a></h3></div>
    <span class="severity-badge severity-badge--{_esc(severity)}">{_esc(badge)}</span>
  </div>
  <time datetime="{_esc(datetime_attr)}">{_esc(_display_cad_date(cd))}</time>
  <div class="distance-readout">
    <div><span>Miss distance</span><strong>{distance:.2f} LD</strong></div>
    <div class="distance-track" aria-hidden="true">
      <i style="--distance-position:{width:.2f}%"></i><b></b>
    </div>
    <small>Earth <span>Moon’s average orbit = 1 LD</span></small>
  </div>
  <dl class="approach-facts">
    <div><dt>Estimated size</dt><dd>{_esc(_estimate_size_from_h(fields.get("h")))}</dd></div>
    <div><dt>Relative speed</dt><dd>{speed:.1f} km/s</dd></div>
  </dl>
  <p class="context-note">A close approach is a measured miss distance, not an impact
     prediction. Size is estimated from brightness and assumed reflectivity.</p>
</article>"""


def _approaches_section(cad: dict) -> str:
    upcoming = _cad_items(cad)
    cards = "".join(_approach_card(row) for row in upcoming[:12])
    if not cards:
        cards = """
<div class="empty-state">
  <strong>No upcoming close passes in the current window.</strong>
  <p>The watcher will populate this section when CNEOS lists one within the configured range.</p>
</div>"""
    return f"""
<section class="approaches-section" id="approaches" aria-labelledby="approaches-title">
  <div class="section-heading">
    <div><p class="eyebrow">The next {config.CAD_LOOKAHEAD_DAYS:g} days</p>
      <h2 id="approaches-title">Upcoming close approaches</h2></div>
    <p>CNEOS passes within {config.CAD_MAX_LUNAR_DISTANCES:g} lunar distances, ordered
       soonest first. “Closer watch” describes the pass—not a hazard forecast.</p>
  </div>
  <div class="approaches-grid">{cards}</div>
  <p class="section-footnote">LD means one average Earth–Moon distance, about 384,400 km.
     <a href="data/close-approaches.json">Download this approach window as JSON</a>.</p>
</section>"""


def _sentry_section(sentry: dict) -> str:
    noteworthy = len(_sentry_items(sentry))
    return f"""
<section class="sentry-section" id="sentry" aria-labelledby="sentry-title">
  <div class="section-heading">
    <div><p class="eyebrow">CNEOS Sentry</p><h2 id="sentry-title">Explore the risk table</h2></div>
    <p>Start with {noteworthy:,} objects crossing at least one watch rule, or inspect all
       {len(sentry):,}. A place in Sentry is not a prediction of impact.</p>
  </div>
  <div class="explorer-shell">
    <form id="risk-controls" class="risk-controls" role="search">
      <label class="search-field" for="risk-search"><span>Object designation</span>
        <input id="risk-search" name="q" type="search" placeholder="Try 99942 or 2010 RF12"
               autocomplete="off"></label>
      <label for="risk-scope"><span>Show</span>
        <select id="risk-scope" name="scope">
          <option value="watch">Watch signals</option>
          <option value="all">Complete Sentry catalog</option>
          <option value="torino">Torino 1 or higher</option>
          <option value="palermo">Above Palermo floor</option>
          <option value="probability">Above probability floor</option>
          <option value="size">At least {config.NOTEWORTHY_DIAMETER_M:g} m</option>
        </select></label>
      <label for="risk-sort"><span>Sort</span>
        <select id="risk-sort" name="sort">
          <option value="attention">Attention order</option>
          <option value="probability">Impact probability</option>
          <option value="size">Estimated size</option>
          <option value="observed">Latest observation</option>
          <option value="name">Designation</option>
        </select></label>
      <button id="risk-clear" class="button" type="button">Reset</button>
    </form>
    <div id="risk-loading" class="catalog-message" role="status">Loading the Sentry catalog…</div>
    <div id="risk-error" class="catalog-message catalog-error" role="alert" hidden></div>
    <div class="catalog-meta">
      <div id="risk-status" aria-live="polite" tabindex="-1"></div>
      <a href="data/sentry.json">Machine-readable catalog</a>
    </div>
    <div id="risk-results" class="risk-grid"></div>
    <nav id="risk-pagination" class="pagination" aria-label="Sentry result pages"></nav>
    <noscript>
      <p class="catalog-message">The interactive catalog needs JavaScript. The leading watch
         signals are available below, and the
         <a href="data/sentry.json">complete JSON remains downloadable</a>.</p>
      <div class="table-wrap"><table>
        <caption>Leading watch signals</caption>
        <thead><tr><th scope="col">Object</th><th scope="col">Size</th>
          <th scope="col">Torino</th><th scope="col">Palermo</th>
          <th scope="col">Impact probability</th><th scope="col">Probability (%)</th></tr></thead>
        <tbody>{_sentry_rows(sentry)}</tbody>
      </table></div>
    </noscript>
  </div>
</section>

<dialog id="risk-dialog" class="risk-dialog" aria-labelledby="risk-dialog-title">
  <div class="dialog-bar"><button id="risk-dialog-close" type="button"
    aria-label="Close object details">×</button></div>
  <div id="risk-dialog-content"></div>
</dialog>"""


def _fireball_card(when: str, fields: dict) -> str:
    energy = _finite_float(fields.get("impact_e_kt")) or 0
    severity = "high" if energy >= config.FIREBALL_HIGH_KT else "info"
    return f"""
<article class="fireball-card">
  <div class="fireball-icon fireball-icon--{severity}" aria-hidden="true"></div>
  <div><time>{_esc(when)} UTC</time><h3>{energy:.2g} kilotons</h3>
    <p>{_esc(_format_location(fields.get("lat"), fields.get("lon")))}</p></div>
</article>"""


def _source_health(meta: dict, available: dict[str, bool]) -> str:
    sources = (
        ("Sentry", "Impact-risk table", "sentry.json"),
        ("Close Approach", "Near-Earth passes", "close_approaches.json"),
        ("Fireball", "Atmospheric bolides", "fireballs.json"),
    )
    rows = []
    for name, purpose, filename in sources:
        streak = _source_streak(meta, filename, available)
        if streak is None:
            state_class = "unknown"
            status_text = "Health not recorded"
        elif streak == 0:
            state_class = "healthy"
            status_text = "Reporting"
        else:
            state_class = "recovering"
            status_text = f"Unavailable for {streak} run(s)"
        rows.append(
            f'<li><span class="source-dot source-dot--{state_class}"></span>'
            f"<div><strong>{_esc(name)}</strong><small>{_esc(purpose)}</small></div>"
            f"<b>{_esc(status_text)}</b></li>"
        )
    return "".join(rows)


def _signals_section(fireballs: dict, meta: dict, available: dict[str, bool]) -> str:
    cards = "".join(_fireball_card(*row) for row in _fireball_items(fireballs)[:6])
    if not cards:
        cards = (
            '<p class="empty-compact">No fireball above the reporting floor in this snapshot.</p>'
        )
    return f"""
<section class="signals-section" id="signals" aria-labelledby="signals-title">
  <div class="section-heading">
    <div><p class="eyebrow">Other signals</p><h2 id="signals-title">Atmosphere and source health</h2></div>
    <p>Bright fireballs are normal evidence of small space rocks meeting the atmosphere.
       Source health shows whether the daily view is complete.</p>
  </div>
  <div class="signals-grid">
    <article class="signal-panel">
      <div class="panel-heading"><div><p class="card-kicker">Last
        {config.FIREBALL_LOOKBACK_DAYS:g} days</p>
        <h3>Reported fireballs</h3></div>
        <a href="{_FIREBALLS_URL}">CNEOS source ↗</a></div>
      <div class="fireball-list">{cards}</div>
      <p class="panel-note">Energy is estimated total impact energy in kilotons of TNT.
         CNEOS reporting can arrive days or weeks after an event.</p>
    </article>
    <article class="signal-panel">
      <div class="panel-heading"><div><p class="card-kicker">Daily ingest</p>
        <h3>Source health</h3></div><span class="last-run">Updated
        {_esc(_format_run(meta.get("last_run_utc")))}</span></div>
      <ul class="source-list">{_source_health(meta, available)}</ul>
      <p class="panel-note">A transient source failure keeps its previous snapshot and is
         retried next run, so missed changes are not silently discarded.</p>
    </article>
  </div>
</section>"""


def _methodology_section() -> str:
    return f"""
<section class="methodology-section" id="methodology" aria-labelledby="methodology-title">
  <div class="section-heading">
    <div><p class="eyebrow">The honesty layer</p>
      <h2 id="methodology-title">How this watch decides what matters</h2></div>
    <p>The source data is authoritative; the attention rules are deliberately plain,
       version-controlled, and visible here.</p>
  </div>
  <div class="scale-grid">
    <article><span class="scale-number scale-number--green">0–10</span>
      <h3>Torino scale</h3>
      <p>The public communication scale combines likelihood and consequence. Zero means no
         unusual public concern; a move above zero is always surfaced.</p>
      <a href="https://cneos.jpl.nasa.gov/sentry/torino_scale.html">Read the CNEOS guide ↗</a>
    </article>
    <article><span class="scale-number scale-number--violet">−∞ → +</span>
      <h3>Palermo scale</h3>
      <p>Compares a modeled impact risk with the ordinary background hazard. Negative values
         are below background; the watch floor is {_esc(config.PALERMO_FLOOR)}.</p>
      <a href="https://cneos.jpl.nasa.gov/sentry/palermo_scale.html">Read the CNEOS guide ↗</a>
    </article>
    <article><span class="scale-number scale-number--amber">P × size</span>
      <h3>Probability needs context</h3>
      <p>A small object can carry a larger probability and still pose little consequence.
         The watcher also considers diameter, scale ratings, and material change.</p>
      <a href="{_SENTRY_URL}">Open CNEOS Sentry ↗</a>
    </article>
  </div>
  <div class="pipeline" aria-label="Daily watcher pipeline">
    <div><span>01</span><strong>Fetch</strong><small>Three CNEOS feeds + NeoWs context</small></div>
    <i aria-hidden="true">→</i>
    <div><span>02</span><strong>Compare</strong><small>Diff against the committed snapshot</small></div>
    <i aria-hidden="true">→</i>
    <div><span>03</span><strong>Explain</strong><small>Deterministic, plain-language alerts</small></div>
    <i aria-hidden="true">→</i>
    <div><span>04</span><strong>Record</strong><small>Issues, Pages, and a git ledger</small></div>
  </div>
  <div class="threshold-note">
    <strong>Current attention floors</strong>
    <span>Palermo ≥ {config.PALERMO_FLOOR:g}</span>
    <span>Impact probability ≥ {config.IP_FLOOR:g}</span>
    <span>Estimated diameter ≥ {config.NOTEWORTHY_DIAMETER_M:g} m</span>
    <span>Close pass ≤ {config.CAD_MAX_LUNAR_DISTANCES:g} LD</span>
  </div>
</section>"""


def _footer() -> str:
    return f"""
<footer class="site-footer">
  <div class="site-footer__inner">
    <div><strong>Planetary-Defense Watch</strong>
      <p>Independent, deterministic, and intentionally calm. Not affiliated with or
         endorsed by NASA or JPL.</p></div>
    <nav aria-label="Footer navigation">
      <a href="{_SENTRY_URL}">CNEOS Sentry</a>
      <a href="https://ssd.jpl.nasa.gov/tools/cad_search.html">Close Approach Data</a>
      <a href="status.json">Status JSON</a>
      <a href="{_REPOSITORY_URL}">Source on GitHub</a>
    </nav>
  </div>
</footer>"""


def _page_document(body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="A daily, evidence-first watch over NASA/JPL planetary-defense data.">
<meta name="theme-color" content="#050812">
<meta property="og:title" content="Planetary-Defense Watch">
<meta property="og:description" content="Near-Earth space, made legible.">
<meta property="og:type" content="website">
<meta property="og:url" content="{_SITE_URL}">
<title>Planetary-Defense Watch</title>
<link rel="canonical" href="{_SITE_URL}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'
 viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='10' fill='%2366e3ff'/%3E
%3Cellipse cx='32' cy='32' rx='27' ry='13' fill='none' stroke='%23a995ff'
 stroke-width='4' transform='rotate(-22 32 32)'/%3E%3C/svg%3E">
<link rel="stylesheet" href="assets/site.css">
<script src="assets/site.js" defer></script>
<noscript><style>
  .risk-controls, .catalog-meta, #risk-loading, #risk-results, #risk-pagination {{
    display: none !important;
  }}
</style></noscript>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<div class="site-shell">
{body}
</div>
</body>
</html>
"""


def render(state_dir: Path) -> str:
    """Build the complete dashboard HTML from snapshots in ``state_dir``."""
    sentry = state.load(state_dir / "sentry.json")
    cad = state.load(state_dir / "close_approaches.json")
    fireballs = state.load(state_dir / "fireballs.json")
    meta = state.load(state_dir / "meta.json")
    available = {filename: (state_dir / filename).is_file() for filename in _SOURCE_FILES}
    body = f"""
{_header()}
<main id="main">
  {_hero(sentry, cad, meta, available)}
  {_posture_section(sentry, cad)}
  {_approaches_section(cad)}
  {_sentry_section(sentry)}
  {_signals_section(fireballs, meta, available)}
  {_methodology_section()}
</main>
{_footer()}"""
    return _page_document(body)


def _write_assets(out_dir: Path, assets: dict[str, bytes]) -> None:
    target = out_dir / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for name, content in assets.items():
        (target / name).write_bytes(content)


def _write_json(path: Path, value: object, *, compact: bool = False) -> None:
    if compact:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def write(state_dir: Path, out_dir: Path) -> None:
    """Write the static site, frontend assets, and public datasets into ``out_dir``."""
    from . import status  # pylint: disable=import-outside-toplevel,cyclic-import

    sentry = state.load(state_dir / "sentry.json")
    cad = state.load(state_dir / "close_approaches.json")
    fireballs = state.load(state_dir / "fireballs.json")
    sentry_document = {
        "schema": 1,
        "scope": "Current CNEOS Sentry catalog",
        "results_per_page": _RESULTS_PER_PAGE,
        "thresholds": {
            "palermo_floor": config.PALERMO_FLOOR,
            "impact_probability_floor": config.IP_FLOOR,
            "diameter_floor_m": config.NOTEWORTHY_DIAMETER_M,
        },
        "objects": _risk_records(sentry),
    }
    approach_document = _approach_records(cad)
    fireball_document = _fireball_records(fireballs)
    status_document = status.build(state_dir)
    index_document = render(state_dir)
    assets = {name: (_ASSET_SOURCE / name).read_bytes() for name in _ASSET_NAMES}

    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)
    _write_assets(out_dir, assets)
    _write_json(data_dir / "sentry.json", sentry_document, compact=True)
    _write_json(data_dir / "close-approaches.json", approach_document, compact=True)
    _write_json(data_dir / "fireballs.json", fireball_document, compact=True)
    _write_json(out_dir / "status.json", status_document)
    (out_dir / "index.html").write_text(index_document, encoding="utf-8")
