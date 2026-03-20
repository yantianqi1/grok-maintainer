import tempfile
import unittest
from pathlib import Path

from deapi_workflow import append_api_key, run_single_deapi_registration


class FakeMailClient:
    def __init__(self):
        self.generated = "demo@example.com"
        self.verify_link = "https://deapi.ai/verify-email/1/hash?expires=1&signature=sig"

    def generate_email(self):
        return self.generated

    def wait_for_verify_link(self, email, timeout, interval):
        self.last_email = email
        self.last_timeout = timeout
        self.last_interval = interval
        return self.verify_link


class FakeDeapiClient:
    def __init__(self):
        self.created_key = "pk_test_created"

    def register(self, name, email, password):
        self.register_args = (name, email, password)
        return "/verify-email"

    def verify_email(self, verify_link):
        self.verify_link = verify_link
        return "https://deapi.ai/dashboard?verified=1"

    def create_api_key(self, key_name):
        self.key_name = key_name
        return self.created_key


class DeapiWorkflowTests(unittest.TestCase):
    def test_append_api_key_writes_one_key_per_line(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "keys.txt"

            append_api_key("first-key", output_path)
            append_api_key("second-key", output_path)

            self.assertEqual(output_path.read_text(encoding="utf-8"), "first-key\nsecond-key\n")

    def test_run_single_registration_exports_created_api_key(self):
        mail_client = FakeMailClient()
        deapi_client = FakeDeapiClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "keys.txt"

            result = run_single_deapi_registration(
                output_path=output_path,
                mail_client=mail_client,
                deapi_client=deapi_client,
                account_name="deapi test",
                password="Deapi!pass12345",
                api_key_name="codex-key",
            )

            self.assertEqual(result["email"], "demo@example.com")
            self.assertEqual(result["api_key"], "pk_test_created")
            self.assertEqual(result["dashboard_url"], "https://deapi.ai/dashboard?verified=1")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "pk_test_created\n")


if __name__ == "__main__":
    unittest.main()
