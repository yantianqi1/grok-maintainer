import unittest

from gptmail_client import extract_deapi_verify_link


WELCOME_MESSAGE = {
    "subject": "Welcome to deAPI! Here's $5 to get started",
    "html_content": '<a href="https://email.deapi.ai/c/tracking-only">Welcome</a>',
    "content": "",
}

ACTIVATION_MESSAGE = {
    "subject": "Activate your deAPI account",
    "html_content": """
        <a href="https://email.deapi.ai/c/tracked">Tracked</a>
        <a href="https://deapi.ai/verify-email/11136/hash?expires=1774066055&amp;signature=abc123">Activate</a>
    """,
    "content": "",
}


class GptMailClientTests(unittest.TestCase):
    def test_extract_deapi_verify_link_prefers_direct_verification_url(self):
        link = extract_deapi_verify_link([WELCOME_MESSAGE, ACTIVATION_MESSAGE])

        self.assertEqual(
            link,
            "https://deapi.ai/verify-email/11136/hash?expires=1774066055&signature=abc123",
        )


if __name__ == "__main__":
    unittest.main()
