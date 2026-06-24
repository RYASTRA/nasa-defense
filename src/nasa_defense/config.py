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

# --- Output ---
FANOUT_MIN_SEVERITY = "high"
SITE_ENABLED = True

# --- Apophis (Plan 05) ---
APOPHIS_DESIGNATION = "99942"
APOPHIS_DATE = "2029-04-13"

# --- HTTP ---
HTTP_TIMEOUT_S = 30.0
HTTP_RETRIES = 3

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
    return os.environ.get("NASA_API_KEY", "DEMO_KEY")
