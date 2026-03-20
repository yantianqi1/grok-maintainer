# deAPI API Key Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将主脚本改造成 deAPI 注册、邮箱验证、创建并导出 API key 的自动化工具。

**Architecture:** 用 `requests.Session` + Livewire 协议完成 deAPI 站点动作，用 GPTMail 替换旧 Worker 邮箱，保留原有 CLI 入口与批量执行方式。

**Tech Stack:** Python 3, requests, unittest, regex/json/html parsing

---

### Task 1: Add Failing Parser And Mail Tests

**Files:**
- Create: `tests/test_deapi_client.py`
- Create: `tests/test_gptmail_client.py`

**Step 1: Write the failing tests**

编写测试覆盖：

- 从 deAPI HTML 解析 `csrf-token`、`update-uri`、指定 `wire:name` 的 `snapshot`
- 从 GPTMail 邮件详情里提取直接的 `https://deapi.ai/verify-email/...` 链接
- 从 `createKey` 响应里提取 `createdKey`

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_deapi_client.py'`

Expected: FAIL because module/functions do not exist yet

**Step 3: Write minimal implementation**

创建：

- `deapi_client.py`
- `gptmail_client.py`

只实现让测试通过的解析与请求组装函数。

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_deapi_client.py'`

Expected: PASS

### Task 2: Implement Workflow Layer

**Files:**
- Create: `deapi_workflow.py`
- Modify: `gptmail_client.py`
- Modify: `deapi_client.py`
- Create: `tests/test_deapi_workflow.py`

**Step 1: Write the failing tests**

编写工作流测试，验证：

- 单轮流程会先生成邮箱，再注册，再轮询邮件，再验证，再创建 key
- 成功后把 key 追加到输出文件

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_deapi_workflow.py'`

Expected: FAIL because workflow does not exist yet

**Step 3: Write minimal implementation**

在 `deapi_workflow.py` 中实现：

- `run_single_deapi_registration(...)`
- 输出文件追加函数

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_deapi_workflow.py'`

Expected: PASS

### Task 3: Replace Main Script Entry

**Files:**
- Modify: `DrissionPage_example.py`
- Modify: `tests/test_target_urls.py`

**Step 1: Write the failing test**

调整现有入口测试，验证：

- CLI 仍支持 `--count` 和 `--output`
- 单轮逻辑返回 API key，不再依赖 `SIGNUP_URL` 或 `sso`

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_target_urls.py'`

Expected: FAIL because old assumptions still exist

**Step 3: Write minimal implementation**

将 [`DrissionPage_example.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/DrissionPage_example.py) 改为轻量 CLI 包装层：

- 读取 `run.count`
- 调用 `run_single_deapi_registration`
- 批量写输出

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_target_urls.py'`

Expected: PASS

### Task 4: Verify Full Test Suite

**Files:**
- Modify: `readme.md`

**Step 1: Update docs**

把 README 从 `x.ai/sso` 改成 deAPI + GPTMail + API key 导出说明。

**Step 2: Run all tests**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`

Expected: PASS

**Step 3: Run real verification**

Run: `python3 DrissionPage_example.py --count 1`

Expected: 成功注册、验证、创建并导出一个 API key
