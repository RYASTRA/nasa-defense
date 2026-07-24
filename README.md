# 🛰️ nasa-defense — Planetary-Defense Watch

A **repo-native, zero-infrastructure** watcher that turns NASA/JPL's authoritative
near-Earth-object data into plain-language **GitHub Issues** — plus a live status
page and a perpetual *Apophis 2029* countdown — on a daily schedule.

The unmet need it fills: CNEOS publishes the authoritative impact-risk data as raw
JSON, but nobody turns its *deltas* into human-legible alerts. This project is the
friendly "watch it, tell me when it **materially** changes, and explain why in plain
English" layer on top — with no servers, no database, and no Docker. The GitHub repo
*is* the deployment.

Quick Look: https://ryastra.github.io/nasa-defense/

---

## What it does

Once a day, a GitHub Actions job:

1. **Fetches** the latest data from four NASA/JPL sources (below).
2. **Detects material changes** against the last committed snapshot — orbit-refinement
   jitter and the long low-risk tail are filtered out, so alerts stay actionable and rare.
3. **Raises GitHub Issues** with deterministic, plain-language briefings (no LLM, no
   hallucination risk). Issues are idempotent: the same object updates in place rather
   than spamming duplicates.
4. **Optionally fans out** high-signal alerts to Slack / Discord / a webhook / email.
5. **Publishes an interactive static observatory** to GitHub Pages — live posture,
   upcoming-pass cards, a searchable Sentry catalog, fireball context, and source health.
6. **Commits the new snapshot** so git history becomes a tamper-evident "what changed when" ledger.

```
cron ─▶ fetch sources ─▶ detect deltas ─▶ render ─▶ GitHub Issues (+ fan-out)
                                              └────▶ static Pages site
                                              └────▶ commit state snapshot
```

## Data sources

| Source | What it provides | Auth |
|---|---|---|
| **CNEOS Sentry** | Impact-risk table (Torino / Palermo / impact probability) | none |
| **CNEOS Close-Approach (CAD)** | Upcoming & recent close approaches | none |
| **CNEOS Fireball** | Observed atmospheric bolide events | none |
| **NeoWs** | *Enrichment* — "potentially hazardous" flag + diameter | **`NASA_API_KEY` (required)** |

The three CNEOS feeds are keyless. NeoWs uses your key — and the watcher **requires a
real `NASA_API_KEY`** (it hard-fails at startup without one; there is no demo fallback).
Grab a free key in seconds at **<https://api.nasa.gov/>**.

## The Apophis 2029 anchor

A single, perpetually-updated tracking Issue counts down to **2029-04-13**, when
asteroid **99942 Apophis** (~340 m) passes ~32,000 km above Earth's surface — inside
geostationary orbit, naked-eye visible (~mag 3), and **not** a threat (impact ruled out
in 2021). Its parameters come from a dedicated `des=99942` query, since the flyby is
years outside the daily look-ahead window.

## What you get

- **GitHub Issues** — one per material event, labelled (`planetary-defense`, plus
  `sentry` / `close-approach` / `fireball` / `apophis` and a `severity-*` label).
  Idempotent: keyed by a hidden marker, updated in place, reopened if still live.
- **Fan-out (optional)** — `critical`/`high` events pushed to a generic webhook, Slack,
  Discord, or email. Each channel is a no-op unless its secret is set; failures are
  best-effort (Issues remain the complete record).
- **Pages observatory** — an accessible, responsive dashboard with a live Apophis
  countdown, plain-language safety posture, full searchable Sentry catalog, upcoming
  approaches, recent fireballs, source health, and downloadable JSON.

---

## Setup (GitHub — the intended deployment)

