import json
import unittest
from pathlib import Path

from app.auth.admin_modules import ADMIN_MODULES, SCENARIO_ADMIN_MODULE_PRESETS


REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "scenarios"
RUNBOOKS_DIR = REPO_ROOT / "docs" / "runbooks"


EXPECTED_ENV = {
    "research_no_auth": {"AUTH_MODE": "none", "ACCESS_STRATEGY": "none", "SCENARIO_PROFILE": "research_no_auth"},
    "employee_wide_rag": {"AUTH_MODE": "dev", "ACCESS_STRATEGY": "employee_all", "SCENARIO_PROFILE": "employee_wide_rag"},
    "small_enterprise_corpus_acl": {"AUTH_MODE": "dev", "ACCESS_STRATEGY": "corpus_level", "SCENARIO_PROFILE": "small_enterprise_corpus_acl"},
    "enterprise_oidc_acl": {"AUTH_MODE": "oidc", "ACCESS_STRATEGY": "document_acl_with_time_bound_grants", "SCENARIO_PROFILE": "enterprise_oidc_acl"},
}


class ScenarioBuildPacksM30Tests(unittest.TestCase):
    def _env_map(self, scenario: str) -> dict[str, str]:
        env_file = SCENARIOS_DIR / scenario / "backend.env.example"
        values: dict[str, str] = {}
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
        return values

    def test_all_required_scenario_packs_exist(self):
        for scenario in EXPECTED_ENV:
            with self.subTest(scenario=scenario):
                scenario_dir = SCENARIOS_DIR / scenario
                self.assertTrue(scenario_dir.exists())
                for filename in ("README.md", "validation.md", "backend.env.example", "web.env.example", "admin_modules.json"):
                    self.assertTrue((scenario_dir / filename).exists(), f"{scenario}/{filename}")

    def test_scenario_env_samples_match_expected_auth_and_access_strategy(self):
        for scenario, expected in EXPECTED_ENV.items():
            env = self._env_map(scenario)
            for key, value in expected.items():
                with self.subTest(scenario=scenario, key=key):
                    self.assertEqual(env.get(key), value)

    def test_scenario_admin_module_inventory_matches_backend_presets(self):
        all_modules = set(ADMIN_MODULES)
        for scenario in EXPECTED_ENV:
            with self.subTest(scenario=scenario):
                payload = json.loads((SCENARIOS_DIR / scenario / "admin_modules.json").read_text(encoding="utf-8"))
                enabled = set(payload["enabled_modules"])
                disabled = set(payload["disabled_modules"])
                self.assertEqual(enabled, SCENARIO_ADMIN_MODULE_PRESETS[scenario])
                self.assertEqual(disabled, all_modules - enabled)

    def test_reuse_runbooks_exist(self):
        required = [
            "CREATE_SUBSET_PRODUCT_FROM_STARTER.md",
            "REPLACE_AUTH_IMPLEMENTATION.md",
            "REPLACE_ACCESS_STRATEGY.md",
            "DISABLE_ADVANCED_ADMIN_MODULES.md",
            "POC_TO_SECURED_INTERNAL_PILOT.md",
            "SECURED_PILOT_TO_PRODUCTION_LIKE_DEPLOYMENT.md",
            "REUSE_ACCEPTANCE_REPORT_TEMPLATE.md",
        ]
        for filename in required:
            with self.subTest(filename=filename):
                self.assertTrue((RUNBOOKS_DIR / filename).exists())


if __name__ == "__main__":
    unittest.main()
