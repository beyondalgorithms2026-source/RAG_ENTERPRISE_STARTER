from __future__ import annotations

import unittest

from app.seed.cleanup_public_demo_duplicates import (
    _assert_apply_preconditions,
    build_cleanup_plan,
)


def _row(source_id: int, source_file: str, *, chunks: int, embedded: int) -> dict:
    return {
        "id": source_id,
        "file_name": source_file,
        "storage_path": f"/runtime-{source_id}/{source_file}",
        "hash_sha256": "abc",
        "sensitivity_label": "public",
        "ingestion_status": "embedded",
        "source_metadata_json": {"seed_pack": "public_demo", "source_file": source_file},
        "chunk_count": chunks,
        "embedded_chunk_count": embedded,
        "acl_count": 1,
    }


class PublicDemoCleanupTests(unittest.TestCase):
    def test_plan_keeps_complete_embedded_survivor_and_reports_dependencies(self):
        plan = build_cleanup_plan(
            [
                _row(1, "policy.md", chunks=2, embedded=0),
                _row(2, "policy.md", chunks=3, embedded=3),
                _row(3, "manual.md", chunks=4, embedded=4),
            ]
        )
        policy = next(
            group for group in plan["duplicate_groups"] if group["canonical_source"] == "policy.md"
        )
        self.assertEqual(policy["survivor_id"], 2)
        self.assertEqual(policy["remove_ids"], [1])
        self.assertEqual(policy["dependent_chunks_to_remove"], 2)
        self.assertEqual(plan["delete_ids"], [1])

    def test_apply_precondition_fails_closed_on_changed_hosted_counts(self):
        rows = [_row(index, f"public-{index}.md", chunks=1, embedded=1) for index in range(14)]
        plan = build_cleanup_plan(rows)
        with self.assertRaisesRegex(RuntimeError, "row precondition changed"):
            _assert_apply_preconditions(
                plan,
                expected_visible_rows=41,
                expected_visible_identities=14,
            )


if __name__ == "__main__":
    unittest.main()
