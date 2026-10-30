"""Deploy guards: /healthz, CORS allow-list, daily/monthly spend caps (provider mocked), keepalive script.

No database and no network needed. The real app is built in a subprocess so its import-time CORS settings come from
the environment given here.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core import deploy  # noqa: E402

PROVIDER_WORDS = ("openai", "deepseek", "anthropic", "claude", "gpt", "gemini", "llama", "mistral")

CHILD = r"""
import json, sys
from fastapi.testclient import TestClient
import app.main as m
m.sync_authenticated_user = lambda user: None
c = TestClient(m.app)
out = {}
out["healthz"] = c.get("/healthz").json()
for name, origin in (("site", "https://spanfold.com"), ("evil", "https://evil.example"), ("local", "http://localhost:3000")):
    out[name] = c.get("/healthz", headers={"Origin": origin}).headers.get("access-control-allow-origin")
r = c.post("/ask", json={"question": "hi"}, headers={"Origin": "https://spanfold.com"})
out["ask_status"] = r.status_code
out["ask_body"] = r.text
out["ask_cors"] = r.headers.get("access-control-allow-origin")
out["healthz_after"] = c.get("/healthz").status_code
print("RESULT" + json.dumps(out))
"""


def run_app(env_extra, tmp):
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOWED_ORIGINS", "API_ALLOWED_ORIGINS", "APP_ENV")}
    env.update(
        {
            "SPEND_DB_PATH": str(Path(tmp) / "spend.sqlite"),
            "AUTH_MODE": "none",
            "AUTH_ENABLED": "false",
            "DATABASE_URL": "postgresql://nobody:nothing@127.0.0.1:1/none",
            "PYTHONPATH": str(BACKEND),
        }
    )
    env.update(env_extra)
    done = subprocess.run(
        [sys.executable, "-c", CHILD], env=env, cwd=str(BACKEND), capture_output=True, text=True, timeout=120
    )
    line = [x for x in done.stdout.splitlines() if x.startswith("RESULT")]
    if not line:
        raise AssertionError(done.stdout[-1500:] + done.stderr[-1500:])
    return json.loads(line[0][6:])


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(
            os.environ,
            {"SPEND_DB_PATH": str(Path(self.tmp.name) / "spend.sqlite")},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for k in ("DAILY_SPEND_CAP_USD", "MONTHLY_SPEND_CAP_USD", "EST_COST_PER_CALL_USD", "APP_ENV"):
            os.environ.pop(k, None)

    def test_healthz_and_cors_on_the_real_app(self):
        r = run_app({"APP_ENV": "demo"}, self.tmp.name)
        self.assertEqual(r["healthz"], {"status": "ok"})
        self.assertEqual(r["site"], "https://spanfold.com")
        self.assertIsNone(r["evil"])
        self.assertIsNone(r["local"])  # localhost is only allowed when APP_ENV=local

    def test_localhost_allowed_only_when_app_env_local(self):
        r = run_app({"APP_ENV": "local"}, self.tmp.name)
        self.assertEqual(r["local"], "http://localhost:3000")
        self.assertIsNone(r["evil"])

    def test_allowed_origins_env_replaces_the_default(self):
        r = run_app({"APP_ENV": "demo", "ALLOWED_ORIGINS": "https://one.example"}, self.tmp.name)
        self.assertIsNone(r["site"])

    def test_cap_exceeded_returns_429_with_cors_and_healthz_still_ok(self):
        deploy.record_spend(0.6, "test")  # default daily cap is 0.50
        r = run_app({"APP_ENV": "demo"}, self.tmp.name)
        self.assertEqual(r["ask_status"], 429)
        self.assertIn("daily limit", json.loads(r["ask_body"])["detail"])
        self.assertEqual(r["ask_cors"], "https://spanfold.com")
        self.assertFalse(any(w in r["ask_body"].lower() for w in PROVIDER_WORDS))
        self.assertEqual(r["healthz_after"], 200)

    def test_monthly_cap(self):
        os.environ["DAILY_SPEND_CAP_USD"] = "100"
        os.environ["MONTHLY_SPEND_CAP_USD"] = "1"
        deploy.record_spend(1.2, "test")
        self.assertEqual(deploy.over_cap(), "monthly")

    def test_provider_reply_usage_is_counted_then_blocks(self):
        from app.llm import client

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 2_000_000, "completion_tokens": 1_000_000},
                }

        class Http:
            TimeoutException = TimeoutError

            class Client:
                def __init__(self, **kw):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def post(self, url, json=None, headers=None):
                    return Resp()

        llm = SimpleNamespace(
            provider="openai", base_url="https://provider.test", api_key="test-key-not-real", model="test-model",
            top_p=1.0, reasoning_effort=None,
        )
        os.environ["DAILY_SPEND_CAP_USD"] = "0.0000001"
        with mock.patch.object(client, "_get_httpx", return_value=Http):
            out = client._provider_generate(
                llm, "sys", "user", json_mode=False, temperature=0.0, max_tokens=50, timeout_s=5
            )
        self.assertTrue(out["success"], out)
        day, _ = deploy.totals()
        self.assertGreater(day, 0)  # counted from the reply's own usage (or the estimate if the model has no price)
        with mock.patch.object(client, "_get_httpx", return_value=Http):
            with self.assertRaises(deploy.DemoLimitReached):
                client._provider_generate(
                    llm, "sys", "user", json_mode=False, temperature=0.0, max_tokens=50, timeout_s=5
                )

    def test_broken_ledger_fails_open(self):
        Path(self.tmp.name, "afile").write_text("x")
        os.environ["SPEND_DB_PATH"] = str(Path(self.tmp.name, "afile", "spend.sqlite"))
        self.assertIsNone(deploy.over_cap())
        self.assertEqual(deploy.record_spend(0.1), 0.1)

    def test_keepalive_runs_a_real_query_and_fails_loudly(self):
        sys.path.insert(0, str(BACKEND / "scripts"))
        import keepalive

        calls = []

        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, stmt):
                calls.append(str(stmt))
                return SimpleNamespace(scalar_one=lambda: 7)

        good = SimpleNamespace(connect=lambda: Conn())
        self.assertEqual(keepalive.run(good), 0)
        self.assertTrue(any("sources" in c.lower() for c in calls))

        def boom():
            raise RuntimeError("db down")

        self.assertEqual(keepalive.run(SimpleNamespace(connect=boom)), 1)


if __name__ == "__main__":
    unittest.main()
