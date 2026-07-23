"""Issue title and body templates for each detected event type."""
from __future__ import annotations

from urllib.parse import quote

from .models import Event


def _sentry_url(des: str) -> str:
    return f"https://cneos.jpl.nasa.gov/sentry/details.html#?des={quote(des)}"


def _footer(des: str) -> str:
    return f"[JPL Sentry — {des}]({_sentry_url(des)}) · source: `sentry.api`"


def _cad_url(des: str) -> str:
    return f"https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr={quote(des)}"


def _cad_footer(des: str) -> str:
    return f"[JPL small-body lookup — {des}]({_cad_url(des)}) · source: `cad.api`"


def _enrichment_line(p: dict) -> str:
    parts = []
    if p.get("pha"):
        parts.append("⚠️ NeoWs flags this a **potentially hazardous asteroid**")
    diameter = p.get("neows_diameter_m")
    if diameter:
        parts.append(f"estimated diameter ~{diameter:.0f} m")
    return ("\n\n" + " · ".join(parts)) if parts else ""


def _new(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[☄️ Sentry] {des} entered the impact-risk table"
    body = (
        f"**{des}** is now tracked on the CNEOS Sentry impact-risk table.\n\n"
        f"| Field | Value |\n|---|---|\n"
        f"| Torino (max) | {p['ts_max']} |\n"
        f"| Palermo (cum.) | {p['ps_cum']} |\n"
        f"| Impact probability | {p['ip']:.2e} |\n\n"
        f"**What it means:** A newly catalogued object cleared the noteworthy "
        f"floor (size, probability, or risk rating). Most such objects are later "
        f"ruled out as the orbit is refined.\n\n{_footer(des)}"
    )
    return title, body


def _removed(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[✅ Sentry] {des} removed from the impact-risk table"
    body = (
        f"**{des}** is no longer on the Sentry impact-risk table.\n\n"
        f"**What it means:** A removal almost always means the impact was ruled "
        f"out by new observations — good news.\n\n{_footer(des)}"
    )
    return title, body


def _torino_up(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[☄️ Sentry] {des} — Torino risk rose to {p['ts_now']}"
    body = (
        f"The impact-risk rating for **{des}** increased from Torino "
        f"**{p['ts_prev']} → {p['ts_now']}**.\n\n"
        f"| Field | Previous | Now |\n|---|---|---|\n"
        f"| Torino (max) | {p['ts_prev']} | **{p['ts_now']}** |\n"
        f"| Palermo (cum.) | {p['ps_prev']} | {p['ps_now']} |\n"
        f"| Impact probability | {p['ip_prev']:.2e} | {p['ip_now']:.2e} |\n\n"
        f"**What it means:** A jump off Torino 0 is rare — every other tracked "
        f"object sits at 0 — so it is worth a look. Further observations usually "
        f"refine the orbit and the rating falls back.\n\n{_footer(des)}"
    )
    return title, body


def _torino_down(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[☄️ Sentry] {des} — Torino risk fell to {p['ts_now']}"
    body = (
        f"The impact-risk rating for **{des}** decreased from Torino "
        f"**{p['ts_prev']} → {p['ts_now']}**.\n\n"
        f"**What it means:** De-escalation — the hazard estimate dropped, "
        f"typically as the orbit was refined.\n\n{_footer(des)}"
    )
    return title, body


def _palermo_up(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[☄️ Sentry] {des} — Palermo scale rose to {p['ps_now']}"
    body = (
        f"The cumulative Palermo rating for **{des}** rose from "
        f"**{p['ps_prev']} → {p['ps_now']}**.\n\n"
        f"**What it means:** The Palermo scale compares this object's risk to the "
        f"random background hazard; a rise means it now stands further above "
        f"background.\n\n{_footer(des)}"
    )
    return title, body


def _ip_jump(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[☄️ Sentry] {des} — impact probability jumped"
    body = (
        f"The impact probability for **{des}** rose from "
        f"**{p['ip_prev']:.2e} → {p['ip_now']:.2e}**.\n\n"
        f"**What it means:** An order-of-magnitude rise in the computed impact "
        f"probability — worth tracking, though refinements often reverse it."
        f"\n\n{_footer(des)}"
    )
    return title, body


def _cad_new_close(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[🛰️ Close approach] {des} — {p['dist_ld']:.2f} lunar distances on {p['cd']}"
    body = (
        f"**{des}** has a newly-listed close approach: it passes "
        f"**{p['dist_ld']:.2f} lunar distances** ({p['dist_au']:.4f} au) from Earth on "
        f"**{p['cd']} UTC** at {p['v_rel_kms']:.1f} km/s.\n\n"
        f"**What it means:** A catalogued near-Earth object on a safe but notable "
        f"pass — the closer and larger it is, the more it is worth watching.\n\n"
        f"{_cad_footer(des)}{_enrichment_line(p)}"
    )
    return title, body


def _cad_sublunar(p: dict) -> tuple[str, str]:
    des = p["des"]
    title = f"[🌙 Close approach] {des} passes inside the Moon's orbit ({p['dist_ld']:.2f} LD)"
    body = (
        f"**{des}** passes **{p['dist_ld']:.2f} lunar distances** "
        f"({p['dist_au']:.4f} au) from Earth on **{p['cd']} UTC**, relative speed "
        f"{p['v_rel_kms']:.1f} km/s — closer than the Moon.\n\n"
        f"**What it means:** A sub-lunar pass is uncommon enough to flag every time. "
        f"For an object this size it is a harmless miss, not a threat.\n\n"
        f"{_cad_footer(des)}{_enrichment_line(p)}"
    )
    return title, body


def _format_location(lat: float | None, lon: float | None) -> str:
    if lat is None or lon is None:
        return ""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f" over {abs(lat):.1f}°{ns}, {abs(lon):.1f}°{ew}"


def _fireball_new(p: dict) -> tuple[str, str]:
    energy = p["impact_e_kt"]
    location = _format_location(p["lat"], p["lon"])
    title = f"[💥 Fireball] {energy:.2g} kt bolide on {p['date']}"
    body = (
        f"A bolide (bright fireball) with an estimated impact energy of "
        f"**{energy:.2g} kt** was recorded on **{p['date']} UTC**{location}.\n\n"
        f"**What it means:** Almost all fireballs are small meteoroids burning up "
        f"harmlessly high in the atmosphere; the energy is the number to watch.\n\n"
        f"[CNEOS Fireballs](https://cneos.jpl.nasa.gov/fireballs/) · source: `fireball.api`"
    )
    return title, body


def _apophis(p: dict) -> tuple[str, str]:
    days = p["days_until"]
    title = f"[🛰️ Apophis 2029] {days} days until the 2029-04-13 flyby"
    rows = ""
    if "cd" in p:
        rows = (
            "| Field | Value |\n|---|---|\n"
            f"| Closest approach | {p['cd']} UTC |\n"
            f"| Miss distance | {p['dist_ld']:.2f} lunar distances ({p['dist_au']:.5f} au) |\n"
            f"| Relative speed | {p['v_rel_kms']:.1f} km/s |\n\n"
        )
    body = (
        f"**99942 Apophis** makes its historic close approach on **2029-04-13** — "
        f"**{days} days** from now.\n\n"
        f"{rows}"
        f"**Why it matters:** An object this size (~340 m) passing this close — about "
        f"32,000 km above the surface, inside geostationary orbit — happens only about "
        f"once in 800 years (NASA), and this is the closest such approach ever known in "
        f"advance. Apophis will be naked-eye visible (~mag 3) across Europe, Africa, and "
        f"Asia. It is **not** a threat in 2029; impact has been ruled out.\n\n"
        f"[JPL CAD — 99942](https://ssd-api.jpl.nasa.gov/cad.api?des=99942) · source: `cad.api`"
    )
    return title, body


_RENDERERS = {
    "SENTRY_NEW": _new,
    "SENTRY_REMOVED": _removed,
    "SENTRY_TORINO_UP": _torino_up,
    "SENTRY_TORINO_DOWN": _torino_down,
    "SENTRY_PALERMO_UP": _palermo_up,
    "SENTRY_IP_JUMP": _ip_jump,
    "CAD_NEW_CLOSE": _cad_new_close,
    "CAD_SUBLUNAR": _cad_sublunar,
    "FIREBALL_NEW": _fireball_new,
    "APOPHIS_ANCHOR": _apophis,
}


def render(event: Event) -> tuple[str, str]:
    """Render an event into an issue title and body, with its key marker appended.

    Raises:
        ValueError: when the event type has no registered renderer.
    """
    fn = _RENDERERS.get(event.type)
    if fn is None:
        raise ValueError(f"no renderer for event type {event.type!r}")
    title, body = fn(event.payload)
    body = f"{body}\n\n<!-- nasa-defense-key: {event.key} -->\n"
    return title, body
