import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_COMPONENTS = ROOT / "web" / "components"


class AdminFormSystemAR19Tests(unittest.TestCase):
    def test_shared_form_primitives_exist(self):
        required = {
            "Field.tsx",
            "TextInput.tsx",
            "NumberInput.tsx",
            "Select.tsx",
            "Textarea.tsx",
            "Toggle.tsx",
            "FormActions.tsx",
            "useFieldState.ts",
        }
        self.assertEqual(required, {path.name for path in (WEB_COMPONENTS / "ui").iterdir()})

    def test_profiles_panel_is_composed_from_bounded_subpanels(self):
        composer = (WEB_COMPONENTS / "admin-profiles-panel.tsx").read_text()
        self.assertLessEqual(len(composer.splitlines()), 100)
        for name in ("TuningLabPanel", "EvalEvidencePanel", "QueryMiningPanel", "GovernanceOpsPanel"):
            self.assertIn(f"<{name} />", composer)
            panel = WEB_COMPONENTS / "admin-profiles" / f"{name}.tsx"
            self.assertLessEqual(len(panel.read_text().splitlines()), 400, name)

    def test_active_admin_panels_use_form_primitives(self):
        files = [
            "admin-panels.tsx",
            "access-admin-panel.tsx",
            "admin-actions-panel.tsx",
            "admin-cache-policy-panel.tsx",
            "admin-connectors-panel.tsx",
            "admin-cost-panel.tsx",
            "admin-embedding-panel.tsx",
            "admin-flywheel-panel.tsx",
            "admin-modules-panel.tsx",
            "admin-providers-panel.tsx",
        ]
        files.extend(str(path.relative_to(WEB_COMPONENTS)) for path in (WEB_COMPONENTS / "admin-profiles").glob("*.tsx"))
        raw_control = re.compile(r"<(?:input|select|textarea)\b")
        for relative in files:
            self.assertIsNone(raw_control.search((WEB_COMPONENTS / relative).read_text()), relative)

    def test_profile_endpoint_contract_is_preserved(self):
        endpoints = (WEB_COMPONENTS / "admin-profiles" / "endpoints.ts").read_text()
        expected = {
            "/admin/tuning/configurations",
            "/admin/tuning/history",
            "/admin/semantic-cache",
            "/admin/semantic-cache/clear",
            "/admin/query-mining",
            "/admin/query-mining/clusters/build",
            "/admin/governance",
            "/admin/retrieval/evidence",
            "/admin/runtime-settings",
            "/admin/tuning/drafts",
            "/admin/tuning/compare",
            "/admin/tuning/eval-runs",
            "/admin/tuning/promote",
            "/admin/tuning/rollback",
        }
        self.assertEqual(expected, set(re.findall(r'"(/admin/[^"]+)"', endpoints)))

    def test_legacy_duplicate_panels_are_removed(self):
        source = (WEB_COMPONENTS / "admin-panels.tsx").read_text()
        self.assertNotIn("export function ProfilesAdminPanel", source)
        self.assertNotIn("export function AccessAdminPanel", source)


if __name__ == "__main__":
    unittest.main()
