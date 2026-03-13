# Grok 账号批量注册工具

基于 [DrissionPage](https://github.com/g1879/DrissionPage) 的 Grok (x.ai) 账号自动注册脚本，通过加载 Chrome 扩展修复 CDP `MouseEvent.screenX/screenY` 缺陷，绕过 Cloudflare Turnstile 人机验证。

> **原理**：Chrome CDP 命令 `Input.dispatchMouseEvent` 触发的鼠标事件，其 `screenX/screenY` 与 `clientX/clientY` 值相同，这是 Chromium 的已知 bug（[chromium#40280325](https://issues.chromium.org/issues/40280325)）。Cloudflare Turnstile 利用该特征识别自动化点击，本工具通过扩展将两个属性重写为随机合理值来规避检测。

---

## 环境要求

- Python 3.12 或 3.13（推荐，3.14+ 会自动切换）
- Chromium 或 Chrome 浏览器
- 自建 Cloudflare Worker 邮件服务（用于接收注册验证码）
- 可选：grok2api 实例（用于自动导入注册好的 SSO token）

---

## 安装

```bash
pip install -r requirements.txt
```

---

## 配置文件（config.json）

所有配置集中在项目根目录的 `config.json`，首次使用前必须填写。

```json
{
    "run": {
        "count": 10
    },
    "email": {
        "worker_domain": "your-worker.example.com",
        "email_domains": ["example.com"],
        "admin_password": "your-admin-password"
    },
    "api": {
        "endpoint": "http://your-api-host/v1/admin/tokens",
        "token": "your-api-token",
        "append": true
    }
}
```

### run — 运行控制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `run.count` | int | `10` | 每次启动执行的注册轮数。设为 `0` 表示无限循环，也可通过命令行 `--count` 覆盖 |

### email — 临时邮箱服务

脚本使用自建 Cloudflare Worker 邮件服务接收注册验证码，需自行部署。

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `email.worker_domain` | string | Worker 服务域名，不含 `https://`，例如 `email.example.com` |
| `email.email_domains` | array | 收件域名列表，每轮随机选一个，例如 `["example.com", "mail.example.com"]` |
| `email.admin_password` | string | Worker 管理接口认证密码，对应请求头 `x-admin-auth` |

Worker 需实现以下两个接口：

| 接口 | 说明 |
|------|------|
| `POST /admin/new_address` | 创建临时邮箱。Body: `{enablePrefix, name, domain}`，Header: `x-admin-auth: <password>`，返回 `{address, jwt}` |
| `GET /api/mails` | 拉取收件列表。Header: `Authorization: Bearer <jwt>`，返回 `{results: [{id, raw, ...}]}` |

### api — grok2api 推送（可选）

所有轮次注册完成后，自动将本批 SSO token 推送到 grok2api 管理接口。不需要此功能可将 `endpoint` 留空。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api.endpoint` | string | 空 | grok2api 管理接口完整地址，例如 `http://your-host:3003/v1/admin/tokens`。留空则跳过推送 |
| `api.token` | string | 空 | 接口 Bearer 认证 token，对应请求头 `Authorization: Bearer <token>` |
| `api.append` | bool | `true` | `true`：推送前先 GET 查询线上现有 token，与本次新增合并后全量推送；`false`：直接用本次 token 全量覆盖 |

推送接口规范：
- `GET <endpoint>` — 查询现有 token，返回 `{"ssoBasic": [{"token": "...", ...}]}`
- `POST <endpoint>` — 写入 token，Body: `{"ssoBasic": ["token1", "token2", ...]}` ，成功返回 `{"status": "success"}`

---

## 启动方式

```bash
# 按 config.json 中 run.count 执行（默认 10 轮）
python DrissionPage_example.py

# 指定轮数（覆盖配置文件）
python DrissionPage_example.py --count 5

# 无限循环，直到手动 Ctrl+C
python DrissionPage_example.py --count 0

# 指定 SSO 输出文件路径（默认自动按时间戳生成）
python DrissionPage_example.py --output ./my_output.txt

# 注册完成后额外提取页面数字文本
python DrissionPage_example.py --extract-numbers
```

脚本启动后浏览器窗口会自动打开，可直接观察注册过程。每轮注册完成后浏览器完全重启，避免 Cookie/会话污染。

---

## 输出文件

注册成功的 SSO token 自动保存在 `sso/` 目录，文件名含启动时间戳，每行一个 token：

```
sso/
  sso_20260313_142301.txt   ← 第一次运行的所有 token
  sso_20260314_093000.txt   ← 第二次运行的所有 token
```

运行日志保存在 `logs/` 目录，记录每轮注册的邮箱、密码和结果：

```
logs/
  run_20260313_142301.log
```

`sso/` 和 `logs/` 目录在首次运行时自动创建。

---

## 文件结构

```
├── DrissionPage_example.py     # 主脚本
├── email_register.py           # 临时邮箱服务封装
├── config.json                 # 配置文件（必须填写）
├── requirements.txt            # Python 依赖
├── turnstilePatch/             # Chrome 扩展（Turnstile patch）
│   ├── manifest.json
│   └── script.js
├── sso/                        # SSO token 输出目录（自动创建）
│   └── sso_<timestamp>.txt
└── logs/                       # 运行日志目录（自动创建）
    └── run_<timestamp>.log
```

---

## 注意事项

- x.ai 注册页面为中文界面，按钮查找依赖中文文本匹配（"使用邮箱注册"、"确认邮箱"等），若页面语言或文案变更需同步更新脚本
- Python 3.14+ 环境下脚本会自动尝试切换到系统中安装的 3.12/3.13 解释器
- Turnstile 解决最多重试 15 次，若持续失败可能是 Cloudflare 更新了检测策略

---

## 关于 grok2api

本工具的 API 推送功能基于 [chenyme/grok2api](https://github.com/chenyme/grok2api) 项目设计。

grok2api 是一个将 Grok（x.ai）的 SSO token 转换为 OpenAI 兼容 API 的代理服务，主要功能：

- 接受标准 OpenAI 格式的请求（`/v1/chat/completions` 等），转发给 Grok 后端
- 支持多 SSO token 池，自动轮询调度，单 token 失效不影响整体服务
- 提供管理接口用于批量导入/查询 SSO token（即本工具推送的目标接口）

### 与本工具的配合方式

```
本工具（批量注册）→ 注册成功后推送 SSO token → grok2api 管理接口
                                                       ↓
                                          对外提供 OpenAI 兼容 API
```

部署 grok2api 后，在 `config.json` 的 `api` 节填入其管理接口地址和认证 token，本工具每次完成批量注册后会自动将新 token 合并推送到 grok2api 的 token 池中。
