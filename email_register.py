
from __future__ import annotations

import json
import logging
import random
import re
import string
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import aiohttp
except Exception:
    aiohttp = None

# ============================================================
# 适配层：为 DrissionPage_example.py 提供简单接口
# ============================================================

_temp_email_cache: Dict[str, str] = {}


def get_email_and_token() -> Tuple[Optional[str], Optional[str]]:
    """
    创建临时邮箱并返回 (email, admin_token)。

    供 DrissionPage_example.py 调用，用于 Grok 注册。
    使用配置文件中的 email 相关设置创建临时邮箱。

    Returns:
        (email, admin_token) 或 (None, None) 如果失败
    """
    import json

    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print(f"[Error] 配置文件不存在：{config_path}")
        return None, None

    conf = load_json(config_path)

    worker_domain = str(pick_conf(conf, "email", "worker_domain", default="") or "")
    admin_password = str(pick_conf(conf, "email", "admin_password", default="") or "")
    email_domains = pick_conf(conf, "email", "email_domains", default=None)
    if not isinstance(email_domains, list):
        old_domain = str(pick_conf(conf, "email", "email_domain", default="tuxixilax.cfd") or "tuxixilax.cfd")
        email_domains = [old_domain]
    else:
        email_domains = [str(x).strip() for x in email_domains if str(x).strip()]

    if not worker_domain or not admin_password:
        print("[Error] 配置缺少 email.worker_domain 或 email.admin_password")
        return None, None

    session = create_session()
    email, token = create_temp_email(
        session=session,
        worker_domain=worker_domain,
        email_domains=email_domains,
        admin_password=admin_password,
        logger=logging.getLogger("openai_register"),
    )

    if email and token:
        _temp_email_cache[email] = token
        return email, token

    return None, None


def get_oai_code(dev_token: str, email: str, timeout: int = 120) -> Optional[str]:
    """
    轮询临时邮箱获取 OTP 验证码。

    供 DrissionPage_example.py 调用，用于 Grok 注册验证码。

    Args:
        dev_token: 临时邮箱的 JWT token
        email: 邮箱地址
        timeout: 超时秒数

    Returns:
        验证码字符串（去除连字符，如 "MM0SF3"）或 None
    """
    import json

    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print(f"[Error] 配置文件不存在：{config_path}")
        return None

    conf = load_json(config_path)
    worker_domain = str(pick_conf(conf, "email", "worker_domain", default="") or "")

    if not worker_domain:
        print("[Error] 配置缺少 email.worker_domain")
        return None

    session = create_session()

    code = wait_for_verification_code(
        session=session,
        worker_domain=worker_domain,
        cf_token=dev_token,
        timeout=timeout,
    )

    if code:
        # 去除连字符，将 "MM0-SF3" 转为 "MM0SF3"
        code = code.replace("-", "")

    return code

def wait_for_verification_code(
    session: requests.Session,
    worker_domain: str,
    cf_token: str,
    timeout: int = 120,
) -> Optional[str]:
    old_ids = set()
    old = fetch_emails(session, worker_domain, cf_token)
    if old:
        old_ids = {e.get("id") for e in old if isinstance(e, dict) and "id" in e}
        for item in old:
            if not isinstance(item, dict):
                continue
            raw = str(item.get("raw") or "")
            code = extract_verification_code(raw)
            if code:
                return code

    start = time.time()
    while time.time() - start < timeout:
        emails = fetch_emails(session, worker_domain, cf_token)
        if emails:
            for item in emails:
                if not isinstance(item, dict):
                    continue
                if item.get("id") in old_ids:
                    continue
                raw = str(item.get("raw") or "")
                code = extract_verification_code(raw)
                if code:
                    return code
        time.sleep(3)
    return None


def create_session(proxy: str = "") -> requests.Session:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"配置文件格式错误，顶层必须是对象: {path}")
    return data


