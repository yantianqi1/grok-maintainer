from __future__ import annotations

import html
import re
import time
from typing import Any, Iterable

import requests


VERIFY_LINK_PATTERN = re.compile(r"https://deapi\.ai/verify-email/[^\s\"'<>]+")


def _message_content(message: dict[str, Any]) -> str:
    html_body = str(message.get("html_content") or "")
    text_body = str(message.get("content") or "")
    return html.unescape(f"{html_body}\n{text_body}")


def extract_deapi_verify_link(messages: Iterable[dict[str, Any]]) -> str:
    for message in messages:
        match = VERIFY_LINK_PATTERN.search(_message_content(message))
        if match is not None:
            return match.group(0)
    raise RuntimeError("未找到 deAPI 邮箱验证链接")


class GptMailClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://mail.chatgpt.org.uk",
        session: requests.Session | None = None,
    ) -> None:
        if not api_key:
            raise RuntimeError("GPTMail API key 为空")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    def generate_email(self, prefix: str | None = None, domain: str | None = None) -> str:
        if prefix or domain:
            payload = {}
            if prefix:
                payload["prefix"] = prefix
            if domain:
                payload["domain"] = domain
            response = self.session.post(
                f"{self.base_url}/api/generate-email",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
        else:
            response = self.session.get(
                f"{self.base_url}/api/generate-email",
                headers=self._headers(),
                timeout=30,
            )
        data = self._json(response)
        return str(data["data"]["email"])

    def list_emails(self, email: str) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base_url}/api/emails",
            params={"email": email},
            headers=self._headers(),
            timeout=30,
        )
        data = self._json(response)
        emails = data["data"]["emails"]
        if not isinstance(emails, list):
            raise RuntimeError("GPTMail 返回的邮件列表格式错误")
        return emails

    def get_email(self, email_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/api/email/{email_id}",
            headers=self._headers(),
            timeout=30,
        )
        data = self._json(response)
        detail = data["data"]
        if not isinstance(detail, dict):
            raise RuntimeError("GPTMail 返回的邮件详情格式错误")
        return detail

    def wait_for_verify_link(self, email: str, timeout: int = 120, interval: int = 3) -> str:
        start = time.time()
        while time.time() - start < timeout:
            emails = self.list_emails(email)
            if emails:
                details = [self.get_email(str(item["id"])) for item in emails]
                try:
                    return extract_deapi_verify_link(details)
                except RuntimeError:
                    pass
            time.sleep(interval)
        raise RuntimeError("等待 deAPI 验证邮件超时")

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not data.get("success"):
            raise RuntimeError(f"GPTMail 请求失败: {data}")
        return data
