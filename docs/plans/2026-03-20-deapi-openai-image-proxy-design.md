# deAPI OpenAI Image Proxy Design

**Goal**

为现有仓库新增一个 OpenAI Images 兼容中转服务，对外暴露 `POST /v1/images/generations`，对内调用 deAPI 的 `txt2img` 和 `request-status`，最终固定返回 `b64_json`。

## Context

当前仓库已经具备：

- Python + `requests` 的 HTTP 自动化风格
- `config.json` 作为主要配置入口
- `unittest` 作为测试方式
- 明确的 debug-first 规则，不允许静默兜底

用户需要的中转能力有这些约束：

- 下游兼容 `new-api` 使用的 OpenAI 图片接口
- 上游是 `POST https://api.deapi.ai/api/v1/client/txt2img`
- deAPI 不是同步直接回图片，而是先回 `request_id`，再通过 `GET /api/v1/client/request-status/{request_id}`` 轮询到 `result_url`
- 中转站必须把最终图片转成 base64，并用 OpenAI 图片响应里的 `b64_json` 返回
- 中转站维护一批 deAPI API key，并按“每个下游请求一个 key”做轮询
- 如果提交任务前的上游请求失败，允许切换到下一把 key 重试
- 一旦某把 key 已经成功拿到 `request_id`，该请求后续轮询必须固定使用这把 key，直到完成或失败

## Architecture

新增 4 个职责清晰的模块：

1. `image_proxy_config.py`
   负责读取 `config.json` 里的 `image_proxy` 配置，并从本地密钥文件读取上游 deAPI keys。

2. `deapi_key_pool.py`
   负责线程安全的 round-robin 取 key。每次下游请求会得到一个“尝试顺序”，首 key 参与轮询，失败时只在提交阶段切下一个。

3. `deapi_image_gateway.py`
   负责和 deAPI 交互：提交 `txt2img`、轮询 `request-status`、下载最终图片二进制，并把上游错误转换成明确异常。

4. `image_proxy_server.py`
   负责 Flask HTTP 服务层：解析 OpenAI 图片请求、调用业务服务、组装 OpenAI 风格响应、输出错误响应。

## Request Mapping

对外兼容：

- 路径：`POST /v1/images/generations`
- 请求体主要字段：
  - `prompt`
  - `model`，默认 `ZImageTurbo_INT8`
  - `size`，格式如 `768x768`
  - `seed`
  - `steps`
  - `negative_prompt`

内部映射到 deAPI：

- `prompt` -> `prompt`
- `model` -> `model`
- `size` -> `width` + `height`
- `seed` -> `seed`
- `steps` -> `steps`
- `negative_prompt` -> `negative_prompt`

约束：

- 默认永远返回 `b64_json`
- 如果下游显式传 `response_format` 且不是 `b64_json`，直接报错
- `n` 仅支持 `1`

## Data Flow

1. Flask 接收 `POST /v1/images/generations`
2. 解析并校验 OpenAI 风格请求体
3. 从 key 池取出本次请求的 key 尝试顺序
4. 用第一个 key 提交 deAPI `txt2img`
5. 如果提交阶段命中可切换错误，则切换下一把 key 重试提交
6. 一旦成功拿到 `request_id`，固定该 key 轮询 `request-status`
7. 轮询拿到 `result_url`
8. 下载图片二进制
9. 转成 base64
10. 返回 OpenAI 图片响应：

```json
{
  "created": 1760000000,
  "data": [
    {
      "b64_json": "..."
    }
  ]
}
```

## Error Handling

遵循 debug-first：

- 请求体缺少 `prompt`、`size` 非法、`n != 1`、`response_format != b64_json` 直接返回 400
- 上游提交阶段返回 `401/403/429/5xx` 或网络异常时，显式切换下一把 key 重试
- 所有 key 的提交都失败时，返回最后一次上游错误
- 上游已返回 `request_id` 后，不再切 key，不再重提任务
- 轮询状态为 `error` 时，直接把上游错误暴露给下游
- 超时、图片下载失败、返回体缺字段都直接报错

## Testing

测试分三层：

1. 配置和 key 池单元测试
   验证 key 文件读取、轮询顺序、空 key 文件报错。

2. 服务层单元测试
   验证：
   - 提交阶段失败会切 key
   - 成功后会轮询、下载并转 base64
   - 一旦拿到 `request_id`，轮询阶段不会切 key

3. Flask 接口测试
   验证：
   - `POST /v1/images/generations` 返回 OpenAI 风格 `b64_json`
   - 非法 `response_format` / `n` 返回 400
   - 上游错误返回结构化 JSON 错误
