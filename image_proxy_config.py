from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8787
DEFAULT_POLL_INTERVAL_SEC = 2
DEFAULT_POLL_TIMEOUT_SEC = 180
DEFAULT_SUBMIT_TIMEOUT_SEC = 30
DEFAULT_DOWNLOAD_TIMEOUT_SEC = 60
DEFAULT_MODEL = "ZImageTurbo_INT8"
DEFAULT_SIZE = "768x768"
DEFAULT_UPSTREAM_KEY_FILE = "api_keys/upstream_deapi_keys.txt"
DEFAULT_DATABASE_PATH = "data/image_proxy.sqlite3"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD_ENV = "IMAGE_PROXY_ADMIN_PASSWORD"
DEFAULT_SESSION_SECRET_ENV = "IMAGE_PROXY_SESSION_SECRET"


@dataclass(frozen=True)
class ImageProxySettings:
    host: str
    port: int
    poll_interval_sec: int
    poll_timeout_sec: int
    submit_timeout_sec: int
    download_timeout_sec: int
    default_model: str
    default_size: str
    upstream_base_url: str
    upstream_key_file: Path


@dataclass(frozen=True)
class AdminSettings:
    database_path: Path
    username: str
    password: str
    session_secret: str


def load_image_proxy_settings(config: Mapping[str, object], root_dir: Path) -> ImageProxySettings:
    proxy_conf = _read_mapping(config, "image_proxy")
    key_path = _resolve_key_file(proxy_conf.get("upstream_key_file"), root_dir)
    return ImageProxySettings(
        host=_read_string(proxy_conf.get("host"), DEFAULT_HOST),
        port=_read_int(proxy_conf.get("port"), DEFAULT_PORT),
        poll_interval_sec=_read_int(proxy_conf.get("poll_interval_sec"), DEFAULT_POLL_INTERVAL_SEC),
        poll_timeout_sec=_read_int(proxy_conf.get("poll_timeout_sec"), DEFAULT_POLL_TIMEOUT_SEC),
        submit_timeout_sec=_read_int(proxy_conf.get("submit_timeout_sec"), DEFAULT_SUBMIT_TIMEOUT_SEC),
        download_timeout_sec=_read_int(proxy_conf.get("download_timeout_sec"), DEFAULT_DOWNLOAD_TIMEOUT_SEC),
        default_model=_read_string(proxy_conf.get("default_model"), DEFAULT_MODEL),
        default_size=_read_string(proxy_conf.get("default_size"), DEFAULT_SIZE),
        upstream_base_url=_read_string(proxy_conf.get("upstream_base_url"), "https://api.deapi.ai"),
        upstream_key_file=key_path,
    )


def load_admin_settings(config: Mapping[str, object], root_dir: Path) -> AdminSettings:
    admin_conf = _read_mapping(config, "admin")
    password_env = _read_string(admin_conf.get("password_env"), DEFAULT_ADMIN_PASSWORD_ENV)
    session_secret_env = _read_string(
        admin_conf.get("session_secret_env"),
        DEFAULT_SESSION_SECRET_ENV,
    )
    password = _read_env(password_env)
    session_secret = _read_env(session_secret_env)
    return AdminSettings(
        database_path=_resolve_database_path(admin_conf.get("database_path"), root_dir),
        username=_read_string(admin_conf.get("username"), DEFAULT_ADMIN_USERNAME),
        password=password,
        session_secret=session_secret,
    )


def load_upstream_api_keys(settings: ImageProxySettings) -> tuple[str, ...]:
    if not settings.upstream_key_file.exists():
        raise RuntimeError(f"上游 key 文件不存在: {settings.upstream_key_file}")
    raw_lines = settings.upstream_key_file.read_text(encoding="utf-8").splitlines()
    keys = tuple(line.strip() for line in raw_lines if line.strip())
    if not keys:
        raise RuntimeError("没有可用的 deAPI API key")
    return keys


def _read_mapping(config: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = config.get(key, {})
    if isinstance(value, Mapping):
        return value
    raise RuntimeError(f"{key} 必须是对象")


def _read_string(value: object, default: str) -> str:
    text = default if value is None else str(value).strip()
    return text or default


def _read_int(value: object, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _resolve_key_file(value: object, root_dir: Path) -> Path:
    raw_path = _read_string(value, DEFAULT_UPSTREAM_KEY_FILE)
    path = Path(raw_path)
    return path if path.is_absolute() else root_dir / path


def _resolve_database_path(value: object, root_dir: Path) -> Path:
    raw_path = _read_string(value, DEFAULT_DATABASE_PATH)
    path = Path(raw_path)
    return path if path.is_absolute() else root_dir / path


def _read_env(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    raise RuntimeError(f"缺少环境变量 {env_name}")
