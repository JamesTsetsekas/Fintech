#!/usr/bin/env python3
"""Decide whether an hourly refresh should publish, using a small local marker.

The scheduled refresh normally publishes only in the six-hour UTC windows. The
marker (``logs/publish-pending.json``, which is gitignored) records the source
HEAD and the outcome of the last publish attempt so that a failed publish, or a
source change since the last successful publish, is retried at the next hourly
run instead of waiting for the next window. Without a marker the original
six-hour behaviour is unchanged.

Only the standard library is used so the shell wrapper can call it with any
Python 3 interpreter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PUBLISH_WINDOW_HOURS = 6
DEFAULT_MARKER_PATH = Path(__file__).resolve().parent / "logs" / "publish-pending.json"


def read_marker(path: Path = DEFAULT_MARKER_PATH) -> dict:
    """Return the marker, or an empty dict when absent or unreadable."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def publish_decision(utc_hour: int, source_head: str | None, marker: dict | None) -> tuple[bool, str]:
    """Return ``(should_publish, reason)`` for this hourly run."""
    if utc_hour % PUBLISH_WINDOW_HOURS == 0:
        return True, "scheduled-window"
    marker = marker or {}
    status = marker.get("status")
    if status == "failed":
        return True, "retry-failed-publish"
    if status == "success" and source_head and marker.get("source_head") != source_head:
        return True, "source-changed"
    return False, "deferred"


def record_attempt(
    source_head: str | None,
    success: bool,
    path: Path = DEFAULT_MARKER_PATH,
    *,
    now: datetime | None = None,
) -> None:
    """Atomically record the outcome of a publish attempt."""
    path = Path(path)
    previous = read_marker(path)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    payload = {
        "status": "success" if success else "failed",
        "source_head": source_head,
        "last_attempt_at": stamp,
        # Keep the last good head for diagnostics when a later attempt fails.
        "last_success_head": source_head if success else previous.get("last_success_head"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    decide = sub.add_parser("decide", help="print 'publish <reason>' or 'defer <reason>'")
    decide.add_argument("--hour", type=int, required=True, help="current UTC hour (0-23)")
    decide.add_argument("--head", default="", help="current source HEAD sha")
    decide.add_argument("--marker", type=Path, default=DEFAULT_MARKER_PATH)
    args = parser.parse_args(argv)
    should_publish, reason = publish_decision(args.hour, args.head or None, read_marker(args.marker))
    print(f"{'publish' if should_publish else 'defer'} {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
