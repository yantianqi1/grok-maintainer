from __future__ import annotations

from dataclasses import dataclass
import html
import json
import re
from typing import Any

import requests


@dataclass(frozen=True)
class LivewireContext:
    csrf_token: str
    update_uri: str
    component_id: str
    snapshot: str


def parse_livewire_context(page_html: str, component_name: str) -> LivewireContext:
    csrf_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', page_html)
    update_match = re.search(r'data-update-uri="([^"]+)"', page_html)
    component_match = re.search(
        rf'wire:snapshot="([^"]+)"[^>]*wire:id="([^"]+)"[^>]*wire:name="{re.escape(component_name)}"',
        page_html,
    )
    if csrf_match is None or update_match is None or component_match is None:
        raise RuntimeError(f"未能解析页面里的 Livewire 上下文: {component_name}")
    return LivewireContext(
        csrf_token=csrf_match.group(1),
        update_uri=update_match.group(1),
        component_id=component_match.group(2),
        snapshot=html.unescape(component_match.group(1)),
    )


def build_livewire_payload(
    *,
    csrf_token: str,
    snapshot: str,
    updates: dict[str, Any],
    method: str,
) -> dict[str, Any]:
    return {
        "_token": csrf_token,
        "components": [
            {
                "snapshot": snapshot,
                "updates": updates,
                "calls": [{"path": "", "method": method, "params": []}],
            }
        ],
    }


def parse_livewire_redirect(response_text: str) -> str:
    body = json.loads(response_text)
    redirect = body["components"][0]["effects"].get("redirect")
    if not redirect:
        raise RuntimeError("Livewire 响应里没有 redirect")
    return str(redirect)


def normalize_created_api_key(created_key: str) -> str:
    value = str(created_key).strip()
    if not value:
        raise RuntimeError("createdKey 为空")
    _, separator, suffix = value.partition("|")
    return suffix if separator and suffix else value


def parse_created_api_key(response_text: str) -> str:
    body = json.loads(response_text)
    snapshot = body["components"][0]["snapshot"]
    created_key = json.loads(snapshot)["data"].get("createdKey")
    if not created_key:
        raise RuntimeError("Livewire 响应里没有 createdKey")
    return normalize_created_api_key(str(created_key))


class DeapiClient:
    def __init__(
        self,
        base_url: str = "https://deapi.ai",
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def register(self, name: str, email: str, password: str) -> str:
        context = self._load_context("/register", "auth.register")
        response = self._post_livewire(
            path="/register",
            context=context,
            updates={
                "name": name,
                "email": email,
                "password": password,
                "password_confirmation": password,
            },
            method="register",
        )
        return parse_livewire_redirect(response.text)

    def verify_email(self, verify_link: str) -> str:
        response = self.session.get(verify_link, allow_redirects=True, timeout=30)
        if "/dashboard" not in response.url:
            raise RuntimeError(f"验证邮箱后未进入 dashboard: {response.url}")
        return response.url

    def create_api_key(self, key_name: str) -> str:
        context = self._load_context("/settings/api-keys", "settings.api-keys")
        response = self._post_livewire(
            path="/settings/api-keys",
            context=context,
            updates={
                "showCreateModal": True,
                "keyName": key_name,
                "createdKey": None,
                "showCreatedKeyModal": False,
                "showDeactivateModal": False,
                "tokenToDeactivate": None,
            },
            method="createKey",
        )
        return parse_created_api_key(response.text)

    def _load_context(self, path: str, component_name: str) -> LivewireContext:
        response = self.session.get(f"{self.base_url}{path}", timeout=30)
        response.raise_for_status()
        return parse_livewire_context(response.text, component_name)

    def _post_livewire(
        self,
        *,
        path: str,
        context: LivewireContext,
        updates: dict[str, Any],
        method: str,
    ) -> requests.Response:
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "X-CSRF-TOKEN": context.csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "X-Livewire": "true",
            "Referer": f"{self.base_url}{path}",
            "Origin": self.base_url,
        }
        payload = build_livewire_payload(
            csrf_token=context.csrf_token,
            snapshot=context.snapshot,
            updates=updates,
            method=method,
        )
        response = self.session.post(context.update_uri, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response
