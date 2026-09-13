from __future__ import annotations

import json
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "corpus"
if str(CORPUS_DIR) not in sys.path:
    sys.path.insert(0, str(CORPUS_DIR))

from app.seed.public_demo import _chunks_for_document  # noqa: E402
from generate_corpus import check, main, write_corpus  # noqa: E402
from library import DOCUMENTS  # noqa: E402


def _manual():
    return next(item for item in DOCUMENTS if item.slug == "northwind-operations-manual-v3.2")


class PublicDemoCorpusP16Tests(unittest.TestCase):
    def test_manual_is_public_synthetic_and_corpus_has_28_sources(self):
        manual = _manual()
        self.assertEqual(len(DOCUMENTS), 28)
        self.assertEqual(manual.classification, "public")
        self.assertEqual(manual.parser_route, "production_markdown")
        self.assertIn("Effective date: 1 September 2026", manual.body)
        self.assertIn("Classification: Public — synthetic demonstration content", manual.body)
        self.assertIn("contains no real company, employee, customer, or private data", manual.body)
        self.assertNotIn("<br>", manual.body.lower())
        self.assertEqual(check(), [])

    def test_manifest_pins_manual_content_hash_and_parser_route(self):
        with tempfile.TemporaryDirectory(prefix="b004-p16-") as directory:
            output = Path(directory)
            result = write_corpus(output, DOCUMENTS)
            manifest = json.loads((output / "corpus-manifest.json").read_text(encoding="utf-8"))
            manual = next(
                item
                for item in manifest["documents"]
                if item["slug"] == "northwind-operations-manual-v3.2"
            )
            self.assertEqual(result["count"], 28)
            self.assertEqual(manifest["document_count"], 28)
            self.assertEqual(manual["parser_route"], "production_markdown")
            self.assertEqual(len(manual["content_sha256"]), 64)
            self.assertTrue(
                (output / manual["filename"])
                .read_text(encoding="utf-8")
                .startswith("# Northwind Logistics Operations Manual")
            )

    def test_legacy_phase_materializes_original_27_sources(self):
        with tempfile.TemporaryDirectory(prefix="b004-p16-legacy-") as directory:
            with patch.object(
                sys, "argv", ["generate_corpus.py", "--out", directory, "--legacy-only"]
            ):
                self.assertEqual(main(), 0)
            manifest = json.loads(
                (Path(directory) / "corpus-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["document_count"], 27)
            manifest_bytes = (Path(directory) / "corpus-manifest.json").read_bytes()
            self.assertEqual(
                sha256(manifest_bytes).hexdigest(),
                "5760b4d7662b395d02b83043975a9037d0d8ba140f45fdcf3138f5d66dc6fdfe",
            )
            self.assertTrue(
                all(
                    "content_sha256" not in item
                    and "parser_route" not in item
                    and "source_file" not in item
                    for item in manifest["documents"]
                )
            )
            self.assertNotIn(
                "northwind-operations-manual-v3.2",
                {item["slug"] for item in manifest["documents"]},
            )

    def test_manual_uses_production_markdown_parser_and_chunker(self):
        manual = _manual()
        chunks = _chunks_for_document(
            content=manual.render(),
            file_name=manual.filename(),
            parser_route=manual.parser_route,
        )
        self.assertGreaterEqual(len(chunks), 40)
        self.assertTrue(
            all(chunk["provenance_json"]["parser"] == "markdown_lightweight" for chunk in chunks)
        )
        self.assertTrue(
            all(chunk["provenance_json"]["corpus_policy"] == "default" for chunk in chunks)
        )
        self.assertTrue(
            any(
                chunk["locator_json"].get("section") == "2.1 Delegation of Authority"
                for chunk in chunks
            )
        )
        self.assertTrue(any("€18,750" in chunk["chunk_text"] for chunk in chunks))

    def test_unknown_parser_route_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported public-demo parser route"):
            _chunks_for_document(content="# A\n\nBody", file_name="a.md", parser_route="shortcut")
