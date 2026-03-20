# deAPI API Key Automation Design

**Goal**

把项目从旧的 `x.ai`/`sso` 注册脚本改造成 deAPI 自动化链路：注册账号、轮询验证邮件、消费签名验证链接、进入 dashboard、创建并导出 API key。

## Context

现有仓库的主脚本 [`DrissionPage_example.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/DrissionPage_example.py) 绑定了旧站点的中文页面文案、验证码输入和 `sso` cookie 抓取逻辑。真实探测已经确认：

- `https://deapi.ai/register` 是 Livewire 驱动的英文注册表单。
- 注册动作通过 `POST /livewire-8b25ad4c/update` 完成，要求携带 `X-Livewire: true`、CSRF 和同会话 cookie。
- 注册成功后进入 `/verify-email`。
- GPTMail 可稳定收到两封邮件，其中 `Activate your deAPI account` 包含真实 `https://deapi.ai/verify-email/...` 签名链接。
- 在同一会话中访问签名验证链接会跳转到 `/dashboard?verified=1`。
- API key 页面真实路径是 `/settings/api-keys`，组件名 `settings.api-keys`，字段 `keyName`，动作 `createKey`，返回 `createdKey`。

## Architecture

采用 HTTP 协议自动化替代旧浏览器页面流，但保留现有 CLI 入口、日志、批量运行和 watchdog 使用方式。

分层如下：

1. `gptmail_client.py`
   负责 GPTMail 的邮箱生成、清空、列邮件、取详情、提取验证链接。

2. `deapi_client.py`
   负责 deAPI 会话管理、页面元数据提取、Livewire 请求组装、注册、验证、创建 API key。

3. `deapi_workflow.py`
   编排单轮完整流程：生成邮箱 -> 注册 -> 等邮件 -> 验证 -> 创建 key -> 导出文件 -> 返回结果。

4. `DrissionPage_example.py`
   缩成 CLI 包装层，只保留参数解析、轮次控制、输出路径和批量执行。

## Data Flow

单轮流程：

1. 调用 GPTMail 生成邮箱。
2. `GET /register` 提取 `csrf-token`、`data-update-uri`、`auth.register` 快照。
3. 发送 Livewire `register` 请求。
4. 轮询 GPTMail，遍历全部邮件，提取直接的 `deapi.ai/verify-email/...` 链接。
5. 用同一个 deAPI `requests.Session` 访问验证链接，确认进入 dashboard。
6. `GET /settings/api-keys` 提取 `settings.api-keys` 快照。
7. 发送 Livewire `createKey` 请求，解析返回快照里的 `createdKey`。
8. 将结果追加写入输出文件。

## Output Format

不再输出 `sso`，改为每行一个 API key，保持简单可批量处理。

额外返回结构：

- `email`
- `api_key`
- `dashboard_url`
- `output_path`

## Error Handling

遵循项目的 debug-first 规则，不做静默兜底：

- GPTMail 请求失败直接抛错。
- 注册响应不是 Livewire JSON 或未返回 `/verify-email` 直接抛错。
- 邮件轮询超时直接抛错。
- 未找到直接的 deAPI 验证链接直接抛错。
- 验证后未进入 dashboard 直接抛错。
- 创建 key 响应里没有 `createdKey` 直接抛错。

## Testing

自动化测试分三类：

1. 纯单元测试
   覆盖页面元数据解析、邮件链接提取、Livewire 响应解析。

2. 协议单元测试
   用 fake session 验证 register/createKey 的请求体组装是否正确。

3. 真实集成验证
   执行 `python3 DrissionPage_example.py --count 1`，确认可以真实生成并导出 API key。
