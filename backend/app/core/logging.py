import json
import logging
import sys
from typing import Any
import os
from dotenv import load_dotenv

from app.auth.context import get_current_user

# Load .env file so os.getenv() can access variables
load_dotenv()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


setup_logging()
database_name_local=os.getenv("DATABASE_NAME")
logger = logging.getLogger(database_name_local)


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
    user = get_current_user()
    if user is not None:
        payload["user_id"] = user.user_id
        if user.email:
            payload["user_email"] = user.email
        if user.roles:
            payload["user_roles"] = list(user.roles)
        if user.groups:
            payload["user_groups"] = list(user.groups)
    for key, value in fields.items():
        if value is not None:
            payload[key] = _normalize_log_value(value)
    logger.log(level, json.dumps(payload, sort_keys=True))
