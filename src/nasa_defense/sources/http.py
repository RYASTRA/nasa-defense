from __future__ import annotations

import time

import httpx

from .. import config


def get_json(url: str, params: dict | None = None) -> dict:
    last_exc: Exception | None = None
    for attempt in range(config.HTTP_RETRIES):
        try:
            resp = httpx.get(url, params=params, timeout=config.HTTP_TIMEOUT_S)
        except httpx.TransportError as exc:
            last_exc = exc
        else:
            if resp.status_code < 500:
                resp.raise_for_status()  # raises on 4xx (not retried)
                return resp.json()
            last_exc = httpx.HTTPStatusError(
                f"server error {resp.status_code}", request=resp.request, response=resp
            )
        if attempt < config.HTTP_RETRIES - 1:
            time.sleep(2**attempt)
    assert last_exc is not None
    raise last_exc
