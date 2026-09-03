import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
GITIGNORE = REPO_ROOT / ".gitignore"
WORKFLOW = REPO_ROOT / "docs" / "runbooks" / "SOURCE_CONTROL_WORKFLOW.md"
MASTER_README = REPO_ROOT / "docs" / "README_from_master.md"
MASTER_DOCS_README = REPO_ROOT / "docs" / "_master_docs" / "README.md"
TEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"


class RepoHygieneM31Tests(unittest.TestCase):
    def test_gitignore_covers_local_and_generated_noise(self):
        content = GITIGNORE.read_text(encoding="utf-8")
        required = [
            "backend/.env",
            "web/.env.local",
            "web/tsconfig.tsbuildinfo",
            "data/reports/*",
            "eval_report_*.json",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, content)

    def test_local_noise_files_are_not_tracked(self):
        tracked = subprocess.run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                "web/.env.local",
                "web/tsconfig.tsbuildinfo",
                "eval_report_retrieval.json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(tracked.returncode, 0, tracked.stdout + tracked.stderr)

    def test_eval_default_reports_write_to_data_reports(self):
        from app.eval import compare_eval, enriched_eval, retrieval_eval

        expected_parent = REPO_ROOT / "data" / "reports"
        self.assertEqual(retrieval_eval.DEFAULT_REPORT_FILE.parent, expected_parent)
        self.assertEqual(compare_eval.DEFAULT_REPORT_FILE.parent, expected_parent)
        self.assertEqual(enriched_eval.DEFAULT_REPORT_FILE.parent, expected_parent)

    def test_readme_declares_canonical_and_legacy_paths(self):
        content = README.read_text(encoding="utf-8")
        required = [
            "Active backend: `backend/`",
            "Active frontend: `web/`",
            "Legacy fallback UI: `frontend/`",
            "Generated local reports: `data/reports/`",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, content)

    def test_source_control_workflow_doc_exists_and_covers_expected_rules(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        required = [
            "## Branch naming",
            "## Tag naming",
            "## PR base expectations",
            "## Generated artifacts",
            "Default local eval outputs belong in `data/reports/`",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, content)

        workflow = TEST_WORKFLOW.read_text(encoding="utf-8")
        required_ci = [
            "push:",
            "pull_request:",
            'python-version: "3.12"',
            "pip install -r backend/requirements.txt",
            "python -m unittest discover -s tests",
            "make reader-clarity-check",
            "make repo-hygiene-check",
        ]
        for item in required_ci:
            with self.subTest(ci_item=item):
                self.assertIn(item, workflow)

    def test_imported_master_docs_are_marked_reference_only(self):
        master_readme = MASTER_README.read_text(encoding="utf-8")
        master_docs = MASTER_DOCS_README.read_text(encoding="utf-8")
        self.assertIn("not the canonical entrypoint", master_readme)
        self.assertIn("imported reference material", master_docs.lower())


if __name__ == "__main__":
    unittest.main()
