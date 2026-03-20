# deAPI API Key 自动化工具

本项目用于自动完成 deAPI 账号注册、邮箱验证、进入 dashboard、创建并导出 API key。

核心流程基于 HTTP 会话和 deAPI 的 Livewire 协议，不再依赖旧的 `x.ai` 页面点击流或 `sso` cookie 抓取。

此外，仓库现在还包含一个 OpenAI Images 兼容的图片中转服务：

- 对外接口：`POST /v1/images/generations`
- 兼容接口：`POST /v1/chat/completions`
- 对内上游：`POST https://api.deapi.ai/api/v1/client/txt2img`
- 中转站会自动轮询 `request-status`
- 默认固定返回 `b64_json`，方便下游直接解码显示图片
- 对外暴露 5 个固定尺寸模型别名，自动映射到上游 `ZImageTurbo_INT8`
- 所有上游请求统一强制 `steps=8`
- 运行时 key 存在 SQLite 中，可通过管理员后台管理
- 按“每个下游请求一个 key”的粒度轮询启用中的 key
- 提交任务前若某把 key 报 `401/403/429/5xx` 或网络错误，会切换到下一把 key 重试
- 一旦某把 key 已成功拿到 `request_id`，后续轮询固定用这把 key，不再换 key 重提
- `chat/completions` 兼容层会从最后一条 `user` 消息提取 prompt
- `chat/completions` 未传 `seed` 时会自动生成随机 seed
- `chat/completions` 返回 assistant Markdown 图片；`stream: true` 时返回 SSE + `[DONE]`

管理员后台能力：

- 简单管理员密码登录
- 中文紧凑界面显示 key 列表
- 批量添加 key
- 删除 key
- 启用/禁用 key
- 筛选 `全部 / 启用 / 停用 / 有错误 / 未成功调用`
- 批量启用、批量停用、批量删除
- 查看每把 key 的累计错误次数、成功调用次数、最近错误、最近使用时间

## 当前流程

1. 调用 GPTMail 生成临时邮箱
2. 提交 `https://deapi.ai/register`
3. 轮询验证邮件并提取 `https://deapi.ai/verify-email/...` 签名链接
4. 在同一会话中消费验证链接进入 dashboard
5. 打开 `https://deapi.ai/settings/api-keys`
6. 创建新的 secret key
7. 将 API key 导出到本地 txt 文件

## 代理池轮询

支持为每一轮注册绑定一个 SOCKS5 代理，并按代理池顺序轮询。

- 轮询粒度是“每一轮注册”，不是“每个请求”
- 同一轮中的 GPTMail 请求和 deAPI 请求会固定走同一个代理
- 下一轮会切换到池中的下一个代理
- 代理配置错误会直接报错，不会静默回退到直连

## 环境要求

- Python 3.12 或 3.13
- 可访问 `https://deapi.ai`
- 可访问 `https://mail.chatgpt.org.uk`
- GPTMail API key 通过环境变量提供
- 启用代理池时需要安装带 SOCKS 支持的 `requests[socks]`

## 安装

```bash
pip install -r requirements.txt
```

## 配置

配置文件为根目录下的 `config.json`：

```json
{
  "run": {
    "count": 30000
  },
  "mail": {
    "base_url": "https://mail.chatgpt.org.uk",
    "api_key_env": "GPTMAIL_API_KEY",
    "timeout_sec": 120,
    "poll_interval_sec": 3
  },
  "deapi": {
    "base_url": "https://deapi.ai"
  },
  "image_proxy": {
    "host": "0.0.0.0",
    "port": 8787,
    "submit_timeout_sec": 30,
    "poll_timeout_sec": 180,
    "poll_interval_sec": 2,
    "download_timeout_sec": 60,
    "upstream_base_url": "https://api.deapi.ai",
    "default_model": "ZImageTurbo_INT8",
    "default_size": "768x768",
    "upstream_key_file": "api_keys/upstream_deapi_keys.txt"
  },
  "admin": {
    "database_path": "data/image_proxy.sqlite3",
    "username": "admin",
    "password_env": "IMAGE_PROXY_ADMIN_PASSWORD",
    "session_secret_env": "IMAGE_PROXY_SESSION_SECRET"
  },
  "proxy_pool": {
    "enabled": false,
    "strategy": "round_robin",
    "proxies": [
      "gate.ipdeep.com:8082:d2533502065-dc-country-any-session-1304948000-sessiontime-5:KspkkhU4"
    ]
  }
}
```

说明：

- `run.count`: 默认执行轮数，`0` 表示无限循环
- `mail.base_url`: GPTMail 服务地址
- `mail.api_key_env`: 读取 GPTMail API key 的环境变量名
- `mail.timeout_sec`: 等待验证邮件的超时时间
- `mail.poll_interval_sec`: 收件轮询间隔
- `deapi.base_url`: deAPI 站点地址
- `image_proxy.host`: 图片中转服务监听地址
- `image_proxy.port`: 图片中转服务监听端口
- `image_proxy.submit_timeout_sec`: 提交 `txt2img` 的单次请求超时
- `image_proxy.poll_timeout_sec`: 单个图片任务整体轮询超时
- `image_proxy.poll_interval_sec`: 查询 `request-status` 的轮询间隔
- `image_proxy.download_timeout_sec`: 下载最终图片的超时
- `image_proxy.upstream_base_url`: deAPI HTTP API 根地址
- `image_proxy.default_model`: 下游未传 `model` 时的默认模型
- `image_proxy.default_size`: 下游未传 `size` 时的默认尺寸
- `image_proxy.upstream_key_file`: 上游 deAPI keys 文本文件路径，一行一个
- `admin.database_path`: SQLite 数据库文件路径
- `admin.username`: 管理员用户名
- `admin.password_env`: 管理员密码环境变量名
- `admin.session_secret_env`: Flask session secret 环境变量名
- `proxy_pool.enabled`: 是否启用代理池
- `proxy_pool.strategy`: 当前仅支持 `round_robin`
- `proxy_pool.proxies`: SOCKS5 代理列表，格式为 `host:port:username:password`

