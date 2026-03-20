import unittest

import DrissionPage_example as main_script


class MainProxyPoolTests(unittest.TestCase):
    def test_load_proxy_pool_returns_none_when_disabled(self):
        self.assertTrue(hasattr(main_script, "load_proxy_pool"), "缺少 load_proxy_pool")

        pool = main_script.load_proxy_pool({"proxy_pool": {"enabled": False, "proxies": []}})

        self.assertIsNone(pool)

    def test_create_clients_for_round_uses_same_proxy_for_both_sessions(self):
        self.assertTrue(hasattr(main_script, "load_proxy_pool"), "缺少 load_proxy_pool")
        self.assertTrue(hasattr(main_script, "create_clients_for_round"), "缺少 create_clients_for_round")

        pool = main_script.load_proxy_pool(
            {
                "proxy_pool": {
                    "enabled": True,
                    "strategy": "round_robin",
                    "proxies": [
                        "gate.ipdeep.com:8082:d2533502065-dc-country-any-session-1304948000-sessiontime-5:KspkkhU4"
                    ],
                }
            }
        )

        mail_client, deapi_client, proxy_label = main_script.create_clients_for_round(
            pool=pool,
            mail_api_key="demo-api-key",
            mail_base_url="https://mail.example.com",
            deapi_base_url="https://deapi.ai",
        )

        expected_proxy = (
            "socks5h://"
            "d2533502065-dc-country-any-session-1304948000-sessiontime-5:"
            "KspkkhU4@gate.ipdeep.com:8082"
        )

        self.assertEqual(mail_client.session.proxies["http"], expected_proxy)
        self.assertEqual(mail_client.session.proxies["https"], expected_proxy)
        self.assertEqual(deapi_client.session.proxies["http"], expected_proxy)
        self.assertEqual(deapi_client.session.proxies["https"], expected_proxy)
        self.assertEqual(
            proxy_label,
            "gate.ipdeep.com:8082:d2533502065-dc-country-any-session-1304948000-sessiontime-5:***",
        )


if __name__ == "__main__":
    unittest.main()
