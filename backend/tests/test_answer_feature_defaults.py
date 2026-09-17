"""Default activation is independent of local secrets and remains reversible."""

import unittest
from unittest.mock import patch

from app.core.config import Settings, settings
from app.core_rag.context_selection import compound_question
from app.llm.prompts import SYSTEM_PROMPT, effective_system_prompt


class AnswerFeatureDefaultsTests(unittest.TestCase):
    def test_declared_defaults_are_enabled_without_loading_local_environment(self):
        for name in (
            "ANSWER_CONTEXT_SELECTION_ENABLED",
            "ANSWER_PROMPT_CANDIDATE",
            "ANSWER_NUMERIC_CLAIM_REPAIR_ENABLED",
        ):
            with self.subTest(name=name):
                self.assertIs(Settings.model_fields[name].default, True)

    def test_explicit_configuration_keeps_independent_rollback(self):
        config = Settings(
            _env_file=None,
            ANSWER_CONTEXT_SELECTION_ENABLED=False,
            ANSWER_PROMPT_CANDIDATE=False,
            ANSWER_NUMERIC_CLAIM_REPAIR_ENABLED=False,
        )
        self.assertFalse(config.ANSWER_CONTEXT_SELECTION_ENABLED)
        self.assertFalse(config.ANSWER_PROMPT_CANDIDATE)
        self.assertFalse(config.ANSWER_NUMERIC_CLAIM_REPAIR_ENABLED)

    def test_prompt_rollback_and_compound_routing_remain_available(self):
        with patch.object(settings, "ANSWER_PROMPT_CANDIDATE", False):
            self.assertEqual(effective_system_prompt(), SYSTEM_PROMPT)
        with patch.object(settings, "ANSWER_PROMPT_CANDIDATE", True):
            self.assertIn("governing trigger", effective_system_prompt())
        self.assertTrue(compound_question("Which sections jointly govern this process?"))
        self.assertFalse(compound_question("What is the meal allowance?"))
