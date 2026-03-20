import unittest

from image_proxy_server import create_app
from openai_image_proxy import ProxyError


class FakeService:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def generate(self, body):
        self.calls.append(body)
        if self._error is not None:
            raise self._error
        return self._response


class ImageProxyServerTests(unittest.TestCase):
    def test_get_models_returns_variant_model_list_by_default(self):
        app = create_app(service=FakeService())
        client = app.test_client()

        response = client.get("/v1/models")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        model_ids = [item["id"] for item in body["data"]]
        self.assertEqual(body["object"], "list")
        self.assertEqual(
            model_ids,
            [
                "z-image-1024x1024",
                "z-image-832x1216",
                "z-image-1216x832",
                "z-image-688x1216",
                "z-image-1216x688",
            ],
        )
        self.assertEqual(body["data"][0]["object"], "model")

    def test_post_images_generations_returns_b64_json_payload(self):
        service = FakeService(
            response={
                "created": 1234567890,
                "data": [{"b64_json": "ZmFrZS1pbWFnZQ=="}],
            }
        )
        app = create_app(service=service)
        client = app.test_client()

        response = client.post("/v1/images/generations", json={"prompt": "a red fox"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"][0]["b64_json"], "ZmFrZS1pbWFnZQ==")
        self.assertEqual(service.calls, [{"prompt": "a red fox"}])

    def test_post_images_generations_returns_structured_error(self):
        service = FakeService(
            error=ProxyError(
                "response_format 仅支持 b64_json",
                status_code=400,
                code="unsupported_response_format",
                param="response_format",
            )
        )
        app = create_app(service=service)
        client = app.test_client()

        response = client.post("/v1/images/generations", json={"prompt": "a red fox"})

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], "unsupported_response_format")
        self.assertEqual(body["error"]["param"], "response_format")

    def test_post_chat_completions_returns_markdown_image_message(self):
        service = FakeService(
            response={
                "created": 1234567890,
                "data": [{"b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYuoAAAAASUVORK5CYII="}],
            }
        )
        app = create_app(service=service)
        client = app.test_client()

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "ZImageTurbo_INT8",
                "messages": [
                    {"role": "system", "content": "[Start a new Chat]"},
                    {"role": "user", "content": "一只小狗"},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["object"], "chat.completion")
        self.assertTrue(body["choices"][0]["message"]["content"].startswith("![](data:image/png;base64,"))
        self.assertEqual(service.calls[0]["prompt"], "一只小狗")
        self.assertIn("seed", service.calls[0])

    def test_post_chat_completions_stream_returns_sse(self):
        service = FakeService(
            response={
                "created": 1234567890,
                "data": [{"b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYuoAAAAASUVORK5CYII="}],
            }
        )
        app = create_app(service=service)
        client = app.test_client()

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "ZImageTurbo_INT8",
                "messages": [{"role": "user", "content": "一只小狗"}],
                "stream": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        payload = response.get_data(as_text=True)
        self.assertIn("chat.completion.chunk", payload)
        self.assertIn("data: [DONE]", payload)

    def test_post_chat_completions_returns_prompt_error(self):
        app = create_app(service=FakeService())
        client = app.test_client()

        response = client.post(
            "/v1/chat/completions",
            json={"model": "ZImageTurbo_INT8", "messages": [{"role": "system", "content": "only"}]},
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], "missing_prompt")

    def test_unknown_route_returns_404_instead_of_internal_server_error(self):
        app = create_app(service=FakeService())
        client = app.test_client()

        response = client.get("/v1/does-not-exist")

        self.assertEqual(response.status_code, 404)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
