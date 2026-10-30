"""Deployment guards: GET /healthz and daily/monthly spend caps.

/healthz answers {"status": "ok"} with no model, embedding or database call, so it is always fast.

Spend is counted in SQLite (SPEND_DB_PATH, default /data/spend.sqlite, ./data/spend.sqlite when /data is
missing or APP_ENV=local). `record_spend` is called with the real cost worked out from the provider's token usage
(app/llm/client.py), or EST_COST_PER_CALL_USD when no usage came back. Over DAILY_SPEND_CAP_USD (default 0.50) or
MONTHLY_SPEND_CAP_USD (default 5), requests that change something answer HTTP 429 with a plain message.
Auth, admin and health routes stay reachable. The ledger fails open: a broken file never blocks visitors.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

DEFAULT_ORIGINS = ["https://spanfold.com", "https://www.spanfold.com"]
LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
DEFAULT_DAILY = 0.50
DEFAULT_MONTHLY = 5.00
DEFAULT_EST_PER_CALL = 0.002
EXEMPT_WORDS = ("auth", "login", "logout", "admin", "healthz")
MSG_DAILY = "This demo has reached its daily limit. Please try again tomorrow."
MSG_MONTHLY = "This demo has reached its monthly limit. Please try again next month."


class DemoLimitReached(Exception):
    def __init__(self, scope: str):
        self.scope = scope  # "daily" or "monthly"
        super().__init__(MSG_DAILY if scope == "daily" else MSG_MONTHLY)


def _env_float(name: str, default: float) -> float:
    try:
        v = float(os.environ.get(name, "").strip())
        return v if v >= 0 else default
    except ValueError:
        return default


def is_local() -> bool:
    return os.environ.get("APP_ENV", "").strip().lower() == "local"


def spend_db_path() -> Path:
    p = os.environ.get("SPEND_DB_PATH", "").strip()
    if p:
        return Path(p)
    data = Path("/data")
    if not is_local() and data.is_dir() and os.access(data, os.W_OK):
        return data / "spend.sqlite"
    return Path("./data/spend.sqlite")


def _connect() -> sqlite3.Connection:
    p = spend_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(p), timeout=5)
    db.execute("CREATE TABLE IF NOT EXISTS spend (ts REAL, day TEXT, month TEXT, demo TEXT, usd REAL)")
    db.execute("CREATE INDEX IF NOT EXISTS spend_day ON spend(day)")
    return db


def totals(now: Optional[float] = None) -> tuple:
    """(dollars today, dollars this month), UTC calendar."""
    t = time.gmtime(now if now is not None else time.time())
    day, month = time.strftime("%Y-%m-%d", t), time.strftime("%Y-%m", t)
    db = _connect()
    try:
        d = db.execute("SELECT COALESCE(SUM(usd),0) FROM spend WHERE day=?", (day,)).fetchone()[0]
        m = db.execute("SELECT COALESCE(SUM(usd),0) FROM spend WHERE month=?", (month,)).fetchone()[0]
    finally:
        db.close()
    return float(d), float(m)


def over_cap(now: Optional[float] = None) -> Optional[str]:
    try:
        d, m = totals(now)
    except (sqlite3.Error, OSError, ValueError):
        return None
    if d >= _env_float("DAILY_SPEND_CAP_USD", DEFAULT_DAILY):
        return "daily"
    if m >= _env_float("MONTHLY_SPEND_CAP_USD", DEFAULT_MONTHLY):
        return "monthly"
    return None


def check_caps(now: Optional[float] = None) -> None:
    scope = over_cap(now)
    if scope:
        raise DemoLimitReached(scope)


def record_spend(usd: Optional[float], label: str = "", now: Optional[float] = None) -> float:
    """Add one paid call. Real cost when known (> 0), otherwise EST_COST_PER_CALL_USD."""
    amount = float(usd) if usd and usd > 0 else _env_float("EST_COST_PER_CALL_USD", DEFAULT_EST_PER_CALL)
    ts = now if now is not None else time.time()
    t = time.gmtime(ts)
    try:
        db = _connect()
        try:
            db.execute(
                "INSERT INTO spend VALUES (?,?,?,?,?)",
                (ts, time.strftime("%Y-%m-%d", t), time.strftime("%Y-%m", t), label, amount),
            )
            db.commit()
        finally:
            db.close()
    except (sqlite3.Error, OSError, ValueError):
        pass
    return amount


def _exempt(path: str) -> bool:
    p = path.lower()
    return any(w in p for w in EXEMPT_WORDS)


def install_gate(app) -> None:
    """Add /healthz, the DemoLimitReached handler and the spend gate.

    Call it BEFORE the CORS middleware is added, so CORS wraps the 429 reply and the browser can read it.
    """
    from fastapi.responses import JSONResponse

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    def limit_response(scope: str) -> JSONResponse:
        msg = MSG_DAILY if scope == "daily" else MSG_MONTHLY
        return JSONResponse(
            {"detail": msg, "error": "demo_limit_reached", "limit": scope},
            status_code=429,
            headers={"Retry-After": "3600", "Cache-Control": "no-store"},
        )

    @app.exception_handler(DemoLimitReached)
    async def _limit_handler(request, exc):
        return limit_response(exc.scope)

    @app.middleware("http")
    async def _spend_gate(request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not _exempt(request.url.path):
            scope = over_cap()
            if scope:
                return limit_response(scope)
        return await call_next(request)
