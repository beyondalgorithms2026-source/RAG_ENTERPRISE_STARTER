from tests.smoke_test_base import *


class SourceDownloadAR20Tests(SmokeTestBase):
    """Console source download with a size-warning guard so an operator can read
    a file before acting."""

    def _admin_client(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        run_migrations()
        client = TestClient(app)
        original_auth = settings.AUTH_ENABLED
        original_fn = main_module.authenticate_request
        settings.AUTH_ENABLED = True
        main_module.authenticate_request = lambda request: AuthenticatedUser(user_id="ar20", email="ar20@example.com", roles=["admin"], groups=["ops"])
        self.addCleanup(lambda: (setattr(settings, "AUTH_ENABLED", original_auth), setattr(main_module, "authenticate_request", original_fn)))
        return client

    def _seed_source(self, *, storage_path: str, file_name: str, size: int, source_type: str = "txt"):
        with engine.begin() as conn:
            sid = conn.execute(
                text(
                    """
                    INSERT INTO sources (file_name, storage_path, source_type, sensitivity_label, hash_sha256,
                        file_size_bytes, ingestion_status, enrichment_status, source_metadata_json)
                    VALUES (:f, :p, :st, 'public', :h, :sz, 'embedded', 'not_started', '{}'::jsonb)
                    RETURNING id
                    """
                ),
                {"f": file_name, "p": storage_path, "st": source_type, "h": (file_name + "ar20") * 4, "sz": size},
            ).scalar_one()
        self.addCleanup(lambda: self._delete_source(sid))
        return sid

    def _delete_source(self, sid):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM sources WHERE id = :id"), {"id": sid})

    def test_download_info_flags_large_file(self):
        client = self._admin_client()
        small = self._seed_source(storage_path=f"tests/ar20-small-{uuid4().hex[:8]}.txt", file_name="small.txt", size=1024)
        big = self._seed_source(storage_path=f"tests/ar20-big-{uuid4().hex[:8]}.pdf", file_name="big.pdf", size=200 * 1024 * 1024, source_type="pdf")
        info_small = client.get(f"/admin/sources/{small}/download-info", headers={"Authorization": "Bearer t"}).json()
        info_big = client.get(f"/admin/sources/{big}/download-info", headers={"Authorization": "Bearer t"}).json()
        self.assertFalse(info_small["too_large_warning"])
        self.assertTrue(info_big["too_large_warning"])
        self.assertEqual(info_big["warn_threshold_bytes"], 25 * 1024 * 1024)

    def test_download_streams_existing_repo_file(self):
        client = self._admin_client()
        sid = self._seed_source(storage_path="README.md", file_name="README.md", size=1024, source_type="txt")
        resp = client.get(f"/admin/sources/{sid}/download", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertTrue(len(resp.content) > 0)

    def test_download_missing_file_is_404(self):
        client = self._admin_client()
        sid = self._seed_source(storage_path="does/not/exist.pdf", file_name="x.pdf", size=10, source_type="pdf")
        resp = client.get(f"/admin/sources/{sid}/download", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"]["error"], "source_file_not_found")

    def test_download_unknown_source_is_404(self):
        client = self._admin_client()
        resp = client.get("/admin/sources/99999999/download", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 404)
