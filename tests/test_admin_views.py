import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from admin_store import AdminStore
from image_proxy_server import create_app


class FakeService:
    def generate(self, body):
        return {"created": 123, "data": [{"b64_json": "ZmFrZQ=="}]}


class AdminViewsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self._temp_dir.name) / "admin.sqlite3"
        self.store = AdminStore(database_path)
        self.store.init_db()
        self.store.ensure_admin_user("admin", "secret-pass")
        runtime = SimpleNamespace(
            service=FakeService(),
            store=self.store,
            admin_settings=SimpleNamespace(
                username="admin",
                session_secret="test-session-secret",
            ),
        )
        self.app = create_app(runtime=runtime)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_admin_requires_login(self):
        response = self.client.get("/admin")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_login_and_manage_keys(self):
        self.store.bulk_add_api_keys("Alpha,key-1\nBravo,key-2\nCharlie,key-3")
        records = sorted(self.store.list_api_keys(), key=lambda item: item.api_key)
        first_key, second_key, third_key = records
        self.store.record_key_success(first_key.id)
        self.store.record_key_success(first_key.id)
        self.store.record_key_error(second_key.id, "rate limited")
        self.store.record_key_success(second_key.id)

        login_response = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret-pass"},
            follow_redirects=True,
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertIn("rate limited", login_response.get_data(as_text=True))
        self.assertIn("成功次数", login_response.get_data(as_text=True))
        self.assertIn("批量操作", login_response.get_data(as_text=True))

        filter_response = self.client.get(
            "/admin?filter=unused",
            follow_redirects=True,
        )

        self.assertEqual(filter_response.status_code, 200)
        filter_html = filter_response.get_data(as_text=True)
        self.assertIn("上游 Key 控制台", filter_html)
        self.assertIn("未成功调用", filter_html)
        self.assertIn("Charlie", filter_html)
        self.assertNotIn("Alpha", filter_html)
        self.assertNotIn("Bravo", filter_html)

        bulk_disable_response = self.client.post(
            "/admin/keys/bulk-action",
            data={"action": "disable", "key_ids": [str(first_key.id), str(second_key.id)]},
            follow_redirects=True,
        )
        bulk_enable_response = self.client.post(
            "/admin/keys/bulk-action",
            data={"action": "enable", "key_ids": [str(second_key.id)]},
            follow_redirects=True,
        )
        bulk_delete_response = self.client.post(
            "/admin/keys/bulk-action",
            data={"action": "delete", "key_ids": [str(third_key.id)]},
            follow_redirects=True,
        )

        self.assertEqual(bulk_disable_response.status_code, 200)
        self.assertEqual(bulk_enable_response.status_code, 200)
        self.assertEqual(bulk_delete_response.status_code, 200)
        final_records = sorted(self.store.list_api_keys(), key=lambda item: item.api_key)
        self.assertEqual([item.api_key for item in final_records], ["key-1", "key-2"])
        self.assertFalse(next(item for item in final_records if item.api_key == "key-1").is_enabled)
        self.assertTrue(next(item for item in final_records if item.api_key == "key-2").is_enabled)


if __name__ == "__main__":
    unittest.main()
