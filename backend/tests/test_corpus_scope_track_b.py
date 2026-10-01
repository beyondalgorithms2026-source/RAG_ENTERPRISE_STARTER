"""Per-request corpus scope (Track B). Offline: no database or provider is contacted."""

import unittest
from unittest import mock

from pydantic import ValidationError

import app.api.corpus as corpus_api
import app.core_rag.answering as answering
import app.core_rag.retrieval as retrieval
from app.auth.access_strategy import _source_authorization_sql, source_access_sql
from app.core.config import settings
from app.core_rag.corpus_scope import (
    active_corpora,
    cache_corpus_scope,
    corpus_scope,
    normalize_corpora,
)
from app.core_rag.retrieval import SearchFilters, SearchRequest
from app.main import app
from fastapi.testclient import TestClient


class CorpusScopeTests(unittest.TestCase):
    def setUp(self):
        self.original_allowed = settings.ALLOWED_CORPORA
        self.original_strategy = settings.ACCESS_STRATEGY
        settings.ACCESS_STRATEGY = "document_acl_with_time_bound_grants"

    def tearDown(self):
        settings.ALLOWED_CORPORA = self.original_allowed
        settings.ACCESS_STRATEGY = self.original_strategy

    def test_unscoped_sql_is_exactly_the_authorization_clause(self):
        scoped_params: dict = {}
        plain_params: dict = {}
        self.assertEqual(
            source_access_sql(params=scoped_params),
            _source_authorization_sql(params=plain_params),
        )
        self.assertEqual(scoped_params, plain_params)
        self.assertIsNone(cache_corpus_scope())

    def test_scope_is_anded_onto_authorization(self):
        params: dict = {}
        with corpus_scope(["western_northline"]):
            sql = source_access_sql(params=params, source_alias="src")
            self.assertEqual(cache_corpus_scope(), {"corpora": ["western_northline"]})
        self.assertIn("src.sensitivity_label = 'public'", sql)
        self.assertIn(" AND COALESCE(src.source_metadata_json ->> 'corpus', '') = ANY(", sql)
        self.assertEqual(params["access_corpus_scope"], ["western_northline"])
        self.assertIsNone(active_corpora())

    def test_scope_resets_after_nested_use(self):
        with corpus_scope(["a"]):
            with corpus_scope(None):
                self.assertIsNone(active_corpora())
            self.assertEqual(active_corpora(), ("a",))
        self.assertIsNone(active_corpora())

    def test_normalization_and_allowlist(self):
        self.assertIsNone(normalize_corpora(None))
        self.assertEqual(normalize_corpora([" b ", "a", "b"]), ("a", "b"))
        with self.assertRaises(ValueError):
            normalize_corpora([])
        with self.assertRaises(ValueError):
            normalize_corpora([" "])
        settings.ALLOWED_CORPORA = "northwind-public-demo, western_northline"
        self.assertEqual(normalize_corpora(["western_northline"]), ("western_northline",))
        with self.assertRaises(ValueError):
            normalize_corpora(["someone-else"])

    def test_search_filters_reject_unknown_corpus(self):
        settings.ALLOWED_CORPORA = "western_northline"
        self.assertEqual(SearchFilters(corpus=["western_northline"]).corpus, ["western_northline"])
        with self.assertRaises(ValidationError):
            SearchFilters(corpus=["northwind-public-demo"])

    def test_perform_search_runs_inside_the_requested_scope(self):
        seen = []
        with mock.patch.object(
            retrieval, "_perform_search_scoped", side_effect=lambda request: seen.append(active_corpora())
        ):
            retrieval.perform_search(
                SearchRequest(question="q", filters=SearchFilters(corpus=["western_northline"]))
            )
            retrieval.perform_search(SearchRequest(question="q"))
        self.assertEqual(seen, [("western_northline",), None])

    def test_perform_ask_runs_inside_the_requested_scope(self):
        seen = []
        with mock.patch.object(
            answering, "_perform_ask_scoped", side_effect=lambda *a, **k: seen.append(active_corpora())
        ):
            answering.perform_ask(
                answering.AskRequest(question="q", filters={"corpus": ["western_northline"]})
            )
        self.assertEqual(seen, [("western_northline",)])

    def test_corpus_listing_accepts_and_validates_scope(self):
        settings.ALLOWED_CORPORA = "western_northline"
        seen = []
        client = TestClient(app)
        with mock.patch.object(
            corpus_api, "list_accessible_sources", side_effect=lambda: seen.append(active_corpora()) or []
        ), mock.patch.object(corpus_api, "_enriched_ingestion_jobs", return_value=[]):
            self.assertEqual(client.get("/corpus?corpus=western_northline").status_code, 200)
            self.assertEqual(client.get("/corpus").status_code, 200)
            self.assertEqual(client.get("/corpus?corpus=unknown").status_code, 422)
        self.assertEqual(seen, [("western_northline",), None])


if __name__ == "__main__":
    unittest.main()
