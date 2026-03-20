# Chat Completions Image Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增 `POST /v1/chat/completions` 到现有图片代理的兼容层，让只支持 Chat Completion API 的客户端也能触发生图。

**Architecture:** 新建独立兼容模块处理消息提取、随机 seed、Markdown data URL 和 SSE chunk 构造，路由层只负责分发到现有图片服务并返回 OpenAI 风格的 chat completion 响应。

**Tech Stack:** Python 3, Flask, unittest, json, secrets

---

### Task 1: Add Failing Tests For Chat Compatibility Module

**Files:**
- Create: `tests/test_chat_completions_compat.py`
- Create: `chat_completions_compat.py`

**Step 1: Write the failing test**

编写测试覆盖：

- 从 `messages` 提取 prompt
- 顶层 `prompt` 优先
- 未传 `seed` 时自动生成
- 非流式 completion 返回 Markdown 图片
- SSE chunk 正确收尾

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_chat_completions_compat -v`
Expected: FAIL because module does not exist yet

**Step 3: Write minimal implementation**

实现：

- prompt 提取
- 随机 seed
- completion 结果包装
- SSE chunk 序列化

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_chat_completions_compat -v`
Expected: PASS

### Task 2: Add Failing Route Tests

**Files:**
- Modify: `tests/test_image_proxy_server.py`
- Modify: `image_proxy_server.py`

**Step 1: Write the failing test**

编写测试覆盖：

- `POST /v1/chat/completions` 非流式返回 200
- `POST /v1/chat/completions` 流式返回 SSE 和 `[DONE]`
- 缺少 prompt 返回结构化错误

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_image_proxy_server -v`
Expected: FAIL because route does not exist yet

**Step 3: Write minimal implementation**

实现：

- `POST /v1/chat/completions`
- 兼容 `stream: true`
- 调用现有图片服务

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_image_proxy_server -v`
Expected: PASS

### Task 3: Verify Real HTTP Behavior

**Files:**
- Modify: `readme.md`

**Step 1: Update docs**

补充：

- `chat/completions` 兼容说明
- `messages -> 图片 Markdown` 行为

**Step 2: Run full test suite**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS

**Step 3: Run live HTTP verification**

Run: real POST requests against `http://127.0.0.1:8787/v1/chat/completions`
Expected: non-stream and stream both return compatible responses
