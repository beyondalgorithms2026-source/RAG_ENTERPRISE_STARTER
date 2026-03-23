import json
import logging
import sys
from typing import Any


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


setup_logging()
logger = logging.getLogger("rag_mm_master_poc")


def _normalize_log_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _normalize_log_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_log_value(item) for item in value]
    return str(value)


def log_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    payload = {"event": event}
    for key, value in fields.items():
        if value is not None:
            payload[key] = _normalize_log_value(value)
    logger.log(level, json.dumps(payload, sort_keys=True))
