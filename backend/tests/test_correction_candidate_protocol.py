import unittest

from app.eval.correction_candidate import require_isolated_database, sanitize_report


class CorrectionCandidateProtocolTests(unittest.TestCase):
    def test_shared_databases_cannot_be_migrated_or_seeded(self):
        for url in [
            "postgresql://user:password@db.supabase.co/b004_eval_test",
            "postgresql://user:password@localhost/production",
            "",
        ]:
            with self.assertRaises(ValueError):
                require_isolated_database(url)
        require_isolated_database("postgresql://user:password@127.0.0.1/b004_eval_test")

    def test_report_redacts_secrets_but_retains_measured_usage(self):
        clean = sanitize_report(
            {
                "api_key": "secret",
                "child": {"LLM_API_KEY": "secret", "prompt_tokens": 123},
                "answer": "sk-testfake12345 /Users/Work/private.env",
                "prompt": "raw untrusted prompt",
            }
        )
        self.assertNotIn("api_key", clean)
        self.assertNotIn("LLM_API_KEY", clean["child"])
        self.assertEqual(clean["child"]["prompt_tokens"], 123)
        self.assertEqual(clean["answer"], "[redacted] [path-redacted]")
        self.assertNotIn("prompt", clean)
