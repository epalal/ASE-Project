from datetime import datetime, timezone
import json
import logging

MAX_FIELD = 64
_logger = logging.getLogger("audit")
_logger.setLevel(logging.INFO)


def _short(value) -> str:
    return str(value)[:MAX_FIELD]


def audit(event: str, outcome: str, user: str = "-", **facts) -> None:
    """Write a single-line JSON audit event without secrets or unescaped newlines."""
    now = datetime.now(timezone.utc)
    record = {
        "ts": now.isoformat(timespec="seconds"),
        "event": _short(event),
        "user": _short(user) if user else "-",
        "outcome": _short(outcome),
    }
    record.update({k: _short(v) for k, v in facts.items()})
    _logger.info(json.dumps(record, ensure_ascii=True, separators=(",", ":")))