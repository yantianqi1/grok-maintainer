from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

from deapi_client import DeapiClient
from deapi_workflow import run_single_deapi_registration
from gptmail_client import GptMailClient
from proxy_pool import ProxyPool


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.json"
API_KEY_DIR = ROOT_DIR / "api_keys"
DEFAULT_OUTPUT_FILE = API_KEY_DIR / f"api_keys_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
DEFAULT_MAIL_API_KEY_ENV = "GPTMAIL_API_KEY"


def setup_run_logger() -> logging.Logger:
    log_dir = ROOT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logger = logging.getLogger("deapi_register")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("日志文件: %s", log_path)
    return logger


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError("config.json 顶层必须是对象")
    return data


def load_run_count(config: dict) -> int:
    value = config.get("run", {}).get("count", 10)
    if isinstance(value, int) and value >= 0:
        return value
    return 10


def load_mail_settings(config: dict) -> tuple[str, str, int, int]:
    mail_conf = config.get("mail", {})
    base_url = str(mail_conf.get("base_url", "https://mail.chatgpt.org.uk")).strip() or "https://mail.chatgpt.org.uk"
    api_key_env = str(mail_conf.get("api_key_env", DEFAULT_MAIL_API_KEY_ENV)).strip() or DEFAULT_MAIL_API_KEY_ENV
    api_key = os.environ.get(api_key_env, "").strip()
    timeout = int(mail_conf.get("timeout_sec", 120) or 120)
    interval = int(mail_conf.get("poll_interval_sec", 3) or 3)
    if not api_key:
        raise RuntimeError(f"缺少 GPTMail API key，请设置环境变量 {api_key_env}")
    return base_url, api_key, timeout, interval


def load_deapi_base_url(config: dict) -> str:
    deapi_conf = config.get("deapi", {})
    return str(deapi_conf.get("base_url", "https://deapi.ai")).strip() or "https://deapi.ai"


def load_proxy_pool(config: dict) -> ProxyPool | None:
    proxy_conf = config.get("proxy_pool", {})
    if not proxy_conf.get("enabled", False):
        return None

    strategy = str(proxy_conf.get("strategy", "round_robin")).strip() or "round_robin"
    raw_proxies = proxy_conf.get("proxies", [])
    if not isinstance(raw_proxies, list):
        raise RuntimeError("proxy_pool.proxies 必须是数组")
    return ProxyPool.from_strings(raw_proxies, strategy=strategy)


def create_session(proxy_mapping: dict[str, str] | None = None) -> requests.Session:
    session = requests.Session()
    if proxy_mapping is not None:
        session.proxies.update(proxy_mapping)
    return session


def create_clients_for_round(
    *,
    pool: ProxyPool | None,
    mail_api_key: str,
    mail_base_url: str,
    deapi_base_url: str,
) -> tuple[GptMailClient, DeapiClient, str]:
    proxy_mapping = None
    proxy_label = "direct"
    if pool is not None:
        proxy_entry = pool.next_proxy()
        proxy_mapping = proxy_entry.requests_proxies()
        proxy_label = proxy_entry.masked_display()

    mail_session = create_session(proxy_mapping)
    deapi_session = create_session(proxy_mapping)
    mail_client = GptMailClient(api_key=mail_api_key, base_url=mail_base_url, session=mail_session)
    deapi_client = DeapiClient(base_url=deapi_base_url, session=deapi_session)
    return mail_client, deapi_client, proxy_label


def mask_secret(secret: str) -> str:
    value = str(secret).strip()
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:8]}...{value[-4:]}"


def main(argv: list[str] | None = None) -> int:
    config = load_config()
    config_count = load_run_count(config)

    parser = argparse.ArgumentParser(description="deAPI 自动注册并导出 API key")
    parser.add_argument(
        "--count",
        type=int,
        default=config_count,
        help=f"执行轮数，0 表示无限循环（默认读取 config.json run.count，当前 {config_count}）",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_FILE), help="API key 输出 txt 路径")
    args = parser.parse_args(argv)

    logger = setup_run_logger()
    mail_base_url, mail_api_key, mail_timeout, poll_interval = load_mail_settings(config)
    deapi_base_url = load_deapi_base_url(config)
    proxy_pool = load_proxy_pool(config)

    current_round = 0
    while True:
        if args.count > 0 and current_round >= args.count:
            break

        current_round += 1
        print(f"\n[*] 开始第 {current_round} 轮注册")

        try:
            mail_client, deapi_client, proxy_label = create_clients_for_round(
                pool=proxy_pool,
                mail_api_key=mail_api_key,
                mail_base_url=mail_base_url,
                deapi_base_url=deapi_base_url,
            )
            logger.info("第 %s 轮代理: %s", current_round, proxy_label)
            result = run_single_deapi_registration(
                output_path=args.output,
                mail_client=mail_client,
                deapi_client=deapi_client,
                mail_timeout=mail_timeout,
                poll_interval=poll_interval,
            )
            logger.info("注册邮箱: %s", result["email"])
            logger.info("API key 已导出: %s", mask_secret(result["api_key"]))
            logger.info("Dashboard: %s", result["dashboard_url"])
            print(f"[*] 本轮成功，API key 已写入: {args.output}")
        except KeyboardInterrupt:
            print("\n[Info] 收到中断信号，停止后续轮次。")
            return 0
        except Exception as error:
            print(f"[Error] 第 {current_round} 轮失败: {error}")
            logger.exception("第 %s 轮失败", current_round)

        if args.count == 0 or current_round < args.count:
            time.sleep(2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
