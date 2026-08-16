"""Report Overture's pinned release against the official release calendar.

This command is intentionally read-only.  It never edits ``config/overture.json``
and it never installs or updates the optional client package.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .io import read_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "overture.json"
RELEASE_PATTERN = re.compile(r"20\d{2}-\d{2}-\d{2}\.0")


def _fetch_release_calendar(url: str, timeout: float = 5.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "uplb-roblox-geodata/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS URL from config
        return response.read().decode("utf-8", errors="replace")


def _latest_release(html: str) -> str | None:
    releases = sorted(set(RELEASE_PATTERN.findall(html)))
    return releases[-1] if releases else None


def check_updates(config_path: Path = DEFAULT_CONFIG, *, fetch: bool = True, timeout: float = 5.0) -> dict[str, Any]:
    config = read_json(config_path)
    pinned = str(config["pinnedRelease"])
    calendar = str(config["officialReleaseCalendar"])
    diagnostics: list[str] = []
    network_status = "not-run"
    current: str | None = None
    if fetch:
        try:
            current = _latest_release(_fetch_release_calendar(calendar, timeout=timeout))
            network_status = "validated" if current else "no-release-found"
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            network_status = "unavailable"
            diagnostics.append(f"official release calendar unavailable: {exc.__class__.__name__}: {exc}")
    if current is None:
        current = config.get("lastVerifiedOfficialRelease")
        if current:
            diagnostics.append("using the last locally verified official release; no config mutation performed")
    update_available = None if current is None else current != pinned
    return {
        "provider": config.get("provider", "Overture Maps Foundation"),
        "role": config.get("role"),
        "pinnedRelease": pinned,
        "currentOfficialPublishedRelease": current,
        "updateAvailable": update_available,
        "networkStatus": network_status,
        "releaseCalendar": calendar,
        "package": config.get("package"),
        "diagnostics": diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--offline", action="store_true", help="use the last locally verified release without network access")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    print(json.dumps(check_updates(args.config, fetch=not args.offline, timeout=args.timeout), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
