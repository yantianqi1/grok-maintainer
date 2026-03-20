import tempfile
import unittest
from pathlib import Path

from admin_store import AdminStore
from managed_key_pool import ManagedApiKeyPool


class ManagedApiKeyPoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self._temp_dir.name) / "admin.sqlite3"
        self.store = AdminStore(database_path)
        self.store.init_db()
        self.store.bulk_add_api_keys("Primary,key-1\nSecondary,key-2\nThird,key-3")

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_reserve_attempt_order_uses_enabled_keys_only(self):
        records = sorted(self.store.list_api_keys(), key=lambda item: item.api_key)
        self.store.toggle_api_key(records[1].id)
        pool = ManagedApiKeyPool(self.store)

        first = tuple(item.api_key for item in pool.reserve_attempt_order())
        second = tuple(item.api_key for item in pool.reserve_attempt_order())

        self.assertEqual(first, ("key-1", "key-3"))
        self.assertEqual(second, ("key-3", "key-1"))


if __name__ == "__main__":
    unittest.main()
