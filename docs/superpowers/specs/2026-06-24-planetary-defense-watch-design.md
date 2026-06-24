# nasa-defense — Planetary-Defense Watch (Design)

**Status:** Approved design, ready for implementation planning
**Date:** 2026-06-24
**Repo:** https://github.com/ryroeu/nasa-defense

## 1. Summary

A repo-native, zero-infrastructure **planetary-defense watcher**. On a daily
schedule, GitHub Actions runs a Python job that pulls NASA/JPL CNEOS's
authoritative near-Earth-object risk data, detects *materially* significant
changes against its last known view of the world, and raises **GitHub Issues**
with deterministic, plain-language briefings.

The unmet need it fills: nobody turns the **Sentry impact-risk table's deltas**
into human-legible alerts. CNEOS publishes the authoritative data as raw JSON;
this project is the friendly "watch it, alert me when it materially changes, and
explain why in plain English" layer on top.

## 2. Goals / Non-goals

### Goals
- Detect and report material changes in NASA/JPL planetary-defense data daily.
- Zero standing infrastructure: the GitHub repo *is* the deployment.
- Alerts are actionable and low-noise — orbit-refinement jitter must not fire.
- Plain-language explanations generated deterministically (reproducible, free,
  no hallucination risk).
- A signature, always-current "Apophis 2029" countdown tracking the
  once-in-a-millennium 2029-04-13 close approach.

### Non-goals
- No web UI / dashboard.
- No Docker.
- No LLM in the pipeline.
- No external notification services (email/SMTP, Slack, Discord, webhooks).
- No dependency on, or integration with, any other project. This repo is
  fully standalone.

## 3. Data sources

All sources are public NASA/JPL endpoints. Three CNEOS feeds are keyless; only
NeoWs benefits from a key.

| Source | Endpoint | Auth | Purpose |
|---|---|---|---|
| CNEOS Sentry | `https://ssd-api.jpl.nasa.gov/sentry.api` | none | Impact-risk table (the crown jewel) |
| CNEOS Close-Approach Data (CAD) | `https://ssd-api.jpl.nasa.gov/cad.api` | none | Upcoming/past close approaches |
| CNEOS Fireball | `https://ssd-api.jpl.nasa.gov/fireball.api` | none | Observed atmospheric bolide events |
| NeoWs Feed | `https://api.nasa.gov/neo/rest/v1/feed` | `NASA_API_KEY` (DEMO_KEY fallback) | Enrichment: "potentially hazardous" flag + diameter estimates |

NeoWs enrichment is **non-critical**: CNEOS is the authoritative source. If
NeoWs is rate-limited or down, the run proceeds without enrichment.

## 4. Domain concepts

Plain-language templates rely on the two standard hazard scales:

- **Torino Scale (0–10):** the public-communication scale combining impact
  probability and energy. `0` = no hazard / negligible; `1` = routine; `2–4` =
  meriting astronomer attention; `5–7` = threatening; `8–10` = certain
  collision. As of this writing every catalogued object sits at `0`, so **any
  object reaching Torino ≥ 1 is inherently newsworthy.**
- **Palermo Technical Scale (logarithmic):** compares an object's risk to the
  background impact hazard. `< -2` = no concern; `-2 to 0` = careful monitoring;
  `> 0` = risk exceeds background.

## 5. Materiality model & event taxonomy (the heart)

Every fetched datum is compared against the previous snapshot. Only **material**
changes produce events; everything else is treated as orbit-refinement noise and
ignored. All thresholds live in `config.py` (Section 13) so signal-vs-noise is a
one-file edit.

### Sentry events
| Event | Trigger | Notes |
|---|---|---|
| `SENTRY_NEW` | Designation present now, absent before | Only fires if the object clears a noteworthy floor (Palermo ≥ floor, **or** Torino ≥ 1, **or** diameter ≥ floor, **or** impact probability ≥ floor) so the long low-risk tail stays quiet |
| `SENTRY_REMOVED` | Designation absent now, present before | Fires only if the object was previously noteworthy (so we never announce the removal of something we never announced) — a removal usually means "ruled out," which is good news |
| `SENTRY_TORINO_UP` | Torino max increased and is now ≥ 1 | **Always fires** — the strongest signal |
| `SENTRY_TORINO_DOWN` | Torino max decreased | Fires if previously ≥ 1 (de-escalation is news too) |
| `SENTRY_PALERMO_UP` | Palermo (cumulative) rose past a step threshold and crosses the floor | |
| `SENTRY_IP_JUMP` | Impact probability rose by ≥ a configured factor and is above floor | Order-of-magnitude jumps |

### Close-approach events
| Event | Trigger | Notes |
|---|---|---|
| `CAD_NEW_CLOSE` | A newly-listed approach inside the look-ahead window and inside a distance threshold | Severity tiered by (miss distance, object size) |
| `CAD_SUBLUNAR` | A newly-listed approach passing closer than the Moon | Always fires |