1. **Fork or clone** this repo to your account.
2. **Add the required secret** under *Settings → Secrets and variables → Actions*:
   - **`NASA_API_KEY`** — required ([get one free](https://api.nasa.gov/)).
   - `GITHUB_TOKEN` is provided automatically by Actions — you don't add it.
   - *(Optional fan-out)* `FANOUT_WEBHOOK_URL`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`,
     and/or `SMTP_HOST` + `SMTP_TO` (+ `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM`).
3. **Enable Pages:** *Settings → Pages → Build and deployment → Source → **GitHub Actions***.
4. The **daily workflow** (`.github/workflows/watch.yml`, 12:00 UTC) runs the watcher and
   publishes the page. Trigger it by hand any time: *Actions → watch → Run workflow*.

> **First run is a cold start:** it seeds the state snapshots and emits **zero** Issues
> (this prevents a day-one flood of every catalogued object). Issues begin on the *next*
> run, when a real delta is detected.

## Running locally

The watcher targets GitHub Actions, but you can run it on your machine.

**Requirements:** Python 3.14 and `httpx`. Install in a virtual environment so your
global Python is left untouched:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

**Configure** — copy the template and add your key (`.env` is gitignored):

```bash
cp .env.example .env      # then set NASA_API_KEY=...
```

**Dry run** — prints what it *would* post, touches nothing, makes no network call on a
cold start (but still requires `NASA_API_KEY` to be set):

```bash
python -m nasa_defense --dry-run
```

**Real run** — writes Issues; also needs `GITHUB_TOKEN` and `GITHUB_REPOSITORY`:

```bash
python -m nasa_defense
```

State is written under `state/`; the generated Pages artifact lives under `site/`
(`index.html`, frontend assets, `status.json`, and public source datasets).

## Environment variables

Real environment variables / CI secrets always take precedence over `.env`.

| Variable | Required? | Purpose |
|---|---|---|
| `NASA_API_KEY` | **Yes** | NASA/NeoWs key — the watcher hard-fails without it |
| `GITHUB_TOKEN` | For real runs | Auto-provided in Actions; needed to post Issues locally |
| `GITHUB_REPOSITORY` | For real runs | `owner/repo` (auto-provided in Actions) |
| `FANOUT_WEBHOOK_URL` / `SLACK_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL` | Optional | Fan-out channels |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_TO` | Optional | Email fan-out |
| `NASA_DEFENSE_STATE_DIR` / `NASA_DEFENSE_SITE_DIR` | Optional | Override output dirs (default `state/`, `site/`) |

## Tuning (`src/nasa_defense/config.py`)

Signal-vs-noise lives in one file. Key knobs:

| Setting | Default | Meaning |
|---|---|---|
| `PALERMO_FLOOR` | `-3.0` | Below this cumulative Palermo, Sentry changes are noise |
| `IP_JUMP_FACTOR` | `10.0` | Impact-probability rise that counts as a jump |
| `NOTEWORTHY_DIAMETER_M` | `140` | PHA-class size floor for a new Sentry object |
| `CAD_LOOKAHEAD_DAYS` | `30` | Forward window for close approaches |
| `CAD_MAX_LUNAR_DISTANCES` | `5.0` | Close-approach alert distance |
| `FIREBALL_ENERGY_MIN_KT` | `0.1` | Minimum bolide impact energy to report |
| `FANOUT_MIN_SEVERITY` | `high` | Only `high`/`critical` events fan out |
| `SITE_ENABLED` | `true` | Generate & publish the Pages site |

## Project layout

```
src/nasa_defense/
  config.py        # all thresholds, URLs, the Apophis constant, .env loader
  models.py        # SentryObject, CloseApproach, Fireball, Event
  state.py         # atomic JSON snapshot load/save
  detect.py        # the materiality engine (pure: previous + current -> events)
  render.py        # Event -> Markdown (deterministic templates)
  site.py          # snapshots -> static observatory + public JSON
  site_assets/     # version-controlled CSS and progressive JavaScript
  watch.py         # orchestrator (the only place wiring side effects)
  sources/         # one thin httpx client per endpoint (sentry, cad, fireball, neows, apophis)
  sinks/           # github_issues (system of record) + fanout (optional channels)
.github/workflows/ # ci.yml (ruff + pylint) · watch.yml (daily cron + Pages publish)
```

The functional core (`detect`/`render`) is pure and side-effect-free; all I/O lives at
the edges and is wired together only in `watch.py`.

## Notes

- **Not affiliated with NASA or JPL.** All data comes from their public APIs; please
  respect their rate limits.
- Alerting is **at-least-once**: an Issue is emitted before its snapshot is saved, so a
  failed run re-detects and re-alerts next cycle (idempotent upserts make that harmless).
- License: [MIT](LICENSE).

## The RYASTRA fleet

| Repo | What it is |
|---|---|
| **nasa-defense** | Planetary-defense watch (the original watcher engine) *(this repo)* |
| [nasa-mcp](https://github.com/RYASTRA/nasa-mcp) | All 16 NASA public APIs as an MCP server (R&D layer) |
| [nasa-new-worlds](https://github.com/RYASTRA/nasa-new-worlds) | New-worlds watch — exoplanet confirmations |
| [nasa-observatory](https://github.com/RYASTRA/nasa-observatory) | Fleet dashboard — one tile per watcher |
| [nasa-space-biology](https://github.com/RYASTRA/nasa-space-biology) | Faceted explorer for OSDR space-biology studies |
| [nasa-space-weather](https://github.com/RYASTRA/nasa-space-weather) | Space-weather watch |
| [nasa-tech-explorer](https://github.com/RYASTRA/nasa-tech-explorer) | NASA patents, free software & spinoffs — searchable |
