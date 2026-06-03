import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
STATUS = REPO_ROOT / "STATUS.md"
QUICKSTART = REPO_ROOT / "docs" / "01_quickstart.md"
NAV_BLUEPRINT = REPO_ROOT / "docs" / "04_repo_navigation_blueprint.md"
HISTORY_ARCHIVE = REPO_ROOT / "docs" / "project_state" / "milestone_history_archive.md"
SAFE_EXTENSION = REPO_ROOT / "docs" / "runbooks" / "SAFE_EXTENSION_BLUEPRINT.md"
MASTER_GUIDE = REPO_ROOT / "docs" / "master_guide.md"
SCENARIO_BLUEPRINT = REPO_ROOT / "docs" / "scenario_profiles_and_reuse_blueprint.md"


class ReaderClarityM32Tests(unittest.TestCase):
    def test_readme_is_canonical_entrypoint(self):
        content = README.read_text(encoding="utf-8")
        required = [
            "## Start Here",
            "What This Repo Is",
            "How To Run It",
            "Current Status",
            "Canonical Paths",
            "docs/01_quickstart.md",
            "docs/04_repo_navigation_blueprint.md",
            "docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, content)

    def test_status_is_short_operational_snapshot_and_links_history(self):
        content = STATUS.read_text(encoding="utf-8")
        self.assertIn("Operational Snapshot", content)
        self.assertIn("Historical Detail", content)
        self.assertIn("docs/project_state/milestone_history_archive.md", content)
        self.assertNotIn("**M10 summary**", content)

    def test_history_archive_exists_and_preserves_milestone_lookup(self):
        content = HISTORY_ARCHIVE.read_text(encoding="utf-8")
        required = [
            "## Milestone Chronology",
            "Historical implementation detail now lives in milestone notes",
            "docs/milestones/m10_nextjs_enterprise_console_ui.md",
            "docs/milestones/m31_repository_hygiene_canonical_paths_and_safe_source_control_workflow.md",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, content)

    def test_repo_navigation_blueprint_exists_and_references_real_paths(self):
        content = NAV_BLUEPRINT.read_text(encoding="utf-8")
        required = [
            "backend/app/main.py",
            "web/app/",
            "docs/runbooks/LOCALHOST_DEV_RUNBOOK.md",
            "docs/project_state/milestone_history_archive.md",
            "frontend/",
            "docs/_master_docs/",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, content)

    def test_quickstart_and_safe_extension_docs_exist(self):
        self.assertTrue(QUICKSTART.exists())
        self.assertTrue(SAFE_EXTENSION.exists())
        quickstart = QUICKSTART.read_text(encoding="utf-8")
        extension = SAFE_EXTENSION.read_text(encoding="utf-8")
        self.assertIn("This is the canonical local run path", quickstart)
        self.assertIn("This is the canonical extension path", extension)

    def test_master_guide_and_scenario_blueprint_defer_to_canonical_path(self):
        master_content = MASTER_GUIDE.read_text(encoding="utf-8")
        scenario_content = SCENARIO_BLUEPRINT.read_text(encoding="utf-8")
        self.assertIn("not the canonical first stop", master_content)
        self.assertIn("docs/04_repo_navigation_blueprint.md", scenario_content)
        self.assertIn("docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md", scenario_content)


if __name__ == "__main__":
    unittest.main()