Dedupe key includes the close-approach date so the same object's *different*
passes are distinct events, and re-runs don't re-alert the same pass.

### Fireball events
| Event | Trigger | Notes |
|---|---|---|
| `FIREBALL_NEW` | A new bolide above an energy threshold since last seen | Dedupe by (date, lat, lon) |

### Apophis anchor
Not a per-day event. A single **perpetually-updated tracking Issue** that always
reflects: days until 2029-04-13, and the latest known approach parameters.
Gives the project its signature feature without daily spam. See Section 11.

## 6. Architecture — isolated seams

Seven small units, each with one responsibility, communicating through plain
data structures so each is testable in isolation with no live network.

| Module | Responsibility | Depends on |
|---|---|---|
| `sources/` | Thin httpx clients — one per endpoint. Fetch → typed records. **No business logic.** | network only |
| `models.py` | Dataclasses: `SentryObject`, `CloseApproach`, `Fireball`, `Event`. Scale helpers. | nothing |
| `state.py` | Load/save JSON snapshots in `state/`. Pure serialization I/O. | filesystem |
| `detect.py` | **The soul.** `detect(previous, current) -> list[Event]`, applying materiality thresholds. Pure function, zero I/O. | models |
| `render.py` | `Event -> Markdown` (Issue title + body) via deterministic templates. Pure. | models |
| `sinks/github_issues.py` | Idempotent upsert of Issues (dedupe by stable key). Uses Actions' `GITHUB_TOKEN`. | GitHub API |
| `watch.py` | Orchestrator: fetch → load → detect → render → emit → save. The only place wiring side effects. | all |

`config.py` centralizes every threshold, window, URL, and the Apophis constant.

## 7. Package layout

```
nasa-defense/
  pyproject.toml
  README.md
  src/nasa_defense/
    __init__.py
    __main__.py            # entry point: python -m nasa_defense
    config.py
    models.py
    state.py
    detect.py
    render.py
    watch.py
    sources/
      __init__.py
      http.py              # shared httpx client w/ timeout + retry/backoff
      sentry.py
      close_approaches.py
      fireballs.py
      neows.py
    sinks/
      __init__.py
      github_issues.py
  state/                   # bot-maintained snapshots, committed by the workflow
    .gitkeep
  tests/
    fixtures/              # recorded JSON responses per source
    test_sources.py
    test_detect.py
    test_render.py
    test_sinks.py
    test_watch.py
  docs/
    superpowers/specs/2026-06-24-planetary-defense-watch-design.md
  .github/workflows/
    ci.yml                 # lint + test on push/PR
    watch.yml              # daily cron + manual dispatch
```

## 8. Data flow & fail-safe ordering

```
cron
  -> sources.fetch()           # per-source, isolated
  -> current snapshot
  -> state.load() previous
  -> if cold start: save state, emit nothing, exit
  -> detect(previous, current) -> events
  -> for each event: render() -> sinks.upsert_issue()
  -> update Apophis tracking issue (always)
  -> state.save()              # ONLY for sources whose events all emitted OK
  -> write run summary to $GITHUB_STEP_SUMMARY
  -> commit changed state files with [skip ci]
  -> exit nonzero if any sink failed (surfaces red in Actions)
```

**At-least-once alerting (correctness crux):** emit the alert *first*, persist
state *second*. State for a given source is advanced only after that source's
events are confirmed delivered. A crashed/failed run re-detects and re-alerts
next cycle; idempotent upserts (Section 10) make re-alerting harmless. The
system fails toward *over*-notifying, never silently *under*-notifying.

## 9. State persistence

Bot-maintained snapshots under `state/`, one file per source for small,
readable diffs (git history becomes the tamper-evident "what changed when"
ledger):

- `state/sentry.json` — designation → key risk fields.
- `state/close_approaches.json` — keyed by (designation, close-approach date).
- `state/fireballs.json` — keyed by (date, lat, lon).
- `state/meta.json` — schema version, last-run timestamp, cold-start flag.

Committed by `watch.yml` with `[skip ci]` so state commits never trigger CI.

**Cold-start guard:** on the very first run (no prior state), seed all snapshots
and emit **no** alerts — prevents a day-one flood of every existing Sentry
object. The Apophis tracking Issue is created on this first run.

## 10. GitHub Issue model & idempotency

Each material event maps to an Issue identified by a **stable dedupe key**
embedded as an HTML comment in the body (`<!-- nasa-defense-key: ... -->`). The
sink searches open Issues for the key; if found it updates the body and adds an
update comment; otherwise it creates a new Issue.

Dedupe keys:
- Sentry: `sentry:<des>` — one Issue per object, updated as its risk evolves.
- Close approach: `cad:<des>:<cd-date>` — one per approach event.
- Fireball: `fireball:<date>:<lat>:<lon>`.
- Apophis: `apophis:2029` — single perpetual tracking Issue.

Labels (created if missing): `planetary-defense` plus a per-type label
(`sentry`, `close-approach`, `fireball`, `apophis`) and a severity label where
relevant (e.g. `torino-ge-1`). The label taxonomy makes triage and filtering
trivial.

