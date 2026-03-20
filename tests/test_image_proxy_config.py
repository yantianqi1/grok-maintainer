import tempfile
import unittest
from pathlib import Path

from image_proxy_config import load_image_proxy_settings, load_upstream_api_keys


class ImageProxyConfigTests(unittest.TestCase):
    def test_load_image_proxy_settings_reads_defaults_and_resolves_key_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            settings = load_image_proxy_settings(
                {
                    "image_proxy": {
                        "host": "127.0.0.1",
                        "port": 9090,
                        "default_model": "demo-model",
                        "default_size": "1024x512",
                        "upstream_key_file": "api_keys/custom_keys.txt",
                    }
                },
                root_dir,
            )

            self.assertEqual(settings.host, "127.0.0.1")
            self.assertEqual(settings.port, 9090)
            self.assertEqual(settings.default_model, "demo-model")
            self.assertEqual(settings.default_size, "1024x512")
            self.assertEqual(settings.upstream_key_file, root_dir / "api_keys" / "custom_keys.txt")
            self.assertEqual(settings.poll_interval_sec, 2)

    def test_load_upstream_api_keys_reads_non_empty_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = Path(temp_dir) / "keys.txt"
            key_file.write_text("key-1\n\n key-2 \n", encoding="utf-8")
            settings = load_image_proxy_settings(
                {"image_proxy": {"upstream_key_file": str(key_file)}},
                Path(temp_dir),
            )

            self.assertEqual(load_upstream_api_keys(settings), ("key-1", "key-2"))

    def test_load_upstream_api_keys_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = Path(temp_dir) / "keys.txt"
            key_file.write_text("\n  \n", encoding="utf-8")
            settings = load_image_proxy_settings(
                {"image_proxy": {"upstream_key_file": str(key_file)}},
                Path(temp_dir),
            )

            with self.assertRaisesRegex(RuntimeError, "没有可用的 deAPI API key"):
                load_upstream_api_keys(settings)


if __name__ == "__main__":
    unittest.main()
