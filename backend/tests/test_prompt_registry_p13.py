import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.llm.prompt_registry import load_prompt, prompt_metadata
from app.llm.prompts import REPAIR_PROMPT, SECOND_PASS_PROMPT, SYSTEM_PROMPT


class PromptRegistryP13Tests(unittest.TestCase):
    def test_active_prompts_are_hash_verified_and_keep_legacy_constants(self):
        with (
            patch.object(settings, "ANSWER_PROMPT_CANDIDATE", False),
            patch.object(settings, "ANSWER_NUMERIC_CLAIM_REPAIR_ENABLED", False),
        ):
            metadata = prompt_metadata()
        prompts = {
            "starter_answer": SYSTEM_PROMPT,
            "starter_json_repair": REPAIR_PROMPT,
            "starter_second_pass": SECOND_PASS_PROMPT,
        }
        expected_versions = {
            "starter_answer": "1.1.0",
            "starter_json_repair": "1.0.0",
            "starter_second_pass": "1.1.0",
        }

        self.assertEqual(set(metadata), set(prompts))
        for prompt_id, prompt in prompts.items():
            self.assertEqual(prompt, load_prompt(prompt_id))
            self.assertEqual(metadata[prompt_id]["version"], expected_versions[prompt_id])
            self.assertEqual(
                metadata[prompt_id]["sha256"], hashlib.sha256(prompt.encode()).hexdigest()
            )

    def test_enabled_metadata_identifies_effective_answer_and_numeric_assets(self):
        with (
            patch.object(settings, "ANSWER_PROMPT_CANDIDATE", True),
            patch.object(settings, "ANSWER_NUMERIC_CLAIM_REPAIR_ENABLED", True),
        ):
            metadata = prompt_metadata()
        for prompt_id, version in (
            ("starter_answer", "1.2.2"),
            ("starter_numeric_claims", "1.1.0"),
        ):
            prompt = load_prompt(prompt_id, candidate=True)
            self.assertEqual(metadata[prompt_id]["version"], version)
            self.assertEqual(
                metadata[prompt_id]["sha256"], hashlib.sha256(prompt.encode()).hexdigest()
            )

    def test_registered_prompt_history_is_retained(self):
        prompt_root = Path(__file__).parents[1] / "app" / "llm" / "prompt_assets"
        for file_name in (
            "answer-v1.0.0.txt",
            "answer-v1.1.0.txt",
            "second-pass-v1.0.0.txt",
            "second-pass-v1.1.0.txt",
        ):
            self.assertTrue((prompt_root / file_name).is_file(), file_name)
        registry = json.loads((prompt_root / "registry.json").read_text())
        history = registry["history"]["starter_answer"]
        self.assertEqual(set(history), {"1.2.1", "1.2.2"})
        for entry in history.values():
            content = (prompt_root / entry["file"]).read_text().rstrip("\n")
            self.assertEqual(hashlib.sha256(content.encode()).hexdigest(), entry["sha256"])


if __name__ == "__main__":
    unittest.main()
