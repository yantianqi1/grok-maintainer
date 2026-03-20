# deAPI Image Proxy Admin Dashboard Design

**Goal**

为现有 deAPI 图片中转服务新增一个带登录保护的管理员后台，用于查看、批量添加、删除、启用/禁用上游 API key，并展示每把 key 的上游报错次数与最近错误信息。

## Context

当前仓库已经具备：

- Flask 图片中转入口 [`image_proxy_server.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/image_proxy_server.py)
- OpenAI Images 到 deAPI 的请求映射逻辑 [`openai_image_proxy.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/openai_image_proxy.py)
- 提交、轮询和图片下载网关 [`deapi_image_gateway.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/deapi_image_gateway.py)
- `unittest` 测试体系

当前图片服务从文本文件读取上游 key，但用户需要：

- 管理员网页后台
- 简单管理员密码登录
- SQLite 持久化
- 查看所有 key
- 批量添加 key
- 删除 key
- 启用/禁用 key
- 显示每把 key 的上游报错次数

## Architecture

新增 5 个职责模块：

1. `admin_store.py`
   负责 SQLite 初始化、管理员用户校验、API key 增删改查、错误计数与统计汇总。

2. `managed_key_pool.py`
   负责从 SQLite 读取当前启用 key，并以请求粒度做 round-robin 轮询。

3. `admin_views.py`
   负责 Flask 管理后台路由、登录登出、页面渲染和表单处理。

4. `templates/admin_login.html`
   登录页。

5. `templates/admin_dashboard.html` + `static/admin.css`
   管理控制台界面，展示统计、批量添加区域和 key 列表。

同时修改现有图片中转服务：

- 不再从文本文件读取运行时 key 池
- 改为从 SQLite 读取当前启用 key
- 在上游失败时回写 `error_count` 和 `last_error_message`
- 在成功生成图片后回写 `last_used_at`

## Data Model

### `admin_users`

- `id`
- `username`
- `password_hash`
- `created_at`
- `updated_at`

### `upstream_api_keys`

- `id`
- `label`
- `api_key`
- `is_enabled`
- `error_count`
- `last_error_message`
- `last_used_at`
- `created_at`
- `updated_at`

约束：

- `api_key` 全局唯一
- `is_enabled` 仅允许 `0/1`

## Auth Model

管理员后台使用简单 session 登录：

- 启动时从配置读取管理员用户名、密码环境变量和 session secret 环境变量
- 自动初始化 SQLite 中的管理员账号
- 登录成功后写入 Flask session
- 未登录访问 `/admin` 自动跳转 `/admin/login`

## Request And Data Flow

### 管理后台

1. 管理员访问 `/admin/login`
2. 提交用户名与密码
3. 登录成功后进入 `/admin`
4. 页面读取 SQLite 统计与 key 列表
5. 批量添加、启用/禁用、删除操作都通过 POST 表单提交
6. 操作完成后重定向回 `/admin`

### 图片中转

1. 下游请求 `POST /v1/images/generations`
2. 从 SQLite 读取 `is_enabled = 1` 的 key 列表
3. 轮询选择本次首 key
4. 提交阶段失败则给该 key 记一次错误，并切到下一把 key
5. 拿到 `request_id` 后固定该 key 轮询
6. 若轮询或下载失败，记一次错误
7. 若成功，更新 `last_used_at`
8. 返回 `b64_json`

## Error Counting Rules

- 只有实际发往上游 deAPI 的失败才累计 `error_count`
- 表单校验失败不计数
- 提交阶段失败且切 key 时，失败的那把 key 计数
- 已获得 `request_id` 后的轮询失败，也记到这把 key
- 最近一次错误文本写入 `last_error_message`

## UI Direction

采用“控制室 / 运营台”风格：

- 深墨绿、骨白和铜金作为主色
- 大号数字统计卡
- 标题用衬线字体，列表与 key 用等宽字体
- 页面有轻微噪点和斜切阴影，避免通用后台模板感
- 移动端收敛为单列布局

## Testing

测试分四层：

1. SQLite 数据层测试
   - 初始化管理员账号
   - 批量添加 key
   - 去重
   - 启用/禁用
   - 删除
   - 错误计数与最后使用时间

2. 管理后台路由测试
   - 未登录跳登录页
   - 错误密码失败
   - 正确密码成功
   - 批量添加、启用/禁用、删除生效

3. 图片服务联动测试
   - 只读取启用 key
   - 上游失败会更新错误计数
   - 成功会更新最后使用时间

4. 全量回归
   - 保持现有图片接口和既有单元测试全部通过
