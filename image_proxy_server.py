from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from time import time
from typing import Any, Mapping

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

from admin_store import AdminStore
from admin_views import create_admin_blueprint
from chat_completions_compat import (
    create_chat_completion,
    create_chat_completion_stream,
    default_seed,
    generate_completion_id,
)
from deapi_image_gateway import DeapiImageGateway
from deapi_key_pool import RoundRobinApiKeyPool
from image_model_variants import list_public_model_ids
from image_proxy_config import load_admin_settings, load_image_proxy_settings, load_upstream_api_keys
from managed_key_pool import ManagedApiKeyPool
from openai_image_proxy import OpenAIImageProxyService, ProxyError


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.json"


@dataclass(frozen=True)
class AppRuntime:
    service: OpenAIImageProxyService
    store: AdminStore
    admin_settings: Any
    model_ids: tuple[str, ...]


def create_app(service=None, runtime: AppRuntime | None = None, models: tuple[str, ...] | None = None) -> Flask:
    actual_runtime = runtime or (build_runtime() if service is None else None)
    app = Flask(__name__)
    proxy_service = service or actual_runtime.service
    model_ids = models or _resolve_model_ids(actual_runtime)
    app.secret_key = (
        actual_runtime.admin_settings.session_secret if actual_runtime is not None else "dev-session-secret"
    )

    _register_openai_routes(app, proxy_service, model_ids)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        if isinstance(error, HTTPException):
            proxy_error = ProxyError(
                error.description,
                status_code=error.code or 500,
                code=_http_error_code(error),
            )
            return jsonify(proxy_error.to_dict()), proxy_error.status_code
        proxy_error = ProxyError(
            str(error) or error.__class__.__name__,
            status_code=500,
            code="internal_server_error",
        )
        return jsonify(proxy_error.to_dict()), proxy_error.status_code

    if actual_runtime is not None:
        app.register_blueprint(create_admin_blueprint(actual_runtime.store, actual_runtime.admin_settings))

    return app


def build_service(config: Mapping[str, Any] | None = None) -> OpenAIImageProxyService:
    project_config = dict(config or load_json_config(CONFIG_PATH))
    settings = load_image_proxy_settings(project_config, ROOT_DIR)
    api_keys = load_upstream_api_keys(settings)
    gateway = DeapiImageGateway(
        base_url=settings.upstream_base_url,
        submit_timeout_sec=settings.submit_timeout_sec,
        poll_timeout_sec=settings.poll_timeout_sec,
        poll_interval_sec=settings.poll_interval_sec,
        download_timeout_sec=settings.download_timeout_sec,
    )
    return OpenAIImageProxyService(
        key_pool=RoundRobinApiKeyPool(api_keys),
        gateway=gateway,
        default_model=settings.default_model,
        default_size=settings.default_size,
    )


def build_runtime(config: Mapping[str, Any] | None = None) -> AppRuntime:
    project_config = dict(config or load_json_config(CONFIG_PATH))
    proxy_settings = load_image_proxy_settings(project_config, ROOT_DIR)
    admin_settings = load_admin_settings(project_config, ROOT_DIR)
    store = AdminStore(admin_settings.database_path)
    store.init_db()
    store.ensure_admin_user(admin_settings.username, admin_settings.password)
    gateway = DeapiImageGateway(
        base_url=proxy_settings.upstream_base_url,
        submit_timeout_sec=proxy_settings.submit_timeout_sec,
        poll_timeout_sec=proxy_settings.poll_timeout_sec,
        poll_interval_sec=proxy_settings.poll_interval_sec,
        download_timeout_sec=proxy_settings.download_timeout_sec,
    )
    service = OpenAIImageProxyService(
        key_pool=ManagedApiKeyPool(store),
        gateway=gateway,
        default_model=proxy_settings.default_model,
        default_size=proxy_settings.default_size,
        key_event_tracker=store,
    )
    return AppRuntime(
        service=service,
        store=store,
        admin_settings=admin_settings,
        model_ids=list_public_model_ids(),
    )


def load_json_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        content = json.load(handle)
    if isinstance(content, dict):
        return content
    raise RuntimeError("config.json 顶层必须是对象")


def main(argv: list[str] | None = None) -> int:
    settings = load_image_proxy_settings(load_json_config(CONFIG_PATH), ROOT_DIR)
    parser = argparse.ArgumentParser(description="deAPI OpenAI 图片兼容中转服务")
    parser.add_argument("--host", default=settings.host, help=f"监听地址，默认 {settings.host}")
    parser.add_argument("--port", type=int, default=settings.port, help=f"监听端口，默认 {settings.port}")
    args = parser.parse_args(argv)
    app = create_app(runtime=build_runtime())
    app.run(host=args.host, port=args.port)
    return 0


def _read_json_payload() -> Mapping[str, Any]:
    payload = request.get_json(silent=True)
    if isinstance(payload, Mapping):
        return payload
    raise ProxyError("请求体必须是 JSON 对象", status_code=400, code="invalid_json")


def _register_openai_routes(
    app: Flask,
    proxy_service,
    model_ids: tuple[str, ...],
) -> None:
    @app.get("/v1/models")
    def list_models():
        return jsonify(_build_model_list(model_ids))

    @app.post("/v1/images/generations")
    def generate_image():
        try:
            payload = _read_json_payload()
            response_body = proxy_service.generate(payload)
            return jsonify(response_body)
        except ProxyError as error:
            return jsonify(error.to_dict()), error.status_code

    @app.post("/v1/chat/completions")
    def chat_completions():
        try:
            payload = _read_json_payload()
            if _is_stream_request(payload):
                return _build_streaming_chat_response(proxy_service, payload)
            response_body = create_chat_completion(
                proxy_service,
                payload,
                completion_id=generate_completion_id(),
                created_at=int(time()),
                seed_factory=default_seed,
            )
            return jsonify(response_body)
        except ProxyError as error:
            return jsonify(error.to_dict()), error.status_code


def _build_model_list(model_ids: tuple[str, ...]) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": 0,
                "owned_by": "deapi-relay",
            }
            for model_id in model_ids
        ],
    }


def _resolve_model_ids(runtime: AppRuntime | None) -> tuple[str, ...]:
    if runtime is not None:
        model_ids = getattr(runtime, "model_ids", None)
        if model_ids:
            return tuple(model_ids)
    return list_public_model_ids()


def _http_error_code(error: HTTPException) -> str:
    if error.code == 404:
        return "not_found"
    if error.code == 405:
        return "method_not_allowed"
    return f"http_{error.code or 500}"


def _build_streaming_chat_response(proxy_service, payload: Mapping[str, Any]) -> Response:
    events = create_chat_completion_stream(
        proxy_service,
        payload,
        completion_id=generate_completion_id(),
        created_at=int(time()),
        seed_factory=default_seed,
    )
    return Response(
        "".join(events),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _is_stream_request(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("stream"))


if __name__ == "__main__":
    raise SystemExit(main())
