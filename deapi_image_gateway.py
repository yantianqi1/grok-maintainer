from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any, Callable

import requests


RETRYABLE_STATUS_CODES = frozenset({401, 403, 429})
TXT2IMG_PATH = "/api/v1/client/txt2img"
REQUEST_STATUS_PATH = "/api/v1/client/request-status/{request_id}"
STATUS_SUCCESS = frozenset({"completed", "done", "success", "succeeded"})
STATUS_PENDING = frozenset({"queued", "pending", "processing", "running"})
STATUS_FAILURE = frozenset({"failed", "error", "cancelled"})
NETWORK_ERROR_STATUS = 502


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    model: str
    width: int
    height: int
    negative_prompt: str
    seed: int | None
    steps: int | None


class UpstreamAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        retryable_with_next_key: bool,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable_with_next_key = retryable_with_next_key


class DeapiImageGateway:
    def __init__(
        self,
        *,
        base_url: str,
        session: requests.Session | None = None,
        submit_timeout_sec: int,
        poll_timeout_sec: int,
        poll_interval_sec: int,
        download_timeout_sec: int,
        sleeper: Callable[[float], None] = sleep,
        time_source: Callable[[], float] = monotonic,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._submit_timeout_sec = submit_timeout_sec
        self._poll_timeout_sec = poll_timeout_sec
        self._poll_interval_sec = poll_interval_sec
        self._download_timeout_sec = download_timeout_sec
        self._sleeper = sleeper
        self._time_source = time_source

    def submit_job(self, api_key: str, request: ImageGenerationRequest) -> str:
        payload = _build_submit_payload(request)
        headers = _build_headers(api_key)
        url = f"{self._base_url}{TXT2IMG_PATH}"
        body = self._request_json(
            "post",
            url,
            headers=headers,
            json_body=payload,
            timeout_sec=self._submit_timeout_sec,
            retryable_with_next_key=True,
        )
        request_id = _extract_request_id(body)
        if not request_id:
            raise UpstreamAPIError(
                "deAPI txt2img 响应里没有 request_id",
                status_code=NETWORK_ERROR_STATUS,
                retryable_with_next_key=False,
            )
        return request_id

    def wait_for_image_bytes(self, api_key: str, request_id: str) -> bytes:
        result_url = self._poll_result_url(api_key, request_id)
        return self._download_image_bytes(result_url)

    def _poll_result_url(self, api_key: str, request_id: str) -> str:
        deadline = self._time_source() + self._poll_timeout_sec
        headers = _build_headers(api_key)
        while self._time_source() <= deadline:
            url = f"{self._base_url}{REQUEST_STATUS_PATH.format(request_id=request_id)}"
            body = self._request_json(
                "get",
                url,
                headers=headers,
                timeout_sec=self._poll_request_timeout_sec(),
                retryable_with_next_key=False,
            )
            if _has_result_url(body):
                return _extract_result_url(body)
            status = _extract_status(body)
            if status in STATUS_PENDING:
                self._sleeper(self._poll_interval_sec)
                continue
            if status in STATUS_SUCCESS:
                return _extract_result_url(body)
            if status in STATUS_FAILURE:
                message = _extract_message(body) or f"deAPI 任务失败: {status}"
                raise UpstreamAPIError(
                    message,
                    status_code=NETWORK_ERROR_STATUS,
                    retryable_with_next_key=False,
                )
            raise UpstreamAPIError(
                f"未知的 deAPI 任务状态: {status}",
                status_code=NETWORK_ERROR_STATUS,
                retryable_with_next_key=False,
            )
        raise UpstreamAPIError(
            "轮询 deAPI 结果超时",
            status_code=NETWORK_ERROR_STATUS,
            retryable_with_next_key=False,
        )

    def _poll_request_timeout_sec(self) -> int:
        return max(self._submit_timeout_sec, self._poll_interval_sec)

    def _download_image_bytes(self, result_url: str) -> bytes:
        try:
            response = self._session.get(result_url, timeout=self._download_timeout_sec)
            response.raise_for_status()
        except requests.RequestException as error:
            raise UpstreamAPIError(
                f"下载图片失败: {error}",
                status_code=NETWORK_ERROR_STATUS,
                retryable_with_next_key=False,
            ) from error
        if not response.content:
            raise UpstreamAPIError(
                "下载图片失败: 返回内容为空",
                status_code=NETWORK_ERROR_STATUS,
                retryable_with_next_key=False,
            )
        return response.content

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout_sec: int,
        retryable_with_next_key: bool,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._session.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=timeout_sec,
            )
        except requests.RequestException as error:
            raise UpstreamAPIError(
                f"请求 deAPI 失败: {error}",
                status_code=NETWORK_ERROR_STATUS,
                retryable_with_next_key=retryable_with_next_key,
            ) from error
        return _parse_json_response(response, retryable_with_next_key)


def _build_submit_payload(request: ImageGenerationRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "prompt": request.prompt,
        "model": request.model,
        "width": request.width,
        "height": request.height,
        "negative_prompt": request.negative_prompt,
    }
    if request.seed is not None:
        payload["seed"] = request.seed
    if request.steps is not None:
        payload["steps"] = request.steps
    return payload


def _build_headers(api_key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }


def _parse_json_response(response: requests.Response, retryable_with_next_key: bool) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as error:
        raise UpstreamAPIError(
            "deAPI 返回了无法解析的 JSON",
            status_code=response.status_code,
            retryable_with_next_key=retryable_with_next_key and response.status_code >= 500,
        ) from error
    if response.ok:
        return _ensure_mapping(body)
    raise UpstreamAPIError(
        _extract_message(body) or f"deAPI 请求失败: HTTP {response.status_code}",
        status_code=response.status_code,
        retryable_with_next_key=_is_retryable_status(response.status_code, retryable_with_next_key),
    )


def _is_retryable_status(status_code: int, retryable_with_next_key: bool) -> bool:
    if not retryable_with_next_key:
        return False
    return status_code in RETRYABLE_STATUS_CODES or status_code >= 500


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise UpstreamAPIError(
        "deAPI 返回体必须是 JSON 对象",
        status_code=NETWORK_ERROR_STATUS,
        retryable_with_next_key=False,
    )


def _extract_request_id(body: dict[str, Any]) -> str:
    for container in (body, _read_mapping(body.get("data"))):
        request_id = container.get("request_id")
        if request_id is not None:
            return str(request_id).strip()
    return ""


def _extract_status(body: dict[str, Any]) -> str:
    for container in (body, _read_mapping(body.get("data"))):
        status = container.get("status")
        if status is not None:
            return str(status).strip().lower()
    raise UpstreamAPIError(
        "deAPI 状态响应里没有 status",
        status_code=NETWORK_ERROR_STATUS,
        retryable_with_next_key=False,
    )


def _extract_result_url(body: dict[str, Any]) -> str:
    for container in (body, _read_mapping(body.get("data"))):
        result_url = container.get("result_url") or container.get("result")
        if isinstance(result_url, str) and result_url.strip():
            return result_url.strip()
    raise UpstreamAPIError(
        "deAPI 状态响应里没有 result_url",
        status_code=NETWORK_ERROR_STATUS,
        retryable_with_next_key=False,
    )


def _has_result_url(body: dict[str, Any]) -> bool:
    for container in (body, _read_mapping(body.get("data"))):
        result_url = container.get("result_url") or container.get("result")
        if isinstance(result_url, str) and result_url.strip():
            return True
    return False


def _extract_message(body: dict[str, Any]) -> str:
    for key in ("message", "error", "detail"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = _read_mapping(body.get("data"))
    for key in ("message", "error", "detail"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
