# Chat Completions Image Compatibility Design

**Goal**

为当前 deAPI 图片中转服务新增 `POST /v1/chat/completions` 兼容层，让只会调用 Chat Completion API 的本地客户端也能触发生图，并把最终图片作为 Markdown data URL 返回。

## Context

当前服务已经支持：

- `GET /v1/models`
- `POST /v1/images/generations`
- SQLite 管理后台

实际客户端日志显示：

- 请求路径是 `POST /v1/chat/completions`
- `messages` 中最后一条 `user` 消息是生图提示词
- `stream: true`
- `model: ZImageTurbo_INT8`
- `seed: undefined`

当前服务没有 `chat/completions` 路由，因此客户端收到 `404`。

## Compatibility Strategy

采用“chat -> image relay”最小兼容方案：

1. 读取 `messages` 中最后一条 `user` 文本作为 prompt
2. 如果顶层 `prompt` 有值，则优先使用顶层 `prompt`
3. `seed` 未提供时由服务端自动生成随机 32 位整数
4. 调用现有图片代理服务，复用已有上游轮询与 key 调度
5. 将返回的 `b64_json` 包装为 Markdown 图片：
   `![](data:image/png;base64,...)`

## Response Shapes

### Non-streaming

返回 OpenAI Chat Completion 风格对象：

- `object: chat.completion`
- `choices[0].message.role = assistant`
- `choices[0].message.content = Markdown 图片`

### Streaming

客户端请求 `stream: true` 时返回 SSE：

1. assistant role chunk
2. content chunk，内容是完整 Markdown 图片
3. finish chunk，`finish_reason = stop`
4. `data: [DONE]`

说明：

- 这不是增量生图流式，而是“完成后再按 SSE 格式发出”
- 这样能兼容只接受流式 Chat API 的客户端，同时避免中途就返回 200 后无法正确处理生成失败

## Prompt Extraction Rules

- 优先使用顶层 `prompt`
- 否则取最后一条 `role = user` 的消息
- `content` 如果是字符串，直接使用
- `content` 如果是数组，只拼接其中 `type = text` 的 `text`
- 若最终没有可用 prompt，返回 400

## MIME Handling

根据图片字节头识别 MIME：

- PNG -> `image/png`
- JPEG -> `image/jpeg`
- WEBP -> `image/webp`
- 无法识别时默认 `image/png`

## Testing

测试覆盖：

- 非流式 `chat/completions`
- 流式 `chat/completions`
- 自动补 `seed`
- 从 `messages` 提取 prompt
- 缺少 prompt 返回 400
- 保持现有图片接口和后台测试通过
