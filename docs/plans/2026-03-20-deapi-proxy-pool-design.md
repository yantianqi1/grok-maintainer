# deAPI Proxy Pool Rotation Design

**Goal**

为当前 deAPI 注册靶场增加 SOCKS5 代理池能力，使每一轮注册流程固定绑定一个代理，并按轮次顺序轮询代理池，降低单个出口 IP 的连续请求压力。

## Context

当前主流程由 [`DrissionPage_example.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/DrissionPage_example.py) 驱动，在单轮内调用：

- [`gptmail_client.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/gptmail_client.py) 生成临时邮箱并轮询验证邮件
- [`deapi_client.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/deapi_client.py) 在同一个 `requests.Session` 中完成注册、验证、创建 API key
- [`deapi_workflow.py`](/Users/项目/deapi%20靶场/grok-maintainer_副本/deapi_workflow.py) 编排单轮流程

这一流程依赖会话连续性。如果在注册、邮箱验证和创建 key 之间切换代理，可能导致站点会话状态或风控判断不一致。因此代理粒度必须是“每一轮固定一个代理”，而不是“每个请求切换一个代理”。

## Requirements

1. 代理池通过 `config.json` 配置。
2. 每个代理项支持用户提供的四段格式：`host:port:username:password`。
3. 每一轮开始时，从代理池中取出一个代理并创建新的 `requests.Session`。
4. 同一轮中的 GPTMail 请求和 deAPI 请求共享同一个代理配置。
5. 下一轮切到池中的下一个代理；到尾部后重新回到起点。
6. 代理配置错误直接报错，不做静默直连回退。
7. 日志需要展示本轮使用的代理，但账号密码必须脱敏。

## Architecture

新增一个独立模块 `proxy_pool.py`，职责保持单一：

1. 解析原始代理字符串。
2. 把代理项转换成 `requests.Session.proxies` 需要的 `socks5h://user:pass@host:port` 形式。
3. 管理轮询状态，按顺序返回当前轮应使用的代理。
4. 生成脱敏后的日志文本。

主循环只负责：

1. 从配置读取代理池配置。
2. 若启用代理池，则在每轮开始时获取一个代理。
3. 为 `GptMailClient` 和 `DeapiClient` 各创建新的会话对象，并注入同一组代理配置。

这样可以保证代理能力与业务逻辑解耦，不把解析、轮询、日志脱敏杂糅到 CLI 和 HTTP 客户端里。

## Data Flow

单轮带代理的流程如下：

1. CLI 读取 `proxy_pool` 配置。
2. 轮询器返回当前轮的代理项。
3. 创建两个新的 `requests.Session`，都设置相同的 `session.proxies`。
4. 用这两个 session 分别初始化 `GptMailClient` 和 `DeapiClient`。
5. 运行已有 `run_single_deapi_registration(...)`。
6. 本轮结束后不复用该 session，下一轮重新取下一个代理并创建新 session。

## Config Shape

在 [`config.json`](/Users/项目/deapi%20靶场/grok-maintainer_副本/config.json) 中增加：

```json
{
  "proxy_pool": {
    "enabled": true,
    "strategy": "round_robin",
    "proxies": [
      "gate.ipdeep.com:8082:d2533502065-dc-country-any-session-1304948000-sessiontime-5:KspkkhU4"
    ]
  }
}
```

说明：

- `enabled`: 是否启用代理池
- `strategy`: 当前只支持 `round_robin`
- `proxies`: 原始代理列表，按顺序轮询

## Error Handling

遵循项目的 debug-first 规则，不添加静默兜底：

- `enabled=true` 但 `proxies` 为空时直接报错
- 代理字符串不是四段格式时直接报错
- 端口不是有效整数时直接报错
- `strategy` 不是 `round_robin` 时直接报错
- 设置代理后如请求失败，保持原始异常暴露，不吞错

## Testing

新增三类测试：

1. `proxy_pool.py` 单元测试
   - 解析四段代理字符串
   - 生成 `socks5h` 代理 URL
   - 轮询顺序正确
   - 脱敏日志正确

2. CLI 配置测试
   - 读取 `proxy_pool` 配置
   - 非法配置报错

3. 客户端注入测试
   - 每一轮使用新建 session
   - `session.proxies` 正确写入 `http` 和 `https`
