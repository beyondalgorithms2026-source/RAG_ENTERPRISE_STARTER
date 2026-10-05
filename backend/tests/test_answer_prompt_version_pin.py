import unittest
from unittest import mock

from app.core.config import settings
from app.llm import prompt_registry, prompts
from app.llm.prompt_registry import load_prompt, load_prompt_version


class AnswerPromptVersionPinTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.multiple(
            settings, ANSWER_PROMPT_VERSION="", ANSWER_PROMPT_CANDIDATE=True
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_is_unchanged_candidate_prompt(self):
        self.assertEqual(
            prompts.effective_system_prompt(), load_prompt("starter_answer", candidate=True)
        )
        self.assertEqual(prompt_registry.prompt_metadata()["starter_answer"]["version"], "1.2.2")

    def test_pin_selects_hash_verified_history_version(self):
        settings.ANSWER_PROMPT_VERSION = "1.2.3"
        text = prompts.effective_system_prompt()
        self.assertEqual(text, load_prompt_version("starter_answer", "1.2.3"))
        self.assertIn("count the source items", text)
        self.assertIn('Never refer to "the specified"', text)
        self.assertEqual(prompt_registry.prompt_metadata()["starter_answer"]["version"], "1.2.3")

    def test_pin_wins_over_candidate_flag(self):
        settings.ANSWER_PROMPT_VERSION = "1.2.3"
        settings.ANSWER_PROMPT_CANDIDATE = False
        self.assertIn("count the source items", prompts.effective_system_prompt())

    def test_1_2_3_only_adds_rules_to_1_2_2(self):
        old = load_prompt_version("starter_answer", "1.2.2").splitlines()
        new = load_prompt_version("starter_answer", "1.2.3").splitlines()
        self.assertEqual([line for line in new if line in old], old)
        self.assertEqual(len(new) - len(old), 3)

    def test_unknown_pin_fails_loudly(self):
        settings.ANSWER_PROMPT_VERSION = "9.9.9"
        with self.assertRaisesRegex(RuntimeError, "9.9.9"):
            prompts.effective_system_prompt()

    def test_cache_scope_changes_with_prompt_selection(self):
        from app.db import repo_semantic_cache as cache

        identities = []
        for version, candidate in (("", True), ("", False), ("1.2.3", True)):
            settings.ANSWER_PROMPT_VERSION = version
            settings.ANSWER_PROMPT_CANDIDATE = candidate
            identities.append(cache.answer_prompt_identity())
        self.assertEqual(identities, ["candidate", "current", "version:1.2.3"])


if __name__ == "__main__":
    unittest.main()
