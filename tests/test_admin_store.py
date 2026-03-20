import tempfile
import unittest
from pathlib import Path

from admin_store import AdminStore


class AdminStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self._temp_dir.name) / "admin.sqlite3"
        self.store = AdminStore(self.database_path)
        self.store.init_db()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_ensure_admin_user_creates_login_credentials(self):
        self.store.ensure_admin_user("admin", "secret-pass")

        self.assertTrue(self.store.verify_admin_credentials("admin", "secret-pass"))
        self.assertFalse(self.store.verify_admin_credentials("admin", "wrong-pass"))

    def test_bulk_add_parses_labels_and_skips_duplicates(self):
        result = self.store.bulk_add_api_keys(
            "\n".join(
                [
                    "Primary,key-1",
                    "key-2",
                    "Primary,key-1",
                    "Secondary,key-2",
                ]
            )
        )

        records = sorted(self.store.list_api_keys(), key=lambda item: item.api_key)
        self.assertEqual(result.added_count, 2)
        self.assertEqual(result.skipped_count, 2)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].label, "Primary")
        self.assertEqual(records[0].api_key, "key-1")
        self.assertEqual(records[1].label, "")
        self.assertEqual(records[1].api_key, "key-2")

    def test_toggle_delete_and_error_tracking_update_records(self):
        self.store.bulk_add_api_keys("Primary,key-1\nkey-2")
        records = sorted(self.store.list_api_keys(), key=lambda item: item.api_key)
        first_key = records[0]
        second_key = records[1]

        self.store.toggle_api_key(first_key.id)
        self.store.record_key_error(second_key.id, "rate limited")
        self.store.record_key_success(second_key.id)
        self.store.delete_api_key(first_key.id)

        enabled_keys = self.store.list_enabled_api_keys()
        remaining = self.store.list_api_keys()
        stats = self.store.get_dashboard_stats()

        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, second_key.id)
        self.assertEqual(enabled_keys[0].id, second_key.id)
        self.assertEqual(remaining[0].error_count, 1)
        self.assertEqual(remaining[0].last_error_message, "rate limited")
        self.assertIsNotNone(remaining[0].last_used_at)
        self.assertEqual(stats.total_keys, 1)
        self.assertEqual(stats.enabled_keys, 1)
        self.assertEqual(stats.total_error_count, 1)

    def test_success_count_filters_and_bulk_actions(self):
        self.store.bulk_add_api_keys("Alpha,key-1\nBravo,key-2\nCharlie,key-3")
        records = sorted(self.store.list_api_keys(), key=lambda item: item.api_key)
        first_key, second_key, third_key = records

        self.store.record_key_success(first_key.id)
        self.store.record_key_success(first_key.id)
        self.store.record_key_error(second_key.id, "rate limited")
        self.store.record_key_success(second_key.id)
        self.store.toggle_api_key(second_key.id)

        all_records = sorted(self.store.list_api_keys("all"), key=lambda item: item.api_key)
        enabled_records = self.store.list_api_keys("enabled")
        disabled_records = self.store.list_api_keys("disabled")
        error_records = self.store.list_api_keys("error")
        unused_records = self.store.list_api_keys("unused")

        self.assertEqual(all_records[0].success_count, 2)
        self.assertEqual(all_records[1].success_count, 1)
        self.assertEqual(all_records[2].success_count, 0)
        self.assertEqual([item.api_key for item in enabled_records], ["key-3", "key-1"])
        self.assertEqual([item.api_key for item in disabled_records], ["key-2"])
        self.assertEqual([item.api_key for item in error_records], ["key-2"])
        self.assertEqual([item.api_key for item in unused_records], ["key-3"])

        disabled_count = self.store.apply_bulk_action("disable", (first_key.id, third_key.id))
        enabled_count = self.store.apply_bulk_action("enable", (second_key.id,))
        deleted_count = self.store.apply_bulk_action("delete", (third_key.id,))

        final_records = sorted(self.store.list_api_keys(), key=lambda item: item.api_key)
        self.assertEqual(disabled_count, 2)
        self.assertEqual(enabled_count, 1)
        self.assertEqual(deleted_count, 1)
        self.assertEqual([item.api_key for item in final_records], ["key-1", "key-2"])
        self.assertFalse(next(item for item in final_records if item.api_key == "key-1").is_enabled)
        self.assertTrue(next(item for item in final_records if item.api_key == "key-2").is_enabled)


if __name__ == "__main__":
    unittest.main()
