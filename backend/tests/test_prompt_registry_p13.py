import hashlib
import unittest

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

        self.assertEqual(set(metadata), set(prompts))
        for prompt_id, prompt in prompts.items():
            self.assertEqual(prompt, load_prompt(prompt_id))
            self.assertEqual(metadata[prompt_id]["version"], "1.0.0")
            self.assertEqual(
                metadata[prompt_id]["sha256"], hashlib.sha256(prompt.encode()).hexdigest()
            )


if __name__ == "__main__":
    unittest.main()
