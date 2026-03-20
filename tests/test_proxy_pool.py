import importlib
import importlib.util
import unittest


class ProxyPoolTests(unittest.TestCase):
    def test_parse_proxy_entry_builds_socks5h_urls(self):
        spec = importlib.util.find_spec("proxy_pool")
        self.assertIsNotNone(spec, "proxy_pool 模块不存在")

        module = importlib.import_module("proxy_pool")
        self.assertTrue(hasattr(module, "parse_proxy_entry"), "缺少 parse_proxy_entry")

        entry = module.parse_proxy_entry(
            "gate.ipdeep.com:8082:d2533502065-dc-country-any-session-1304948000-sessiontime-5:KspkkhU4"
        )

        self.assertEqual(entry.host, "gate.ipdeep.com")
        self.assertEqual(entry.port, 8082)
        self.assertEqual(
            entry.username,
            "d2533502065-dc-country-any-session-1304948000-sessiontime-5",
        )
        self.assertEqual(entry.password, "KspkkhU4")
        self.assertEqual(
            entry.requests_proxies(),
            {
                "http": "socks5h://d2533502065-dc-country-any-session-1304948000-sessiontime-5:KspkkhU4@gate.ipdeep.com:8082",
                "https": "socks5h://d2533502065-dc-country-any-session-1304948000-sessiontime-5:KspkkhU4@gate.ipdeep.com:8082",
            },
        )

    def test_round_robin_proxy_pool_cycles_entries(self):
        spec = importlib.util.find_spec("proxy_pool")
        self.assertIsNotNone(spec, "proxy_pool 模块不存在")

        module = importlib.import_module("proxy_pool")
        self.assertTrue(hasattr(module, "ProxyPool"), "缺少 ProxyPool")

        pool = module.ProxyPool.from_strings(
            [
                "host1.example.com:1001:user1:pass1",
                "host2.example.com:1002:user2:pass2",
            ]
        )

        self.assertEqual(pool.next_proxy().host, "host1.example.com")
        self.assertEqual(pool.next_proxy().host, "host2.example.com")
        self.assertEqual(pool.next_proxy().host, "host1.example.com")

    def test_masked_display_hides_password(self):
        spec = importlib.util.find_spec("proxy_pool")
        self.assertIsNotNone(spec, "proxy_pool 模块不存在")

        module = importlib.import_module("proxy_pool")
        self.assertTrue(hasattr(module, "parse_proxy_entry"), "缺少 parse_proxy_entry")

        entry = module.parse_proxy_entry("host.example.com:1080:user-name:secret-pass")

        self.assertEqual(
            entry.masked_display(),
            "host.example.com:1080:user-name:***",
        )


if __name__ == "__main__":
    unittest.main()