## 11. Apophis anchor

A single Issue keyed `apophis:2029`, created at cold start and updated every run:
- Countdown: days until 2029-04-13.
- Latest known close-approach parameters from CAD/Sentry.
- Brief, fixed explanatory context (why this flyby matters; naked-eye
  visibility; it is *not* a threat in 2029).

This ties the repo to the global public moment (the UN's International Year of
Asteroid Awareness and Planetary Defence) without generating daily noise.

## 12. Runtime

Two workflows, stock GitHub-hosted runners, native Python — no Docker.

### `watch.yml`
- Trigger: `schedule: cron: '0 12 * * *'` (daily 12:00 UTC) + `workflow_dispatch`.
- Permissions: `issues: write`, `contents: write` (to commit state).
- Steps: checkout → setup-python 3.14 → install → `python -m nasa_defense` →
  commit changed `state/` with `[skip ci]`.
- Env: `NASA_API_KEY` from repo secrets (optional; DEMO_KEY fallback);
  `GITHUB_TOKEN` provided automatically by Actions.

### `ci.yml`
- Trigger: push / pull_request.
- Steps: setup-python 3.14 → install → `ruff` + `pylint` + `pytest`.

## 13. Configuration (`config.py`)

Single source of truth for tuning. Initial defaults (to be validated against
live data during implementation):

| Setting | Default | Meaning |
|---|---|---|
| `PALERMO_FLOOR` | `-3.0` | Below this, Sentry changes are noise |
| `IP_JUMP_FACTOR` | `10.0` | Impact-probability increase that counts as a jump |
| `NOTEWORTHY_DIAMETER_M` | `140` | PHA-class size threshold for `SENTRY_NEW` |
| `CAD_LOOKAHEAD_DAYS` | `30` | Forward window for close approaches |
| `CAD_MAX_LUNAR_DISTANCES` | `5.0` | Close-approach alert distance |
| `CAD_SUBLUNAR_ALWAYS` | `true` | Always alert on sub-lunar passes |
| `FIREBALL_ENERGY_MIN_KT` | `0.1` | Minimum bolide energy to report |
| `FETCH_LOOKBACK_DAYS` | `7` | Look-back for CAD/fireball/NeoWs queries |
| `APOPHIS_DESIGNATION` | `99942` | |
| `APOPHIS_DATE` | `2029-04-13` | |
| `HTTP_TIMEOUT_S` | `30` | |
| `HTTP_RETRIES` | `3` | Exponential backoff on 5xx/timeout |

## 14. Error handling & edge cases

- **Per-source isolation:** a failed/zero-result source is skipped for the run
  and does not sink the whole job; its state is left unchanged so it re-detects
  next cycle.
- **HTTP transients:** shared client retries 5xx/timeouts with exponential
  backoff.
- **NeoWs rate limit (429):** enrichment is skipped gracefully (non-critical).
- **Cold start:** seed state, emit nothing, create the Apophis Issue.
- **GitHub API:** paginate when searching open Issues; back off on secondary
  rate limits; treat sink failure as a hard run failure (red Action) but only
  *after* not advancing the affected source's state.
- **Schema drift / unexpected fields:** sources parse defensively; an
  unparseable record is logged and skipped, never crashes the run.

## 15. Testing strategy

- `tests/fixtures/` — small, representative recorded JSON per source.
- `test_sources.py` — parse fixtures → models with mocked HTTP (no live net).
- `test_detect.py` — **the critical suite.** One case per event type **plus
  explicit "noise must NOT alert" cases**: a Palermo nudge of 0.01 must not
  fire; an IP change below the factor must not fire; cold start emits nothing.
- `test_render.py` — Markdown snapshot tests per event type; assert numbers are
  correct and **no template placeholders leak**.
- `test_sinks.py` — faked GitHub client; assert upsert idempotency (create vs
  update), label creation, key matching.
- `test_watch.py` — end-to-end with all sources faked, a fake sink, and a tmp
  state dir; assert emit-then-persist ordering and per-source isolation (one
  source raising does not block others; failed source's state not advanced).
- `--dry-run` — prints what it *would* post without touching GitHub or
  committing; also the local-dev entry point and an end-to-end smoke test.
- CI runs `ruff` + `pylint` + `pytest` on Python 3.14.

## 16. Conventions

- Python 3.14.3; `requires-python >=3.14`; CI matrix `["3.14"]`.
- `src/` layout; httpx for HTTP; ruff + pylint clean.
- Commit directly to `main`; no feature branches.
- Secrets never committed; `NASA_API_KEY` only via repo secrets / local env.

## 17. Out of scope (possible future work)

- Static GitHub Pages site rendering the current state for the public.
- Optional LLM pass to smooth prose (off by default; spine stays deterministic).
- Additional sources (e.g. ESA NEOCC risk list cross-check).
- Webhook/Slack/Discord/email fan-out sinks.
