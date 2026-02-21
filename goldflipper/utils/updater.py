"""
Update checker for Goldflipper.

Fetches a version.json manifest from a configurable URL and compares it
against the running version.  Designed to run in a background thread so it
never blocks TUI startup.

Expected version.json schema
-----------------------------
{
    "version":      "0.3.1",
    "download_url": "https://cloud.zimerguz.net/public.php/webdav/goldflipper-0.3.1-x64.msi",
    "notes":        "Goldflipper Multi 0.3 from 2026 February"
}

The URL is set in settings.yaml under update_check.url.  Leave it blank to
disable update checking entirely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class UpdateInfo:
    """Result of a completed update check."""

    current_version: str
    latest_version: str
    download_url: str
    notes: str
    is_newer: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_semver(version: str) -> tuple[int, ...]:
    """
    Parse 'X.Y.Z' or 'X.Y.Z-suffix' into a comparable integer tuple.
    Unknown / malformed strings return (0, 0, 0).
    """
    base = version.split("-")[0].split("+")[0]
    try:
        return tuple(int(x) for x in base.split("."))
    except ValueError:
        return (0, 0, 0)


def _get_current_version() -> str:
    """
    Return the running version string.

    Resolution order:
    1. goldflipper.__version__  (reliable in both source and Nuitka frozen mode)
    2. importlib.metadata       (works in source / installed-wheel mode)
    3. "0.0.0"                  (safe fallback — update check will still run)
    """
    try:
        from goldflipper import __version__  # type: ignore[attr-defined]

        return __version__
    except Exception:
        pass
    try:
        from importlib.metadata import version

        return version("goldflipper")
    except Exception:
        pass
    return "0.0.0"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_for_update(url: str, timeout: float = 5.0) -> UpdateInfo | None:
    """
    Fetch *url*, parse version.json, and compare against the running version.

    Returns an UpdateInfo on success (even if not newer so callers can log it).
    Returns None on any network or parse error — callers need no try/except.
    """
    if not url or not url.strip():
        return None

    try:
        import requests

        resp = requests.get(url.strip(), timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        latest = str(data.get("version", "")).strip()
        if not latest:
            log.debug("update check: version.json missing 'version' field")
            return None

        current = _get_current_version()
        return UpdateInfo(
            current_version=current,
            latest_version=latest,
            download_url=str(data.get("download_url", "")).strip(),
            notes=str(data.get("notes", "")).strip(),
            is_newer=_parse_semver(latest) > _parse_semver(current),
        )

    except Exception as exc:
        log.debug("update check failed: %s", exc)
        return None
