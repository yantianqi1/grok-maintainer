# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

本项目使用浏览器自动化技术实现 Grok (x.ai) 账号批量注册。核心功能是绕过 Cloudflare Turnstile 机器人检测，方法是加载一个 Chrome 扩展来修复 Chrome CDP 的 `MouseEvent.screenX/screenY` 属性缺陷（[chromium#40280325](https://issues.chromium.org/issues/40280325)），Turnstile 利用该缺陷来识别自动化点击。注册成功的 SSO token 可自动推送到 [grok2api](https://github.com/chenyme/grok2api) 管理接口。

## 运行命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行注册脚本（轮数从 config.json 读取，默认 10 轮）
python DrissionPage_example.py

# 运行指定轮数（覆盖 config.json）
python DrissionPage_example.py --count 5

# 无限循环
python DrissionPage_example.py --count 0

# 输出到指定文件
python DrissionPage_example.py --output my_sso.txt

# 注册完成后提取页面数字文本
python DrissionPage_example.py --extract-numbers
```

推荐使用 Python 3.12 或 3.13。脚本检测到 3.14+ 时会通过 `os.execve` 自动切换，原因是临时邮箱服务在 3.14+ 下存在 TLS 兼容问题。

## 架构

### 文件说明

| 文件 | 说明 |
|------|------|
| `DrissionPage_example.py` | 主脚本，驱动 Chromium 完成完整注册流程 |
| `email_register.py` | 临时邮箱服务封装，调用自建 Cloudflare Worker 邮件 API |
| `config.json` | 统一配置文件（运行轮数、邮件服务、grok2api 推送） |
| `turnstilePatch/` | Chrome Manifest V3 扩展，patch `MouseEvent.screenX/screenY` |
| `sso/` | 注册成功的 SSO token 输出目录，文件名按启动时间戳命名 |
| `logs/` | 运行日志目录，文件名按启动时间戳命名 |

### 配置文件（`config.json`）

```json
{
    \"run\": {
        \"count\": 10
    },
    \"email\": {
        \"worker_domain\": \"<Cloudflare Worker 域名>\",
        \"email_domains\": [\"<收件域名>\"],
        \"admin_password\": \"<管理员密码>\"
    },
    \"api\": {
        \"endpoint\": \"<grok2api 管理接口地址>\",
        \"token\": \"<Bearer token>\",
        \"append\": true
    }
}
```

- `run.count`：默认执行轮数，`0` 为无限循环，可被 `--count` 覆盖
- `api.append`：`true` 时推送前先 GET 查询线上现有 token 合并后全量推送；`false` 时直接覆盖
- `api.endpoint` 留空则跳过推送

### 注册主流程（`DrissionPage_example.py`）

每轮注册依次执行：

1. `start_browser()` — 启动携带 `turnstilePatch` 扩展的 Chromium
2. `open_signup_page()` — 打开注册页，点击"使用邮箱注册"
3. `fill_email_and_submit()` — 调用 `email_register.get_email_and_token()` 创建临时邮箱并填写
4. `fill_code_and_submit()` — 调用 `email_register.get_oai_code()` 轮询 OTP 并填写确认
5. `getTurnstileToken()` — 解决 Cloudflare Turnstile 人机验证
6. `fill_profile_and_submit()` — 填写姓名（Neo Lin）、密码并提交
7. 提取 SSO token，追加写入 `sso/<timestamp>.txt`

所有轮次结束后，`main()` 的 `finally` 块调用 `push_sso_to_api(collected_sso)` 一次性推送本批全部 token。每轮结束后整个浏览器实例完全重启（`restart_browser()`），避免 Cookie/会话污染。

### 临时邮箱服务（`email_register.py`）

基于自建 Cloudflare Worker 的邮件 API，配置从 `config.json` 读取。

关键函数：
- `create_temp_email()` — POST `/admin/new_address` 创建随机邮箱，返回 `(email, jwt_token)`
- `fetch_emails()` — GET `/api/mails` 拉取收件列表（需 Bearer JWT）
- `wait_for_verification_code()` — 轮询新邮件，调用 `extract_verification_code()` 提取验证码
- `extract_verification_code()` — 按优先级匹配多种验证码格式（`XXX-XXX` 字母数字混合、6位数字等），硬过滤 `177010`

### grok2api 推送（`push_sso_to_api`）

所有轮次完成后调用，入参为本次注册成功的 token 列表：

- `append=true`：先 GET 查询线上现有 token，与本次列表合并去重后全量 POST
- `append=false`：直接用本次列表全量 POST 覆盖

推送接口：`GET/POST <api.endpoint>`，Header: `Authorization: Bearer <api.token>`，Body: `{"ssoBasic": ["token1", ...]}`

### Cloudflare Turnstile 绕过（`turnstilePatch/`）

Chrome CDP 派发的鼠标事件 `screenX/screenY` 与 `clientX/clientY` 相同（Chromium bug），Turnstile 据此识别自动化。

修复方案：`script.js` 在 `document_start`、`MAIN` 世界、所有 frames 中执行，将 `MouseEvent.prototype.screenX/screenY` 重写为随机整数（X: 800-1200，Y: 400-600）。`getTurnstileToken()` 进入 Turnstile iframe 后再次执行相同 patch（4K 屏适配），然后点击 checkbox，最多轮询 15 次获取 token。

### React 表单填写模式

所有输入框填写统一使用原生 setter 注入，避免 React 受控组件忽略直接赋值：

1. `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set` 获取原生 setter
2. 重置 `input._valueTracker`
3. 调用原生 setter 写入值
4. 依次派发 `beforeinput` → `input` → `change` 事件

### 异常处理要点

- `PageDisconnectedError`：OTP 提交后页面跳转导致旧句柄失效，捕获后调用 `refresh_active_page()` 重新获取活动标签页
- 所有 DOM 查找通过内联 `isVisible()` 过滤隐藏元素（`display:none`、`visibility:hidden`、零尺寸），并检查 `disabled`、`readOnly`、`aria-disabled` 状态
- 按钮查找依赖中文文本匹配（"使用邮箱注册"、"确认邮箱"等），前端文案变更需同步更新
