from __future__ import annotations

import base64
from dataclasses import dataclass
from time import time
from typing import Any, Callable, Mapping

from deapi_image_gateway import ImageGenerationRequest, UpstreamAPIError
from image_model_variants import FIXED_GENERATION_STEPS, find_image_model_variant


DEFAULT_NEGATIVE_PROMPT = ""
SUPPORTED_RESPONSE_FORMAT = "b64_json"
SUPPORTED_IMAGE_COUNT = 1


class ProxyError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.param = param

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "message": str(self),
                "type": "invalid_request_error" if self.status_code < 500 else "server_error",
                "param": self.param,
                "code": self.code,
            }
        }


@dataclass(frozen=True)
class SubmissionHandle:
    key_item: Any
    api_key: str
    request_id: str


class OpenAIImageProxyService:
    def __init__(
        self,
        *,
        key_pool,
        gateway,
        default_model: str,
        default_size: str,
        key_event_tracker=None,
        time_source: Callable[[], float] = time,
    ) -> None:
        self._key_pool = key_pool
        self._gateway = gateway
        self._default_model = default_model
        self._default_size = default_size
        self._key_event_tracker = key_event_tracker
        self._time_source = time_source

    def generate(self, body: Mapping[str, Any]) -> dict[str, Any]:
        request = parse_image_generation_request(
            body,
            default_model=self._default_model,
            default_size=self._default_size,
        )
        submission = self._submit_with_retry(request)
        try:
            image_bytes = self._gateway.wait_for_image_bytes(submission.api_key, submission.request_id)
        except UpstreamAPIError as error:
            self._record_key_error(submission.key_item, str(error))
            raise _translate_upstream_error(error) from error
        self._record_key_success(submission.key_item)
        return build_image_response(image_bytes, int(self._time_source()))

    def _submit_with_retry(self, request: ImageGenerationRequest) -> SubmissionHandle:
        last_error: UpstreamAPIError | None = None
        for key_item in self._key_pool.reserve_attempt_order():
            api_key = _read_api_key_value(key_item)
            try:
                request_id = self._gateway.submit_job(api_key, request)
            except UpstreamAPIError as error:
                self._record_key_error(key_item, str(error))
                if error.retryable_with_next_key:
                    last_error = error
                    continue
                raise _translate_upstream_error(error) from error
            return SubmissionHandle(key_item=key_item, api_key=api_key, request_id=request_id)
        if last_error is None:
            raise ProxyError(
                "没有可用的上游 API key",
                status_code=502,
                code="no_upstream_api_key",
            )
        raise _translate_upstream_error(last_error) from last_error

    def _record_key_error(self, key_item: Any, message: str) -> None:
        key_id = _read_key_id(key_item)
        if self._key_event_tracker is None or key_id is None:
            return
        self._key_event_tracker.record_key_error(key_id, message)

    def _record_key_success(self, key_item: Any) -> None:
        key_id = _read_key_id(key_item)
        if self._key_event_tracker is None or key_id is None:
            return
        self._key_event_tracker.record_key_success(key_id)


def parse_image_generation_request(
    body: Mapping[str, Any],
    *,
    default_model: str,
    default_size: str,
) -> ImageGenerationRequest:
    if not isinstance(body, Mapping):
        raise ProxyError("请求体必须是 JSON 对象", status_code=400, code="invalid_json")
    _validate_response_format(body.get("response_format"))
    _validate_image_count(body.get("n"))
    prompt = _read_prompt(body)
    requested_model = _read_string(body.get("model"), default_model)
    model, width, height = _resolve_model_and_dimensions(body, requested_model, default_size)
    return ImageGenerationRequest(
        prompt=prompt,
        model=model,
        width=width,
        height=height,
        negative_prompt=_read_string(body.get("negative_prompt"), DEFAULT_NEGATIVE_PROMPT),
        seed=_read_required_int(body.get("seed"), "seed"),
        steps=FIXED_GENERATION_STEPS,
    )


def build_image_response(image_bytes: bytes, created_at: int) -> dict[str, Any]:
    return {
        "created": created_at,
        "data": [
            {
                "b64_json": base64.b64encode(image_bytes).decode("ascii"),
            }
        ],
    }


def _validate_response_format(value: Any) -> None:
    if value is None:
        return
    if str(value).strip() == SUPPORTED_RESPONSE_FORMAT:
        return
    raise ProxyError(
        "response_format 仅支持 b64_json",
        status_code=400,
        code="unsupported_response_format",
        param="response_format",
    )


def _validate_image_count(value: Any) -> None:
    if value is None:
        return
    if int(value) == SUPPORTED_IMAGE_COUNT:
        return
    raise ProxyError(
        "当前仅支持 n=1",
        status_code=400,
        code="unsupported_image_count",
        param="n",
    )


def _read_prompt(body: Mapping[str, Any]) -> str:
    if "prompt" not in body:
        raise ProxyError("缺少 prompt", status_code=400, code="missing_prompt", param="prompt")
    prompt = body["prompt"]
    if not isinstance(prompt, str):
        raise ProxyError("prompt 必须是字符串", status_code=400, code="invalid_prompt", param="prompt")
    return prompt


def _read_dimensions(body: Mapping[str, Any], default_size: str) -> tuple[int, int]:
    if "width" in body or "height" in body:
        return _read_explicit_dimensions(body)
    size = _read_string(body.get("size"), default_size)
    return _parse_size(size)


def _resolve_model_and_dimensions(
    body: Mapping[str, Any],
    requested_model: str,
    default_size: str,
) -> tuple[str, int, int]:
    variant = find_image_model_variant(requested_model)
    if variant is None:
        width, height = _read_dimensions(body, default_size)
        return requested_model, width, height
    return variant.upstream_name, variant.width, variant.height


def _read_explicit_dimensions(body: Mapping[str, Any]) -> tuple[int, int]:
    if "width" not in body or "height" not in body:
        raise ProxyError(
            "width 和 height 必须同时提供",
            status_code=400,
            code="invalid_dimensions",
            param="size",
        )
    return _read_positive_int(body["width"], "width"), _read_positive_int(body["height"], "height")


def _parse_size(size: str) -> tuple[int, int]:
    parts = size.lower().split("x")
    if len(parts) != 2:
        raise ProxyError("size 必须是 WxH", status_code=400, code="invalid_size", param="size")
    return _read_positive_int(parts[0], "size"), _read_positive_int(parts[1], "size")


def _read_positive_int(value: Any, param: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ProxyError(f"{param} 必须是正整数", status_code=400, code="invalid_integer", param=param)
    return parsed


def _read_string(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _read_required_int(value: Any, param: str) -> int:
    if value is None:
        raise ProxyError(f"缺少 {param}", status_code=400, code=f"missing_{param}", param=param)
    return int(value)


def _translate_upstream_error(error: UpstreamAPIError) -> ProxyError:
    status_code = error.status_code if error.status_code >= 400 else 502
    return ProxyError(
        str(error),
        status_code=status_code,
        code="upstream_deapi_error",
    )


def _read_api_key_value(key_item: Any) -> str:
    if hasattr(key_item, "api_key"):
        return str(getattr(key_item, "api_key"))
    return str(key_item)


def _read_key_id(key_item: Any) -> int | None:
    if not hasattr(key_item, "id"):
        return None
    return int(getattr(key_item, "id"))
