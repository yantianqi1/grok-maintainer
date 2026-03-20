# Admin Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 deAPI 图片中转服务新增一个带 SQLite 和简单登录保护的管理员后台，并让运行时 key 池改为从数据库读取。

**Architecture:** 使用 `sqlite3` 建立管理员与上游 key 数据表，用独立存储层封装账号校验与 key 管理，用 Flask 模板渲染登录页和后台主页，并让图片服务通过数据库驱动的轮询 key 池读取启用 key 与回写错误统计。

**Tech Stack:** Python 3, Flask, Jinja2, sqlite3, werkzeug.security, unittest

---

### Task 1: Add Failing Tests For SQLite Admin Store

**Files:**
- Create: `tests/test_admin_store.py`
- Create: `admin_store.py`

**Step 1: Write the failing test**

编写测试覆盖：

- 初始化管理员账号并校验密码
- 批量添加 key 并跳过重复项
- 启用/禁用、删除 key
- 记录错误次数与最近使用时间

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_admin_store -v`
Expected: FAIL because `admin_store.py` does not exist yet

**Step 3: Write minimal implementation**

实现：

- `AdminStore`
- `ManagedApiKey`
- `DashboardStats`
- `BulkAddResult`

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_admin_store -v`
Expected: PASS

### Task 2: Add Failing Tests For Key Pool And Proxy Tracking

**Files:**
- Create: `managed_key_pool.py`
- Modify: `openai_image_proxy.py`
- Modify: `tests/test_image_proxy_service.py`

**Step 1: Write the failing test**

编写测试覆盖：

- 数据库驱动的 key 池只返回启用 key
- 图片服务在提交失败时记录错误次数
- 图片服务在成功时记录最后使用时间

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_image_proxy_service -v`
Expected: FAIL because tracking behavior does not exist yet

**Step 3: Write minimal implementation**

实现：

- `ManagedApiKeyPool`
- `OpenAIImageProxyService` 的 key 记录与回写

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_image_proxy_service -v`
Expected: PASS

### Task 3: Add Failing Tests For Admin Routes

**Files:**
- Create: `tests/test_admin_views.py`
- Create: `admin_views.py`
- Create: `templates/admin_login.html`
- Create: `templates/admin_dashboard.html`
- Create: `static/admin.css`

**Step 1: Write the failing test**

编写测试覆盖：

- 未登录访问 `/admin` 会跳转 `/admin/login`
- 正确账号密码可以登录
- 批量添加、启用/禁用、删除可以通过表单完成
- 后台页面能看到统计与错误次数

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_admin_views -v`
Expected: FAIL because admin routes and templates do not exist yet

**Step 3: Write minimal implementation**

实现：

- 管理后台 blueprint
- session 登录保护
- 登录页与控制台模板
- 管理操作路由

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_admin_views -v`
Expected: PASS

### Task 4: Integrate Runtime Config And App Factory

**Files:**
- Modify: `image_proxy_config.py`
- Modify: `image_proxy_server.py`
- Modify: `tests/test_image_proxy_server.py`

**Step 1: Write the failing test**

调整测试覆盖：

- `create_app(runtime=...)` 可注册管理员后台
- 图片接口旧行为保持不变

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_image_proxy_server -v`
Expected: FAIL because runtime integration does not exist yet

**Step 3: Write minimal implementation**

实现：

- 管理员配置读取
- 运行时装配 `AdminStore`、`ManagedApiKeyPool`、图片服务和后台 blueprint

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_image_proxy_server -v`
Expected: PASS

### Task 5: Update Docs And Verify Full Suite

**Files:**
- Modify: `config.json`
- Modify: `readme.md`

**Step 1: Update docs**

补充：

- SQLite 管理后台配置
- 管理员密码环境变量
- 登录入口
- 批量导入 key 的格式说明

**Step 2: Run full test suite**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS

**Step 3: Run import smoke check**

Run: `python3 -c "from image_proxy_server import create_app; print('ok')"`
Expected: `ok`
