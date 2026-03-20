# deAPI Proxy Pool Rotation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 deAPI 注册脚本增加 SOCKS5 代理池，并让每一轮注册固定绑定一个代理后按顺序轮询。

**Architecture:** 新增独立 `proxy_pool.py` 负责代理字符串解析、轮询和日志脱敏；主循环按轮次为 `GptMailClient` 与 `DeapiClient` 创建带同一代理配置的新 `requests.Session`。

**Tech Stack:** Python 3, requests, unittest

---

### Task 1: Add Failing Proxy Pool Tests

**Files:**
- Create: `tests/test_proxy_pool.py`
- Modify: `tests/test_deapi_client.py`

**Step 1: Write the failing test**

```python
def test_parse_proxy_entry_builds_socks5h_urls():
    entry = parse_proxy_entry(
        "gate.ipdeep.com:8082:user-name:secret-pass"
    )
    assert entry.host == "gate.ipdeep.com"
    assert entry.port == 8082
    assert entry.requests_proxies()["http"].startswith("socks5h://")


def test_round_robin_proxy_pool_cycles_entries():
    pool = ProxyPool.from_strings([
        "host1:1001:u1:p1",
        "host2:1002:u2:p2",
    ])
    assert pool.next_proxy().host == "host1"
    assert pool.next_proxy().host == "host2"
    assert pool.next_proxy().host == "host1"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_proxy_pool.py'`
Expected: FAIL because `proxy_pool.py` does not exist yet

**Step 3: Write minimal implementation**

创建 `proxy_pool.py`，实现：

- `ProxyEntry`
- `parse_proxy_entry`
- `ProxyPool`
- 代理脱敏展示

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_proxy_pool.py'`
Expected: PASS

### Task 2: Add Failing Main Loop Proxy Tests

**Files:**
- Modify: `tests/test_deapi_workflow.py`
- Create: `tests/test_main_proxy_pool.py`

**Step 1: Write the failing test**

```python
def test_create_clients_for_round_uses_proxy_on_both_sessions():
    config = {
        "proxy_pool": {
            "enabled": True,
            "strategy": "round_robin",
            "proxies": ["gate.ipdeep.com:8082:user:pass"],
        }
    }
    pool = load_proxy_pool(config)
    mail_client, deapi_client, masked = create_clients_for_round(
        pool=pool,
        mail_api_key="demo-key",
        mail_base_url="https://mail.example.com",
        deapi_base_url="https://deapi.ai",
    )
    assert mail_client.session.proxies["https"].startswith("socks5h://user:pass@")
    assert deapi_client.session.proxies["https"].startswith("socks5h://user:pass@")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_main_proxy_pool.py'`
Expected: FAIL because helper functions do not exist yet

**Step 3: Write minimal implementation**

在 `DrissionPage_example.py` 中实现：

- `load_proxy_pool(config)`
- `create_clients_for_round(...)`
- 主循环中的按轮次代理日志

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_main_proxy_pool.py'`
Expected: PASS

### Task 3: Update Runtime Docs And Dependencies

**Files:**
- Modify: `config.json`
- Modify: `readme.md`
- Modify: `requirements.txt`

**Step 1: Update docs/config**

补充：

- `proxy_pool` 配置结构
- SOCKS5 代理格式说明
- `requests[socks]` 依赖说明

**Step 2: Run targeted tests**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS

**Step 3: Manual runtime check**

Run: `python3 DrissionPage_example.py --count 1`
Expected: 启用代理池时日志输出当前轮代理脱敏信息，并继续执行注册流程
