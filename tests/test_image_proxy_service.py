import base64
from dataclasses import dataclass
import unittest

from admin_store import ManagedApiKey
from deapi_image_gateway import ImageGenerationRequest, UpstreamAPIError
from deapi_key_pool import RoundRobinApiKeyPool
from openai_image_proxy import OpenAIImageProxyService, ProxyError


class FakeGateway:
    def __init__(self, submit_results, wait_results):
        self._submit_results = submit_results
        self._wait_results = wait_results
        self.submit_calls = []
        self.wait_calls = []

    def submit_job(self, api_key, request):
        self.submit_calls.append((api_key, request))
        result = self._submit_results[api_key]
        if isinstance(result, Exception):
            raise result
        return result

    def wait_for_image_bytes(self, api_key, request_id):
        self.wait_calls.append((api_key, request_id))
        result = self._wait_results[(api_key, request_id)]
        if isinstance(result, Exception):
            raise result
        return result


class FakeTracker:
    def __init__(self):
        self.error_calls = []
        self.success_calls = []

    def record_key_error(self, key_id, message):
        self.error_calls.append((key_id, message))

    def record_key_success(self, key_id):
        self.success_calls.append(key_id)


@dataclass(frozen=True)
class FakeManagedKey:
    id: int
    api_key: str


class ImageProxyServiceTests(unittest.TestCase):
    def test_generate_variant_model_overrides_dimensions_and_steps(self):
        gateway = FakeGateway(
            submit_results={"key-a": "request-1"},
            wait_results={("key-a", "request-1"): b"png-bytes"},
        )
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(("key-a",)),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            time_source=lambda: 1234567890,
        )

        service.generate(
            {
                "prompt": "四格漫画",
                "model": "z-image-688x1216",
                "size": "1x1",
                "width": 1,
                "height": 1,
                "steps": 99,
                "seed": 7,
            }
        )

        request = gateway.submit_calls[0][1]
        self.assertEqual(request.model, "ZImageTurbo_INT8")
        self.assertEqual(request.width, 688)
        self.assertEqual(request.height, 1216)
        self.assertEqual(request.steps, 8)

    def test_generate_retries_next_key_before_request_id_and_returns_b64(self):
        gateway = FakeGateway(
            submit_results={
                "key-a": UpstreamAPIError(
                    "submit rate limited",
                    status_code=429,
                    retryable_with_next_key=True,
                ),
                "key-b": "request-2",
            },
            wait_results={("key-b", "request-2"): b"png-bytes"},
        )
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(("key-a", "key-b")),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            time_source=lambda: 1234567890,
        )

        response = service.generate(
            {
                "prompt": "a red fox",
                "size": "512x768",
                "seed": 7,
                "steps": 8,
                "negative_prompt": "blur",
            }
        )

        first_request = gateway.submit_calls[0][1]
        second_request = gateway.submit_calls[1][1]
        self.assertEqual(gateway.submit_calls[0][0], "key-a")
        self.assertEqual(gateway.submit_calls[1][0], "key-b")
        self.assertEqual(gateway.wait_calls, [("key-b", "request-2")])
        self.assertIsInstance(first_request, ImageGenerationRequest)
        self.assertEqual(first_request.prompt, "a red fox")
        self.assertEqual(second_request.width, 512)
        self.assertEqual(second_request.height, 768)
        self.assertEqual(second_request.seed, 7)
        self.assertEqual(second_request.steps, 8)
        self.assertEqual(second_request.negative_prompt, "blur")
        self.assertEqual(response["created"], 1234567890)
        self.assertEqual(
            response["data"][0]["b64_json"],
            base64.b64encode(b"png-bytes").decode("ascii"),
        )

    def test_generate_does_not_switch_key_after_request_id_is_created(self):
        gateway = FakeGateway(
            submit_results={"key-a": "request-1", "key-b": "request-2"},
            wait_results={
                (
                    "key-a",
                    "request-1",
                ): UpstreamAPIError(
                    "poll failed",
                    status_code=502,
                    retryable_with_next_key=True,
                )
            },
        )
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(("key-a", "key-b")),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            time_source=lambda: 1234567890,
        )

        with self.assertRaisesRegex(ProxyError, "poll failed"):
            service.generate({"prompt": "a red fox", "seed": 7})

        self.assertEqual(gateway.submit_calls, [("key-a", gateway.submit_calls[0][1])])
        self.assertEqual(gateway.wait_calls, [("key-a", "request-1")])

    def test_generate_rejects_response_format_other_than_b64_json(self):
        gateway = FakeGateway(submit_results={"key-a": "request-1"}, wait_results={})
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(("key-a",)),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            time_source=lambda: 1234567890,
        )

        with self.assertRaisesRegex(ProxyError, "response_format 仅支持 b64_json"):
            service.generate({"prompt": "a red fox", "response_format": "url"})

    def test_generate_rejects_n_other_than_one(self):
        gateway = FakeGateway(submit_results={"key-a": "request-1"}, wait_results={})
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(("key-a",)),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            time_source=lambda: 1234567890,
        )

        with self.assertRaisesRegex(ProxyError, "当前仅支持 n=1"):
            service.generate({"prompt": "a red fox", "n": 2})

    def test_generate_requires_seed_before_hitting_upstream(self):
        gateway = FakeGateway(submit_results={"key-a": "request-1"}, wait_results={})
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(("key-a",)),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            time_source=lambda: 1234567890,
        )

        with self.assertRaisesRegex(ProxyError, "缺少 seed"):
            service.generate({"prompt": "a red fox"})

        self.assertEqual(gateway.submit_calls, [])

    def test_generate_records_error_and_success_for_managed_keys(self):
        gateway = FakeGateway(
            submit_results={
                "key-a": UpstreamAPIError(
                    "submit rate limited",
                    status_code=429,
                    retryable_with_next_key=True,
                ),
                "key-b": "request-2",
            },
            wait_results={("key-b", "request-2"): b"png-bytes"},
        )
        tracker = FakeTracker()
        service = OpenAIImageProxyService(
            key_pool=RoundRobinApiKeyPool(
                (
                    FakeManagedKey(id=10, api_key="key-a"),
                    FakeManagedKey(id=11, api_key="key-b"),
                )
            ),
            gateway=gateway,
            default_model="ZImageTurbo_INT8",
            default_size="768x768",
            key_event_tracker=tracker,
            time_source=lambda: 1234567890,
        )

        response = service.generate({"prompt": "a red fox", "seed": 7})

        self.assertEqual(
            tracker.error_calls,
            [(10, "submit rate limited")],
        )
        self.assertEqual(tracker.success_calls, [11])
        self.assertEqual(response["data"][0]["b64_json"], base64.b64encode(b"png-bytes").decode("ascii"))


if __name__ == "__main__":
    unittest.main()
