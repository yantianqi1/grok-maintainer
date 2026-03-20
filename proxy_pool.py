from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote


PROXY_PART_COUNT = 4
ROUND_ROBIN = "round_robin"


@dataclass(frozen=True)
class ProxyEntry:
    host: str
    port: int
    username: str
    password: str

    def proxy_url(self) -> str:
        encoded_user = quote(self.username, safe="")
        encoded_password = quote(self.password, safe="")
        return f"socks5h://{encoded_user}:{encoded_password}@{self.host}:{self.port}"

    def requests_proxies(self) -> dict[str, str]:
        proxy_url = self.proxy_url()
        return {"http": proxy_url, "https": proxy_url}

    def masked_display(self) -> str:
        return f"{self.host}:{self.port}:{self.username}:***"


def parse_proxy_entry(raw_value: str) -> ProxyEntry:
    parts = str(raw_value).strip().split(":", maxsplit=PROXY_PART_COUNT - 1)
    if len(parts) != PROXY_PART_COUNT:
        raise RuntimeError(f"代理配置格式错误，应为 host:port:username:password，实际: {raw_value}")

    host, port_text, username, password = parts
    if not host or not username or not password:
        raise RuntimeError(f"代理配置存在空字段: {raw_value}")

    try:
        port = int(port_text)
    except ValueError as error:
        raise RuntimeError(f"代理端口不是整数: {port_text}") from error

    if port <= 0:
        raise RuntimeError(f"代理端口必须大于 0: {port_text}")

    return ProxyEntry(host=host, port=port, username=username, password=password)


class ProxyPool:
    def __init__(self, entries: Iterable[ProxyEntry], strategy: str = ROUND_ROBIN) -> None:
        self._entries = tuple(entries)
        self._strategy = strategy
        self._index = 0
        if self._strategy != ROUND_ROBIN:
            raise RuntimeError(f"不支持的代理轮询策略: {self._strategy}")
        if not self._entries:
            raise RuntimeError("代理池为空，无法启用轮询")

    @classmethod
    def from_strings(
        cls,
        raw_entries: Iterable[str],
        strategy: str = ROUND_ROBIN,
    ) -> "ProxyPool":
        entries = tuple(parse_proxy_entry(item) for item in raw_entries)
        return cls(entries=entries, strategy=strategy)

    def next_proxy(self) -> ProxyEntry:
        entry = self._entries[self._index]
        self._index = (self._index + 1) % len(self._entries)
        return entry
