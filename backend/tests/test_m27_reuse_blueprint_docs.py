import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = REPO_ROOT / "docs" / "scenario_profiles_and_reuse_blueprint.md"
DIAGRAM = REPO_ROOT / "docs" / "diagrams" / "m27_module_selection_map.mmd"


class M27ReuseBlueprintDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blueprint = BLUEPRINT.read_text(encoding="utf-8")
        cls.diagram = DIAGRAM.read_text(encoding="utf-8")

    def test_blueprint_and_diagram_exist(self):
        self.assertTrue(BLUEPRINT.exists())
        self.assertTrue(DIAGRAM.exists())
        self.assertIn("flowchart LR", self.diagram)

    def test_required_scenarios_are_documented(self):
        required = [
            "Small Enterprise Login/Password With Corpus-Level Access",
            "Employee-Wide RAG With Equal Access",
            "No-Auth Research/Admin RAG For Trusted Environments",
            "Full Enterprise OIDC + ACL + Governance Mode",
        ]
        for heading in required:
            with self.subTest(heading=heading):
                self.assertIn(heading, self.blueprint)

    def test_each_scenario_includes_required_checklist_terms(self):
        required_terms = [
            "Keep:",
            "Disable:",
            "Replace:",
            "Required env:",
            "Security assumptions:",
            "Minimum test pack:",
            "Expected admin UI:",
        ]
        for term in required_terms:
            with self.subTest(term=term):
                self.assertGreaterEqual(self.blueprint.count(term), 4)

    def test_security_and_future_boundaries_are_explicit(self):
        required_text = [
            "SQL retrieval queries",
            "No sensitive data",
            "M28",
            "M29",
            "M30",
            "does not introduce new access-control code",
        ]
        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, self.blueprint)

    def test_referenced_repo_paths_exist(self):
        paths = [
            "backend/app/api/upload.py",
            "backend/app/connectors",
            "backend/app/ingestion",
            "backend/app/adapters",
            "backend/app/core_rag",
            "backend/app/auth",
            "backend/app/db/repo_acl.py",
            "web/components/chat-workspace.tsx",
            "web/components/admin-panels.tsx",
            "backend/app/eval",
            "backend/app/db/repo_admin_audit.py",
            "docs/diagrams/m27_module_selection_map.mmd",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((REPO_ROOT / path).exists(), path)


if __name__ == "__main__":
    unittest.main()
