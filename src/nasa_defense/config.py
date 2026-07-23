"""Tunable thresholds, API endpoints, and filesystem paths resolved from the environment."""
from __future__ import annotations

import os
from pathlib import Path

# --- Sentry materiality ---
PALERMO_FLOOR = -3.0
PALERMO_STEP = 1.0
IP_JUMP_FACTOR = 10.0
IP_FLOOR = 1e-4
NOTEWORTHY_DIAMETER_M = 140.0

# --- Close approaches (Plan 02; defined here as single source of truth) ---
CAD_LOOKAHEAD_DAYS = 30
CAD_MAX_LUNAR_DISTANCES = 5.0
AU_PER_LUNAR_DISTANCE = 0.002569
CAD_SUBLUNAR_ALWAYS = True
CAD_HIGH_LD = 3.0
CAD_NOTEWORTHY_H_MAX = 22.0

# --- Fireballs (Plan 03) ---
FIREBALL_ENERGY_MIN_KT = 0.1
FIREBALL_HIGH_KT = 1.0

# --- Fetch windows ---
FETCH_LOOKBACK_DAYS = 7
FIREBALL_LOOKBACK_DAYS = 30  # fireball data is published with a multi-week lag

# --- Output ---
FANOUT_MIN_SEVERITY = "high"
SITE_ENABLED = True

# --- Apophis (Plan 05) ---
APOPHIS_DESIGNATION = "99942"
APOPHIS_DATE = "2029-04-13"

# --- HTTP ---
# The retries must span enough wall clock to outlast an upstream gateway blip, which is
# what defeats them — not the attempt count. Equal-jitter backoff over 5 attempts spans
# 7.5-15s, against the ~3s that let a JPL 502 take down watch run #33.
HTTP_TIMEOUT_S = 30.0
HTTP_RETRIES = 5
HTTP_BACKOFF_BASE_S = 1.0
HTTP_BACKOFF_CAP_S = 10.0

# --- Source health ---
# A source that is briefly unreachable is expected and self-healing: its state is not
# advanced, so the next run re-detects whatever was missed. Only escalate to a hard
# failure once a source has been down for this many consecutive runs, at which point we
# may genuinely be blind to something rather than just waiting out an outage.
SOURCE_FAILURE_LIMIT = 3

# --- Endpoints ---
SENTRY_API = "https://ssd-api.jpl.nasa.gov/sentry.api"
CAD_API = "https://ssd-api.jpl.nasa.gov/cad.api"
FIREBALL_API = "https://ssd-api.jpl.nasa.gov/fireball.api"
NEOWS_FEED = "https://api.nasa.gov/neo/rest/v1/feed"

# --- Paths ---
STATE_DIR = Path(os.environ.get("NASA_DEFENSE_STATE_DIR", "state"))
SITE_DIR = Path(os.environ.get("NASA_DEFENSE_SITE_DIR", "site"))

SCHEMA_VERSION = 1


def nasa_api_key() -> str:
    """Return the NASA API key from the environment.

    Raises:
        RuntimeError: when NASA_API_KEY is unset, naming the places it can be set.
    """
    key = os.environ.get("NASA_API_KEY")
    if not key:
        raise RuntimeError(
            "NASA_API_KEY is not set — add it to .env (see .env.example) or set it "
            "in the environment / GitHub Actions secrets."
        )
    return key


def load_dotenv(path: Path | str = ".env") -> None:
    """Load `KEY=VALUE` lines from a local .env into the environment for keys not
    already set (real env vars / CI secrets always win). Convenience for local
    runs; a no-op when the file is absent."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
