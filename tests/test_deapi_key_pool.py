import unittest

from deapi_key_pool import RoundRobinApiKeyPool


class DeapiKeyPoolTests(unittest.TestCase):
    def test_reserve_attempt_order_rotates_initial_key_per_request(self):
        pool = RoundRobinApiKeyPool(("key-a", "key-b", "key-c"))

        self.assertEqual(pool.reserve_attempt_order(), ("key-a", "key-b", "key-c"))
        self.assertEqual(pool.reserve_attempt_order(), ("key-b", "key-c", "key-a"))
        self.assertEqual(pool.reserve_attempt_order(), ("key-c", "key-a", "key-b"))
        self.assertEqual(pool.reserve_attempt_order(), ("key-a", "key-b", "key-c"))

    def test_pool_requires_at_least_one_key(self):
        with self.assertRaisesRegex(RuntimeError, "至少需要一把 deAPI API key"):
            RoundRobinApiKeyPool(())


if __name__ == "__main__":
    unittest.main()
