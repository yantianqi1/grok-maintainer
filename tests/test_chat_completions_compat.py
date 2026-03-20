import base64
import unittest

from chat_completions_compat import create_chat_completion, create_chat_completion_stream
from deapi_key_pool import RoundRobinApiKeyPool
from openai_image_proxy import OpenAIImageProxyService
from openai_image_proxy import ProxyError


PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYuoAAAAASUVORK5CYII="
PNG_BYTES = base64.b64decode(PNG_B64)


class FakeImageService:
    def __init__(self):
        self.calls = []

    def generate(self, body):
        self.calls.append(body)
        return {
            "created": 1234567890,
            "data": [{"b64_json": PNG_B64}],
        }


class RecordingGateway:
    def __init__(self):
        self.submit_request = None

    def submit_job(self, api_key, request):
        self.submit_request = request
        return "request-1"

    def wait_for_image_bytes(self, api_key, request_id):
        return PNG_BYTES


class ChatCompletionsCompatTests(unittest.TestCase):
    def test_create_chat_completion_variant_model_forces_steps_and_dimensions(self):
        gateway = RecordingGateway()
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(("key-a",)),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            time_source=lambda: 1234567890,
        )

        response = create_chat_completion(
            service,
            {
                "messages": [{"role": "user", "content": "画个四格漫画"}],
                "model": "z-image-688x1216",
            },
            completion_id="chatcmpl-variant",
            created_at=111,
            seed_factory=lambda: 7,
        )

        self.assertEqual(gateway.submit_request.model, "ZImageTurbo_INT8")
        self.assertEqual(gateway.submit_request.width, 688)
        self.assertEqual(gateway.submit_request.height, 1216)
        self.assertEqual(gateway.submit_request.steps, 8)
        self.assertEqual(response["model"], "z-image-688x1216")

    def test_create_chat_completion_uses_last_user_message_and_generates_seed(self):
        service = FakeImageService()

        response = create_chat_completion(
            service,
            {
                "messages": [
                    {"role": "system", "content": "[Start a new Chat]"},
                    {"role": "user", "content": "一只小狗"},
                ],
                "model": "ZImageTurbo_INT8",
            },
            completion_id="chatcmpl-1",
            created_at=111,
            seed_factory=lambda: 7,
        )

        self.assertEqual(service.calls[0]["prompt"], "一只小狗")
        self.assertEqual(service.calls[0]["seed"], 7)
        self.assertEqual(response["object"], "chat.completion")
        self.assertTrue(
            response["choices"][0]["message"]["content"].startswith("![](data:image/png;base64,")
        )

    def test_create_chat_completion_prefers_top_level_prompt(self):
        service = FakeImageService()

        create_chat_completion(
            service,
            {
                "prompt": "显式提示词",
                "messages": [{"role": "user", "content": "不会使用这个"}],
                "model": "ZImageTurbo_INT8",
                "seed": 9,
            },
            completion_id="chatcmpl-2",
            created_at=222,
            seed_factory=lambda: 1,
        )

        self.assertEqual(service.calls[0]["prompt"], "显式提示词")
        self.assertEqual(service.calls[0]["seed"], 9)

    def test_create_chat_completion_stream_returns_sse_chunks_and_done(self):
        service = FakeImageService()

        events = create_chat_completion_stream(
            service,
            {
                "messages": [{"role": "user", "content": "一只小狗"}],
                "model": "ZImageTurbo_INT8",
            },
            completion_id="chatcmpl-3",
            created_at=333,
            seed_factory=lambda: 11,
        )

        self.assertIn('"chat.completion.chunk"', events[0])
        self.assertIn('"role": "assistant"', events[0])
        self.assertIn("data:image/png;base64,", events[1])
        self.assertIn('"finish_reason": "stop"', events[2])
        self.assertEqual(events[3], "data: [DONE]\n\n")

    def test_create_chat_completion_requires_prompt(self):
        service = FakeImageService()

        with self.assertRaisesRegex(ProxyError, "缺少 prompt"):
            create_chat_completion(
                service,
                {"messages": [{"role": "system", "content": "[Start a new Chat]"}]},
                completion_id="chatcmpl-4",
                created_at=444,
                seed_factory=lambda: 5,
            )


if __name__ == "__main__":
    unittest.main()