def create_temp_email(
    session: requests.Session,
    worker_domain: str,
    email_domains: List[str],
    admin_password: str,
    logger: logging.Logger,
) -> tuple[Optional[str], Optional[str]]:
    name_len = random.randint(10, 14)
    name_chars = list(random.choices(string.ascii_lowercase, k=name_len))
    for _ in range(random.choice([1, 2])):
        pos = random.randint(2, len(name_chars) - 1)
        name_chars.insert(pos, random.choice(string.digits))
    name = "".join(name_chars)

    chosen_domain = random.choice(email_domains) if email_domains else "tuxixilax.cfd"

    try:
        res = session.post(
            f"https://{worker_domain}/admin/new_address",
            json={"enablePrefix": True, "name": name, "domain": chosen_domain},
            headers={"x-admin-auth": admin_password, "Content-Type": "application/json"},
            timeout=10,
            verify=False,
        )
        if res.status_code == 200:
            data = res.json()
            email = data.get("address")
            token = data.get("jwt")
            if email:
                logger.info("创建临时邮箱成功: %s (domain=%s)", email, chosen_domain)
                return str(email), str(token or "")
        logger.warning("创建临时邮箱失败: HTTP %s", res.status_code)
    except Exception as e:
        logger.warning("创建临时邮箱异常: %s", e)
    return None, None



def pick_conf(root: Dict[str, Any], section: str, key: str, *legacy_keys: str, default: Any = None) -> Any:
    sec = root.get(section)
    if not isinstance(sec, dict):
        sec = {}

    v = sec.get(key)
    if v is None:
        for lk in legacy_keys:
            v = sec.get(lk)
            if v is not None:
                break
    if v is not None:
        return v

    v = root.get(key)
    if v is None:
        for lk in legacy_keys:
            v = root.get(lk)
            if v is not None:
                break
    if v is not None:
        return v
    return default


def fetch_emails(session: requests.Session, worker_domain: str, cf_token: str) -> List[Dict[str, Any]]:
    try:
        res = session.get(
            f"https://{worker_domain}/api/mails",
            params={"limit": 10, "offset": 0},
            headers={"Authorization": f"Bearer {cf_token}"},
            verify=False,
            timeout=30,
        )
        if res.status_code == 200:
            rows = res.json().get("results", [])
            return rows if isinstance(rows, list) else []
    except Exception:
        pass
    return []


def extract_verification_code(content: str) -> Optional[str]:
    """
    从邮件原始内容中提取验证码。

    Grok/x.ai 验证码格式可能是：
    - 6 位纯数字：123456
    - 字母数字混合：MM0-SF3、AB1-CD2 等

    优先匹配 Grok 邮件格式，按优先级尝试多种模式。
    """
    if not content:
        return None

    # 模式 1: Grok 格式 - 类似 "MM0-SF3" 的 6 字符验证码（3 位 + 连字符 + 3 位）
    # 注意：邮件纯文本中验证码后可能紧跟其他文字（无空格），不能用 \b
    m = re.search(r"(?<![A-Z0-9-])([A-Z0-9]{3}-[A-Z0-9]{3})(?![A-Z0-9-])", content)
    if m:
        return m.group(1)

    # 模式 2: Grok 邮件常见格式 - 查找类似 "Verification code: XXX" 或 "验证码：XXX"
    m = re.search(r"(?:verification code|验证码|your code|您的验证码)[:\s]*[<>\s]*([A-Z0-9]{3}-[A-Z0-9]{3})\b", content, re.IGNORECASE)
    if m:
        return m.group(1)

    # 模式 3: 查找被样式包裹的验证码（常见于 HTML 邮件）
    m = re.search(r"background-color:\s*#F3F3F3[^>]*>[\s\S]*?([A-Z0-9]{3}-[A-Z0-9]{3})[\s\S]*?</p>", content)
    if m:
        return m.group(1)

    # 模式 4: 从主题行提取（6 位数字）
    m = re.search(r"Subject:.*?(\d{6})", content)
    if m:
        code = m.group(1)
        if code != "177010":
            return code

    # 模式 5: 查找 HTML 标签内的 6 位数字
    for code in re.findall(r">\s*(\d{6})\s*<", content):
        if code != "177010":
            return code

    # 模式 6: 查找独立的 6 位数字（排除 URL 编码和 HTML 实体）
    for code in re.findall(r"(?<![&#\d])(\d{6})(?![&#\d])", content):
        if code != "177010":
            return code

    return None
