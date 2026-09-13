import hashlib
import unittest
from pathlib import Path

from app.llm.prompt_registry import load_prompt, prompt_metadata
from app.llm.prompts import REPAIR_PROMPT, SECOND_PASS_PROMPT, SYSTEM_PROMPT


class PromptRegistryP13Tests(unittest.TestCase):
    def test_active_prompts_are_hash_verified_and_keep_legacy_constants(self):
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

    def test_registered_prompt_history_is_retained(self):
        prompt_root = Path(__file__).parents[1] / "app" / "llm" / "prompt_assets"
        for file_name in (
            "answer-v1.0.0.txt",
            "answer-v1.1.0.txt",
            "second-pass-v1.0.0.txt",
            "second-pass-v1.1.0.txt",
        ):
            self.assertTrue((prompt_root / file_name).is_file(), file_name)


if __name__ == "__main__":
    unittest.main()
