# deAPI OpenAI Image Proxy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为仓库新增一个 OpenAI Images 兼容中转服务，将 deAPI 的异步 `txt2img` 结果转换成固定 `b64_json` 响应。

**Architecture:** 使用 Flask 暴露 `POST /v1/images/generations`，用独立配置模块加载 `image_proxy` 配置和上游 key 文件，用线程安全的轮询 key 池分配请求初始 key，用 deAPI 网关模块完成提交、轮询和下载。

**Tech Stack:** Python 3, Flask, requests, unittest, dataclasses, base64

---

### Task 1: Add Failing Tests For Config And Key Rotation

**Files:**
- Create: `tests/test_image_proxy_config.py`
- Create: `tests/test_deapi_key_pool.py`
- Create: `image_proxy_config.py`
- Create: `deapi_key_pool.py`

**Step 1: Write the failing test**

编写测试覆盖：

- 从 `config.json` 风格对象中读取 `image_proxy` 配置
- 从 key 文件读取多行 deAPI keys
- key 池按请求粒度 round-robin 返回尝试顺序
- 空 key 文件直接报错

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_image_proxy_config tests.test_deapi_key_pool -v`
Expected: FAIL because modules do not exist yet

**Step 3: Write minimal implementation**

实现：

- `ImageProxySettings`
- `load_image_proxy_settings(...)`
- `load_upstream_api_keys(...)`
- `RoundRobinApiKeyPool.reserve_attempt_order()`

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_image_proxy_config tests.test_deapi_key_pool -v`
Expected: PASS

### Task 2: Add Failing Tests For Proxy Service

**Files:**
- Create: `tests/test_image_proxy_service.py`
- Create: `deapi_image_gateway.py`
- Create: `openai_image_proxy.py`

**Step 1: Write the failing test**

编写测试覆盖：

- OpenAI 风格请求被正确映射到 deAPI 参数
- 提交阶段失败时会切下一把 key
- 成功拿到 `request_id` 后只用该 key 轮询
- 最终返回 OpenAI 风格 `b64_json`
- `response_format != b64_json` 和 `n != 1` 时直接报错

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_image_proxy_service -v`
Expected: FAIL because service code does not exist yet

**Step 3: Write minimal implementation**

实现：

- OpenAI 请求解析
- OpenAI 响应组装
- deAPI 提交/轮询/下载网关
- 按“提交阶段可切 key，受理后固定 key”执行的代理服务

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_image_proxy_service -v`
Expected: PASS

### Task 3: Add Failing Tests For Flask Endpoint

**Files:**
- Create: `tests/test_image_proxy_server.py`
- Create: `image_proxy_server.py`
- Modify: `requirements.txt`

**Step 1: Write the failing test**

编写 Flask 接口测试，验证：

- `POST /v1/images/generations` 返回 200 和 `b64_json`
- 业务层异常转换成 JSON 错误响应

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_image_proxy_server -v`
Expected: FAIL because Flask app does not exist yet

**Step 3: Write minimal implementation**

实现：

- Flask app factory
- 路由 `POST /v1/images/generations`
- 配置加载
- 服务实例装配
- CLI 启动入口

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_image_proxy_server -v`
Expected: PASS

### Task 4: Verify Docs And Full Suite

**Files:**
- Modify: `config.json`
- Modify: `readme.md`
- Create: `api_keys/upstream_deapi_keys.example.txt`

**Step 1: Update docs and sample config**

补充：

- `image_proxy` 配置段
- 上游 key 文件示例
- 启动方式和请求示例

**Step 2: Run full test suite**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS

**Step 3: Run import smoke check**

Run: `python3 -c "from image_proxy_server import create_app; print('ok')"`
Expected: `ok`
