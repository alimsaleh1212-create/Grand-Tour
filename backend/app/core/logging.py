"""Structured JSON logging setup.

HOW THIS MODULE FITS INTO THE STARTUP FLOW
-------------------------------------------
Called as the FIRST step inside lifespan() in app/main.py, before settings
validation, DB engine creation, or router registration. This ensures that
every subsequent step is observable.

After setup_logging() returns, every module in the app uses:
    logger = logging.getLogger(__name__)
    logger.info("some.event", extra={"key": "value"})

Each call emits exactly one JSON line to stdout, e.g.:
    {"ts": "2024-01-15T10:23:45.123456+00:00", "level": "INFO",
     "logger": "app.routers.health", "msg": "health.check"}

WHY JSON OVER PLAIN TEXT
-------------------------
- Production log aggregators (Datadog, CloudWatch, Loki) parse JSON natively.
  Searching all events for user_id=42 is one query, not a grep + awk pipeline.
- Structured fields (user_id, tool_name, latency_ms) are first-class: you
  can filter, aggregate, and alert on them without regex.
- Counting agent failures over time is a SQL-style query, not grep + awk.

SENSITIVE FIELDS
-----------------
This formatter does NOT redact. Callers are responsible for never passing
passwords, JWT tokens, API keys, or PII in extra={} kwargs. See CLAUDE.md §22.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# stdlib attribute names that exist on every LogRecord — we skip these when
# collecting caller-supplied extra={} kwargs to avoid polluting the JSON output.
_STDLIB_ATTRS: frozenset[str] = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
)
# A few more attrs that logging adds internally after __init__:
_STDLIB_ATTRS = _STDLIB_ATTRS | {
    "message",
    "asctime",
    "taskName",  # Python 3.12+
}


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Standard fields every line includes:
        ts      — ISO-8601 UTC timestamp
        level   — DEBUG / INFO / WARNING / ERROR / CRITICAL
        logger  — dotted module path (e.g. "app.agent.tools.live_conditions")
        msg     — the log message string

    Extra fields from logger.info("event", extra={"user_id": 42}):
        Any key in extra={} that is NOT a stdlib LogRecord attribute is
        included verbatim in the JSON object. This is how callers add
        structured context like user_id, tool_name, latency_ms, etc.

    Exception information:
        If an exception is active (logger.exception / exc_info=True), an
        "exc" key is added with the exception type and message. Full
        tracebacks are intentionally omitted from JSON output — they go to
        stderr separately and are captured by most log aggregators anyway.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Attach caller-supplied extra={} kwargs (skip all stdlib attrs).
        for key, value in record.__dict__.items():
            if key not in _STDLIB_ATTRS:
                payload[key] = value

        # Add exception summary when present (type + message, not full traceback).
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            payload["exc"] = f"{type(exc).__name__}: {exc}"

        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with JSON output.

    Args:
        level: Logging level string ("DEBUG", "INFO", "WARNING", "ERROR").
               Loaded from settings.log_level so it is env-driven.

    Side effects:
        - Installs _JsonFormatter on a StreamHandler writing to stdout.
        - Sets the root logger level.
        - Pins noisy third-party loggers to WARNING so they don't drown
          application events in production logs.

    Call this exactly once, as the first statement inside lifespan(), before
    any other code that might emit log lines.
    """
    # Root handler: one JSON object per line to stdout.
    # Docker / most log aggregators capture stdout automatically.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level.upper())
    # Remove any handlers that were added before us (e.g. by uvicorn's
    # default config) to avoid duplicate lines.
    root.handlers.clear()
    root.addHandler(handler)

    # ── Silence noisy third-party loggers ────────────────────────────────────
    # These libraries are very chatty at DEBUG/INFO but their output is rarely
    # useful in production. Pin them to WARNING so they only surface problems.
    _quiet = [
        "uvicorn.access",  # every HTTP request line — too verbose
        "uvicorn.error",  # keep at WARNING to see startup/shutdown messages
        "httpx",  # every outgoing HTTP call body/headers
        "sqlalchemy.engine",  # every SQL statement (dev only; see echo= in main.py)
        "multipart",  # form data parsing internals
        "asyncio",  # low-level event loop noise
    ]
    for name in _quiet:
        logging.getLogger(name).setLevel(logging.WARNING)
