# Admin Key Console Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为上游 Key 控制台增加中文紧凑布局、成功调用次数、筛选和批量操作能力。

**Architecture:** 在 SQLite 存储层新增 `success_count` 与过滤/批量更新接口；在 Flask 管理路由层新增筛选与批量操作入口；在模板和样式层改为紧凑中文控制台布局并增加复选框、筛选条和批量操作区。

**Tech Stack:** Python, Flask, SQLite, Jinja2, CSS, unittest

---

### Task 1: 扩展后台存储模型

**Files:**
- Create: `admin_models.py`
- Modify: `admin_store.py`
- Test: `tests/test_admin_store.py`

**Step 1: Write the failing test**

在 `tests/test_admin_store.py` 新增测试，覆盖：

- `record_key_success()` 会递增 `success_count`
- `list_api_keys(filter_name=...)` 能按 `enabled/disabled/error/unused` 过滤
- `apply_bulk_action()` 能批量启用、禁用和删除

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_admin_store -v`
Expected: FAIL，提示缺少 `success_count`、筛选或批量操作实现

**Step 3: Write minimal implementation**

- 新建 `admin_models.py` 放置数据类
- 在 `upstream_api_keys` 表中补齐 `success_count`
- 在 `record_key_success()` 中递增成功次数
- 为 `AdminStore` 新增筛选与批量操作接口

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_admin_store -v`
Expected: PASS

### Task 2: 扩展管理后台路由

**Files:**
- Modify: `admin_views.py`
- Test: `tests/test_admin_views.py`

**Step 1: Write the failing test**

在 `tests/test_admin_views.py` 新增测试，覆盖：

- `/admin?filter=unused` 会显示对应结果
- `POST /admin/keys/bulk-action` 支持 `enable/disable/delete`
- 页面 HTML 中包含“成功次数”“批量操作”“全部/启用/停用/有错误/未成功调用”

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_admin_views -v`
Expected: FAIL，提示路由或页面缺失对应元素

**Step 3: Write minimal implementation**

- `dashboard()` 读取 `filter`
- 新增批量操作路由
- 严格校验提交参数

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_admin_views -v`
Expected: PASS

### Task 3: 重做中文紧凑控制台页面

**Files:**
- Modify: `templates/admin_dashboard.html`
- Modify: `templates/admin_login.html`
- Create: `static/admin_base.css`
- Create: `static/admin_dashboard.css`
- Delete: `static/admin.css`
- Test: `tests/test_admin_views.py`

**Step 1: Write the failing test**

复用 Task 2 的页面断言，确保改版后关键中文文案和表格列仍可通过测试验证。

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_admin_views -v`
Expected: FAIL，直到模板结构更新完成

**Step 3: Write minimal implementation**

- 登录页和控制台统一改为中文标题
- 控制台增加筛选条、批量操作条、勾选列和成功次数列
- 样式拆分为共享基础样式与控制台样式，保持文件小于 300 行并采用紧凑布局

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_admin_views -v`
Expected: PASS

### Task 4: 全量回归验证

**Files:**
- Modify: `readme.md`
- Test: `tests/test_admin_store.py`
- Test: `tests/test_admin_views.py`
- Test: `tests/test_image_proxy_service.py`
- Test: `tests/test_image_proxy_server.py`

**Step 1: Update docs**

- 在 `readme.md` 补充后台新增能力说明

**Step 2: Run focused tests**

Run: `python3 -m unittest tests.test_admin_store tests.test_admin_views -v`
Expected: PASS

**Step 3: Run full regression**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS
