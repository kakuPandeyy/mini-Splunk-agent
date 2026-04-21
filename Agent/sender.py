import json
import logging
import time

import httpx

from Agent.config import BACKEND_URL, DEAD_LETTER_FILE, MAX_RETRIES

log = logging.getLogger(__name__)

_token: str | None = None
_username: str = ""
_password: str = ""


def set_credentials(username: str, password: str) -> None:
    global _username, _password
    _username, _password = username, password


def _login() -> bool:
    global _token
    if not _username or not _password:
        log.error("credentials not set — call set_credentials() before sending")
        return False
    try:
        r = httpx.post(
            f"{BACKEND_URL}/auth/login",
            json={"username": _username, "password": _password},
            timeout=10,
        )
        if r.status_code == 401:
            log.error("agent login failed — wrong credentials")
            return False
        r.raise_for_status()
        _token = r.json()["access_token"]
        log.info("agent logged in as '%s'", _username)
        return True
    except Exception as exc:
        log.error("agent login error: %s", exc)
        return False


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_token}"} if _token else {}


def send_batch(lines: list[dict]) -> bool:
    """Send a batch to the backend. Returns True on success, False after all retries fail."""
    global _token

    if not _token:
        if not _login():
            _write_dead_letter(lines)
            return False

    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = httpx.post(
                f"{BACKEND_URL}/logs/batch",
                json=lines,
                headers=_auth_headers(),
                timeout=10,
            )
            if r.status_code == 401:
                log.warning("token expired — re-logging in")
                _token = None
                if not _login():
                    break
                continue
            r.raise_for_status()
            log.debug("sent %d lines", len(lines))
            return True
        except Exception as exc:
            log.warning("send attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2

    log.error("all retries exhausted — writing %d lines to dead-letter file", len(lines))
    _write_dead_letter(lines)
    return False


def check_backend() -> bool:
    """Return True if the backend is reachable."""
    try:
        httpx.get(BACKEND_URL, timeout=5).raise_for_status()
        return True
    except Exception:
        return False


def _write_dead_letter(lines: list[dict]) -> None:
    try:
        with open(DEAD_LETTER_FILE, "a", encoding="utf-8") as f:
            for entry in lines:
                f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        log.error("could not write dead-letter file '%s': %s", DEAD_LETTER_FILE, exc)
