from __future__ import annotations

import base64
import json
import secrets
from typing import Any, Callable, Mapping

from openai_image_proxy import ProxyError


CHAT_COMPLETION_OBJECT = "chat.completion"
CHAT_COMPLETION_CHUNK_OBJECT = "chat.completion.chunk"
CHAT_COMPLETION_ROLE = "assistant"
DONE_EVENT = "data: [DONE]\n\n"
TEXT_PART_TYPES = frozenset({"text", "input_text"})
USER_ROLE = "user"
DEFAULT_IMAGE_MIME = "image/png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
WEBP_RIFF_SIGNATURE = b"RIFF"
WEBP_WEBP_SIGNATURE = b"WEBP"


def create_chat_completion(
    image_service,
    body: Mapping[str, Any],
    *,
    completion_id: str,
    created_at: int,
    seed_factory: Callable[[], int],
) -> dict[str, Any]:
    image_request = build_image_request_from_chat_request(body, seed_factory)
    image_response = image_service.generate(image_request)
    content = _build_markdown_image_content(image_response["data"][0]["b64_json"])
    model = _read_model_name(body, image_request)
    return {
        "id": completion_id,
        "object": CHAT_COMPLETION_OBJECT,
        "created": created_at,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": CHAT_COMPLETION_ROLE,
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
    }


def create_chat_completion_stream(
    image_service,
    body: Mapping[str, Any],
    *,
    completion_id: str,
    created_at: int,
    seed_factory: Callable[[], int],
) -> tuple[str, ...]:
    completion = create_chat_completion(
        image_service,
        body,
        completion_id=completion_id,
        created_at=created_at,
        seed_factory=seed_factory,
    )
    content = completion["choices"][0]["message"]["content"]
    model = completion["model"]
    return (
        _serialize_sse_chunk(_build_chunk(completion_id, created_at, model, {"role": CHAT_COMPLETION_ROLE}, None)),
        _serialize_sse_chunk(_build_chunk(completion_id, created_at, model, {"content": content}, None)),
        _serialize_sse_chunk(_build_chunk(completion_id, created_at, model, {}, "stop")),
        DONE_EVENT,
    )


def build_image_request_from_chat_request(
    body: Mapping[str, Any],
    seed_factory: Callable[[], int],
) -> dict[str, Any]:
    prompt = _extract_prompt(body)
    image_request: dict[str, Any] = {
        "prompt": prompt,
        "seed": _read_seed(body, seed_factory),
    }
    for field_name in ("model", "size", "width", "height", "steps", "negative_prompt", "n"):
        value = body.get(field_name)
        if value is not None:
            image_request[field_name] = value
    return image_request


def generate_completion_id() -> str:
    return f"chatcmpl-{secrets.token_hex(12)}"


def default_seed() -> int:
    return secrets.randbits(32)


def _extract_prompt(body: Mapping[str, Any]) -> str:
    explicit_prompt = _read_text(body.get("prompt"))
    if explicit_prompt:
        return explicit_prompt
    messages = body.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            prompt = _extract_prompt_from_message(message)
            if prompt:
                return prompt
    raise ProxyError("缺少 prompt", status_code=400, code="missing_prompt", param="prompt")


def _extract_prompt_from_message(message: Any) -> str:
    if not isinstance(message, Mapping):
        return ""
    if str(message.get("role", "")).strip() != USER_ROLE:
        return ""
    return _extract_message_content(message.get("content"))


def _extract_message_content(content: Any) -> str:
    text_content = _read_text(content)
    if text_content:
        return text_content
    if not isinstance(content, list):
        return ""
    parts = [_extract_text_part(part) for part in content]
    return "\n".join(part for part in parts if part)


def _extract_text_part(part: Any) -> str:
    if not isinstance(part, Mapping):
        return ""
    part_type = str(part.get("type", "")).strip()
    if part_type and part_type not in TEXT_PART_TYPES:
        return ""
    return _read_text(part.get("text"))


def _read_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _read_seed(body: Mapping[str, Any], seed_factory: Callable[[], int]) -> int:
    value = body.get("seed")
    return int(value) if value is not None else int(seed_factory())


def _read_model_name(body: Mapping[str, Any], image_request: Mapping[str, Any]) -> str:
    value = body.get("model", image_request.get("model", ""))
    return str(value).strip() or "ZImageTurbo_INT8"


def _build_markdown_image_content(b64_json: str) -> str:
    mime_type = _detect_image_mime_type(b64_json)
    return f"![](data:{mime_type};base64,{b64_json})"


def _detect_image_mime_type(b64_json: str) -> str:
    prefix = _decode_prefix_bytes(b64_json)
    if prefix.startswith(PNG_SIGNATURE):
        return "image/png"
    if prefix.startswith(JPEG_SIGNATURE):
        return "image/jpeg"
    if prefix.startswith(WEBP_RIFF_SIGNATURE) and prefix[8:12] == WEBP_WEBP_SIGNATURE:
        return "image/webp"
    return DEFAULT_IMAGE_MIME


def _decode_prefix_bytes(b64_json: str) -> bytes:
    prefix = b64_json[:64]
    padding = "=" * ((4 - len(prefix) % 4) % 4)
    return base64.b64decode(prefix + padding)


def _build_chunk(
    completion_id: str,
    created_at: int,
    model: str,
    delta: dict[str, Any],
    finish_reason: str | None,
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": CHAT_COMPLETION_CHUNK_OBJECT,
        "created": created_at,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def _serialize_sse_chunk(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
