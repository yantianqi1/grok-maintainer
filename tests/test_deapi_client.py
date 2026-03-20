import unittest

from deapi_client import (
    build_livewire_payload,
    parse_created_api_key,
    parse_livewire_context,
    parse_livewire_redirect,
)


REGISTER_HTML = """
<html>
  <head>
    <meta name="csrf-token" content="csrf-123" />
  </head>
  <body>
    <div wire:snapshot="{&quot;data&quot;:{&quot;name&quot;:&quot;&quot;},&quot;memo&quot;:{&quot;id&quot;:&quot;abc123&quot;,&quot;name&quot;:&quot;auth.register&quot;},&quot;checksum&quot;:&quot;sum&quot;}" wire:effects="[]" wire:id="abc123" wire:name="auth.register"></div>
    <section wire:snapshot="{&quot;data&quot;:{&quot;showCreateModal&quot;:false,&quot;keyName&quot;:&quot;&quot;,&quot;createdKey&quot;:null},&quot;memo&quot;:{&quot;id&quot;:&quot;def456&quot;,&quot;name&quot;:&quot;settings.api-keys&quot;},&quot;checksum&quot;:&quot;sum2&quot;}" wire:id="def456" wire:name="settings.api-keys"></section>
    <script src="https://deapi.ai/livewire/livewire.min.js" data-update-uri="https://deapi.ai/livewire/update"></script>
  </body>
</html>
"""

REGISTER_RESPONSE = """
{"components":[{"snapshot":"{\\"data\\":{\\"name\\":\\"deapi test\\"},\\"memo\\":{\\"id\\":\\"abc123\\",\\"name\\":\\"auth.register\\"},\\"checksum\\":\\"sum\\"}","effects":{"returns":[null],"redirect":"\\/verify-email","redirectUsingNavigate":true}}],"assets":[]}
""".strip()

CREATE_KEY_RESPONSE = """
{"components":[{"snapshot":"{\\"data\\":{\\"showCreateModal\\":false,\\"keyName\\":\\"\\",\\"createdKey\\":\\"8614|secret-value\\",\\"showCreatedKeyModal\\":true},\\"memo\\":{\\"id\\":\\"def456\\",\\"name\\":\\"settings.api-keys\\"},\\"checksum\\":\\"sum2\\"}","effects":{"returns":[null]}}],"assets":[]}
""".strip()


class DeapiClientParsingTests(unittest.TestCase):
    def test_parse_livewire_context_extracts_csrf_update_uri_and_snapshot(self):
        context = parse_livewire_context(REGISTER_HTML, "auth.register")

        self.assertEqual(context.csrf_token, "csrf-123")
        self.assertEqual(context.update_uri, "https://deapi.ai/livewire/update")
        self.assertEqual(context.component_id, "abc123")
        self.assertIn('"name":"auth.register"', context.snapshot)

    def test_build_livewire_payload_sets_updates_and_call(self):
        context = parse_livewire_context(REGISTER_HTML, "settings.api-keys")

        payload = build_livewire_payload(
            csrf_token=context.csrf_token,
            snapshot=context.snapshot,
            updates={"keyName": "codex-key"},
            method="createKey",
        )

        self.assertEqual(payload["_token"], "csrf-123")
        self.assertEqual(payload["components"][0]["updates"]["keyName"], "codex-key")
        self.assertEqual(payload["components"][0]["calls"][0]["method"], "createKey")

    def test_parse_livewire_redirect_reads_verify_email_redirect(self):
        redirect = parse_livewire_redirect(REGISTER_RESPONSE)

        self.assertEqual(redirect, "/verify-email")

    def test_parse_created_api_key_strips_numeric_prefix_from_snapshot(self):
        created_key = parse_created_api_key(CREATE_KEY_RESPONSE)

        self.assertEqual(created_key, "secret-value")


if __name__ == "__main__":
    unittest.main()
