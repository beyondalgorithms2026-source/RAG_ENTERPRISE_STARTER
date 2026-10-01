"""Western (Northline) corpus seeder validation (Track B). Offline: no database or API."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app.seed.western_corpus as western
from app.core.config import settings
from app.seed.western_corpus import (
    WesternCorpusError,
    auto_seed_western_corpus,
    dry_run,
    load_documents,
    wipe,
)

MANIFEST_HEADER = "id,filename,doc_type,jurisdiction,classification,word_count,gold_use\n"


def _doc(doc_id: str, classification: str = "Internal", body: str = "Policy text.") -> str:
    return (
        "SYNTHETIC\n\n---\n"
        f"id: {doc_id}\ntitle: {doc_id} Title\ndoc_type: policy\nclassification: {classification}\n"
        "---\n\n"
        f"# {doc_id} Title\n\n## Scope\n\n{body}\n"
    )


class WesternCorpusFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.corpus_dir = root / "corpus"
        self.corpus_dir.mkdir()
        self.manifest = root / "MANIFEST.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, docs: dict[str, str], manifest_rows: list[str]):
        for name, content in docs.items():
            (self.corpus_dir / name).write_text(content, encoding="utf-8")
        self.manifest.write_text(MANIFEST_HEADER + "".join(manifest_rows), encoding="utf-8")

    def _load(self):
        return load_documents(self.corpus_dir, self.manifest)

    def test_valid_pack_maps_classification_and_strips_front_matter(self):
        self._write(
            {
                "NL-HR-A.md": _doc("NL-HR-A"),
                "NL-OPS-SOP-INCIDENT.md": _doc("NL-OPS-SOP-INCIDENT", "Confidential"),
                "NL-SEC-DATA-RETENTION-2026.md": _doc(
                    "NL-SEC-DATA-RETENTION-2026", "Confidential"
                ),
            },
            [
                "NL-HR-A,NL-HR-A.md,policy,group,Internal,10,policy_qa\n",
                "NL-OPS-SOP-INCIDENT,NL-OPS-SOP-INCIDENT.md,sop,group,Confidential,10,sop_steps\n",
                "NL-SEC-DATA-RETENTION-2026,NL-SEC-DATA-RETENTION-2026.md,policy,group,Confidential,10,x\n",
                "NL-CORPUS-NOTES-2026,CORPUS_NOTES.md,appendix,group,Internal,10,x\n",
            ],
        )
        documents = {document.doc_id: document for document in self._load()}
        self.assertEqual(
            set(documents), {"NL-HR-A", "NL-OPS-SOP-INCIDENT", "NL-SEC-DATA-RETENTION-2026"}
        )
        self.assertEqual(documents["NL-HR-A"].classification, "public")
        self.assertEqual(documents["NL-OPS-SOP-INCIDENT"].classification, "restricted")
        self.assertEqual(documents["NL-SEC-DATA-RETENTION-2026"].classification, "public")
        self.assertEqual(documents["NL-HR-A"].owner_group, "people-operations")
        self.assertEqual(documents["NL-HR-A"].storage_path, "corpus/western/NL-HR-A.md")
        self.assertEqual(documents["NL-HR-A"].title, "NL-HR-A Title")
        indexed = documents["NL-HR-A"].indexed_text
        self.assertTrue(indexed.startswith("# NL-HR-A Title"))
        self.assertNotIn("classification:", indexed)
        self.assertNotIn("SYNTHETIC", indexed)
        self.assertIn("SYNTHETIC", documents["NL-HR-A"].content)

        report = dry_run(list(documents.values()))
        self.assertEqual(report["documents"], 3)
        self.assertEqual(report["classification_counts"], {"public": 2, "restricted": 1})
        self.assertGreater(report["chunks"], 0)

    def _assert_rejected(self, docs, rows, fragment):
        self._write(docs, rows)
        with self.assertRaises(WesternCorpusError) as caught:
            self._load()
        self.assertIn(fragment, str(caught.exception))

    def test_missing_file_is_rejected(self):
        self._assert_rejected(
            {}, ["NL-HR-A,NL-HR-A.md,policy,group,Internal,1,x\n"], "file not found"
        )

    def test_unlisted_file_is_rejected(self):
        self._assert_rejected(
            {"NL-HR-A.md": _doc("NL-HR-A"), "NL-HR-B.md": _doc("NL-HR-B")},
            ["NL-HR-A,NL-HR-A.md,policy,group,Internal,1,x\n"],
            "NL-HR-B.md: present in corpus/western but not in the manifest",
        )

    def test_readme_is_documentation_not_corpus(self):
        self._write(
            {"NL-HR-A.md": _doc("NL-HR-A"), "README.md": "# About this corpus\n"},
            ["NL-HR-A,NL-HR-A.md,policy,group,Internal,1,x\n"],
        )
        self.assertEqual([document.doc_id for document in self._load()], ["NL-HR-A"])

    def test_unknown_classification_is_rejected(self):
        self._assert_rejected(
            {"NL-HR-A.md": _doc("NL-HR-A", "Secret")},
            ["NL-HR-A,NL-HR-A.md,policy,group,Secret,1,x\n"],
            "unknown classification",
        )

    def test_gst_india_content_is_rejected(self):
        self._assert_rejected(
            {"NL-FIN-A.md": _doc("NL-FIN-A", body="Charge GST at 18% on invoices.")},
            ["NL-FIN-A,NL-FIN-A.md,policy,group,Internal,1,x\n"],
            "GST/India guard",
        )

    def test_front_matter_disagreement_is_rejected(self):
        self._assert_rejected(
            {"NL-HR-A.md": _doc("NL-HR-A", "Confidential")},
            ["NL-HR-A,NL-HR-A.md,policy,group,Internal,1,x\n"],
            "disagrees with manifest",
        )

    def test_duplicate_id_and_path_traversal_are_rejected(self):
        self._assert_rejected(
            {"NL-HR-A.md": _doc("NL-HR-A")},
            [
                "NL-HR-A,NL-HR-A.md,policy,group,Internal,1,x\n",
                "NL-HR-A,NL-HR-A.md,policy,group,Internal,1,x\n",
                "NL-HR-B,../NL-HR-B.md,policy,group,Internal,1,x\n",
            ],
            "duplicate id NL-HR-A",
        )


class WesternCorpusSafetyTests(unittest.TestCase):
    def test_received_corpus_validates(self):
        documents = load_documents()
        ids = {document.doc_id for document in documents}
        self.assertNotIn("NL-CORPUS-NOTES-2026", ids)
        restricted = {d.doc_id for d in documents if d.classification == "restricted"}
        self.assertEqual(restricted, {"NL-OPS-SOP-INCIDENT"})
        poison = next(d for d in documents if d.doc_id == "NL-TEST-POISON-DOC")
        self.assertTrue(poison.test_fixture)

    def test_wipe_requires_exact_confirmation(self):
        with self.assertRaises(WesternCorpusError):
            wipe(confirm="")
        with self.assertRaises(WesternCorpusError):
            wipe(confirm="public_demo")

    def test_autoseed_is_off_by_default_and_never_fatal(self):
        original = settings.WESTERN_CORPUS_AUTOSEED
        try:
            settings.WESTERN_CORPUS_AUTOSEED = False
            self.assertIsNone(auto_seed_western_corpus())
            settings.WESTERN_CORPUS_AUTOSEED = True
            with (
                mock.patch.object(
                    western, "load_documents", side_effect=WesternCorpusError("bad drop")
                ),
                mock.patch.object(western, "log_event") as log_event,
            ):
                self.assertIsNone(auto_seed_western_corpus())
            self.assertEqual(log_event.call_args.args[0], "western_corpus.autoseed_failed")
        finally:
            settings.WESTERN_CORPUS_AUTOSEED = original


if __name__ == "__main__":
    unittest.main()