代理示例：

```text
gate.ipdeep.com:8082:d2533502065-dc-country-any-session-1304948000-sessiontime-5:KspkkhU4
```

程序运行时会将其转换成 `socks5h://username:password@host:port` 注入 `requests.Session`。

必须先设置 GPTMail API key：

```bash
export GPTMAIL_API_KEY='your-gptmail-key'
```

`image_proxy.upstream_key_file` 这个字段保留在配置里，主要用于兼容旧的文本导入方式；当前管理员后台模式下，运行时不会直接从这个文件读取 key。

如果你手头已经有一份纯文本 key 列表，可以直接把这些内容粘贴进后台的“批量添加 Key”文本框，一行一个即可。

如果要启用管理员后台，还需要设置管理员密码和 session secret：

```bash
export IMAGE_PROXY_ADMIN_PASSWORD='your-admin-password'
export IMAGE_PROXY_SESSION_SECRET='your-session-secret'
```

说明：

- SQLite 数据库会在首次启动时自动初始化
- 管理员账号也会在首次启动时自动写入 SQLite
- 实际运行时，图片中转会从 SQLite 读取“已启用”的 key，而不是从文本文件直接读取

## 启动方式

```bash
# 按 config.json 中 run.count 执行
python3 DrissionPage_example.py

# 只执行 1 轮
python3 DrissionPage_example.py --count 1

# 无限循环
python3 DrissionPage_example.py --count 0

# 指定输出文件
python3 DrissionPage_example.py --output ./my_keys.txt
```

图片中转服务启动方式：

```bash
python3 image_proxy_server.py

# 指定监听地址和端口
python3 image_proxy_server.py --host 127.0.0.1 --port 8787
```

后台入口：

```text
http://127.0.0.1:8787/admin
```

批量导入格式：

```text
Primary,key-1
key-2
备用,key-3
```

OpenAI 兼容图片请求示例：

```bash
curl -X POST 'http://127.0.0.1:8787/v1/images/generations' \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "a cinematic red fox in snow",
    "model": "z-image-1024x1024",
    "seed": 4013112700,
    "negative_prompt": ""
  }'
```

说明：

- 对外可见模型列表通过 `GET /v1/models` 获取，当前固定返回：
  - `z-image-1024x1024`
  - `z-image-832x1216`
  - `z-image-1216x832`
  - `z-image-688x1216`
  - `z-image-1216x688`
- 这 5 个模型别名都会强制覆盖为固定宽高，并统一把上游 `model` 设为 `ZImageTurbo_INT8`
- 中转层会忽略下游传入的 `size`、`width`、`height`、`steps`，始终按模型别名预设值提交
- 当前上游 deAPI 真实要求 `seed` 必填，因此中转接口也会将 `seed` 视为必填字段
- 不传 `seed` 时会直接返回 `400`，错误码为 `missing_seed`

成功响应示例：

```json
{
  "created": 1760000000,
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAA..."
    }
  ]
}
```

Chat Completion 兼容请求示例：

```bash
curl -X POST 'http://127.0.0.1:8787/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "z-image-688x1216",
    "messages": [
      {"role": "system", "content": "[Start a new Chat]"},
      {"role": "user", "content": "一只小狗"}
    ],
    "stream": false
  }'
```

兼容返回示例：

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1760000000,
  "model": "z-image-688x1216",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "![](data:image/png;base64,...)"
      },
      "finish_reason": "stop"
    }
  ]
}
```

## 输出

生成的 API key 默认写入 `api_keys/` 目录，每行一个：

```text
api_keys/
  api_keys_20260320_120000.txt
```

运行日志写入 `logs/`：

```text
logs/
  run_20260320_120000.log
```

启用代理池后，日志还会记录每一轮使用的代理地址，但密码会被脱敏。

## 文件结构

```text
├── DrissionPage_example.py   # CLI 入口
├── image_proxy_server.py     # OpenAI Images 兼容图片中转服务
├── image_proxy_config.py     # 图片中转配置读取
├── admin_store.py            # SQLite 管理后台存储层
├── admin_views.py            # 管理后台登录与页面路由
├── managed_key_pool.py       # 从 SQLite 读取启用 key 并做轮询
├── deapi_key_pool.py         # 上游 deAPI API key 轮询池
├── deapi_image_gateway.py    # deAPI txt2img / request-status / 下载封装
├── openai_image_proxy.py     # OpenAI 请求映射与中转业务逻辑
├── templates/                # 管理后台模板
├── static/                   # 管理后台样式
├── deapi_client.py           # deAPI Livewire 协议封装
├── deapi_workflow.py         # 单轮注册/验证/创建 key 工作流
├── gptmail_client.py         # GPTMail 封装
├── proxy_pool.py             # SOCKS5 代理池解析与轮询
├── config.json               # 运行配置
├── tests/                    # 单元测试
├── api_keys/                 # 导出的 API key（运行后生成）
└── logs/                     # 运行日志
```

## 调试原则

- 注册失败直接报错，不做静默兜底
- 邮件轮询超时直接报错
- 未找到 deAPI 验证链接直接报错
- 创建 key 响应里没有 `createdKey` 直接报错
- 图片中转请求体非法直接报错
- 图片任务轮询超时直接报错
- 已拿到 `request_id` 后不会静默换 key 重提
- 后台未登录访问会直接跳转到登录页
