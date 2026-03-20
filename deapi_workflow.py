from __future__ import annotations

from pathlib import Path
import secrets


def append_api_key(api_key: str, output_path: str | Path) -> None:
    normalized = str(api_key).strip()
    if not normalized:
        raise RuntimeError("待写入的 API key 为空")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{normalized}\n")


def generate_password() -> str:
    return f"Deapi!{secrets.token_urlsafe(12)}"


def generate_api_key_name() -> str:
    return f"codex-{secrets.token_hex(4)}"


def run_single_deapi_registration(
    *,
    output_path: str | Path,
    mail_client,
    deapi_client,
    account_name: str = "deapi test",
    password: str | None = None,
    api_key_name: str | None = None,
    mail_timeout: int = 120,
    poll_interval: int = 3,
) -> dict[str, str]:
    email = mail_client.generate_email()
    actual_password = password or generate_password()
    actual_key_name = api_key_name or generate_api_key_name()

    redirect = deapi_client.register(account_name, email, actual_password)
    if redirect != "/verify-email":
        raise RuntimeError(f"注册后跳转异常: {redirect}")

    verify_link = mail_client.wait_for_verify_link(
        email,
        timeout=mail_timeout,
        interval=poll_interval,
    )
    dashboard_url = deapi_client.verify_email(verify_link)
    api_key = deapi_client.create_api_key(actual_key_name)
    append_api_key(api_key, output_path)

    return {
        "email": email,
        "password": actual_password,
        "api_key_name": actual_key_name,
        "api_key": api_key,
        "dashboard_url": dashboard_url,
        "output_path": str(output_path),
    }
