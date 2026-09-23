"""Structured-ish logging — spec §65: named events (sync_started,
sync_completed, sync_failed, spotify_rate_limit, youtube_quota_warning,
matching_failed, token_refresh_failed), never tokens/secrets.

Deliberately not real JSON structured logging (no new dependency, no log
aggregator to send it to yet) — a `logger.info("event_name", extra={...})`
call with a formatter that prints the extras is enough to be greppable
today and trivial to upgrade to JSON later if a real observability backend
shows up (Regla 75: no sobreingeniería).
"""

import logging
import sys

logger = logging.getLogger("synctune")


class _EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__ and k != "message"
        }
        if extras:
            base += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


def configure_logging() -> None:
    if logger.handlers:
        return  # already configured (e.g. re-imported under --reload)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_EventFormatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
