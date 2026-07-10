# LLM API 协议分析

> 本文档详细分析 OpenAI 兼容 API 的核心协议，用于面试展示"深入理解 LLM API 底层机制"

---

## 1. OpenAI API 核心协议

### 1.1 认证方式
- **Bearer Token**：`Authorization: Bearer sk-xxx`
- 放在 HTTP Header 中，不需要在 URL 中传递
- 所有厂商兼容 API 都使用此方式

### 1.2 核心端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/v1/chat/completions` | POST | 对话生成（最常用） |
| `/v1/models` | GET | 获取可用模型列表 |

### 1.3 请求体格式（非流式）

```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好"}
  ],
  "temperature": 0.3,
  "max_tokens": 1500
}
```

### 1.4 响应体格式（非流式）

```json
{
  "id": "chatcmpl-xxx",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35}
}
```

---

## 2. SSE 流式协议

### 2.1 请求差异
- 请求体添加 `"stream": true`
- 响应为 Server-Sent Events 格式
- Content-Type: `text/event-stream`

### 2.2 响应格式
SSE 协议规定：
- 每行以 `data: ` 开头
- 事件之间用空行分隔
- 结束标记为 `data: [DONE]`

```
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"你"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"好"},"index":0}]}

data: [DONE]
```

### 2.3 前端解析流程
```javascript
fetch(url, { 
  method: 'POST',
  body: JSON.stringify({ stream: true }) 
})
  .then(r => r.body.getReader())
  .then(reader => {
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      // 解析 data: 行，提取 content 字段
      const text = decoder.decode(value);
      // 处理 SSE 格式
    }
  });
```

---

## 3. 各厂商 API 对比

| 厂商 | Base URL | 模型名 | 是否兼容 OpenAI | 流式支持 | 特点 |
|------|----------|--------|----------------|----------|------|
| OpenAI | https://api.openai.com/v1 | gpt-4 | - | ✅ | 基准协议 |
| MiniMax | https://api.minimax.chat/v1 | MiniMax-M2.5 | ✅ 完全兼容 | ✅ | 中文理解强 |
| Anthropic | https://api.anthropic.com | claude-3-sonnet |  需适配 | ✅ | 长文本优秀 |
| Ollama | http://localhost:11434 | llama3 | ✅ 兼容 | ✅ | 本地部署 |
| DeepSeek | https://api.deepseek.com | deepseek-chat | ✅ 兼容 | ✅ | 性价比高 |

---

## 4. 本项目实现

### 4.1 实现方式

| Provider | 实现方式 | 依赖 | 用途 |
|----------|----------|------|------|
| `OpenAICompatibleProvider` | OpenAI SDK | `openai` 包 | 日常使用 |
| `RawHTTPProvider` | 纯 HTTP 请求 | `requests` 包 | 面试展示底层协议 |
| `MiniMaxProvider` | 继承 OpenAICompatibleProvider | `openai` 包 | MiniMax 专用 |

### 4.2 关键代码位置

- **抽象基类**：[llm_provider.py](../backend/app/services/llm_provider.py#L14-L38)
- **OpenAI SDK 实现**：[llm_provider.py](../backend/app/services/llm_provider.py#L40-L93)
- **纯 HTTP 实现**：[llm_provider.py](../backend/app/services/llm_provider.py#L196-L302)
- **工厂模式**：[llm_provider.py](../backend/app/services/llm_provider.py#L304-L366)
- **降级策略**：[llm_provider.py](../backend/app/services/llm_provider.py#L146-L193)

---

## 5. 错误处理

### 5.1 常见错误码

| 状态码 | 含义 | 处理方式 |
|--------|------|----------|
| 401 | 认证失败 | 检查 API Key |
| 429 | 请求过于频繁 | 限流/等待重试 |
| 500 | 服务器错误 | 切换备用模型 |
| 503 | 服务不可用 | 切换备用模型 |

### 5.2 重试策略

1. **第一次失败**：等待 1 秒后重试
2. **第二次失败**：等待 2 秒后重试
3. **第三次失败**：切换到备用模型

### 5.3 降级策略

- 主模型：OpenAI GPT-4
- 备用模型 1：MiniMax MiniMax-M2.5
- 备用模型 2：本地 Ollama llama3

---

## 6. 性能优化

### 6.1 连接池
使用 `requests.Session()` 复用 TCP 连接，减少握手开销

### 6.2 超时控制
- 非流式请求：30 秒超时
- 流式请求：60 秒超时

### 6.3 批量处理
嵌入模型推理使用批量处理（batch=32），提升吞吐量

---

## 7. 安全注意事项

### 7.1 API Key 保护
- 不硬编码在代码中
- 使用环境变量或 `.env` 文件
- 不提交到版本控制

### 7.2 请求限流
- 基于 IP 的滑动窗口限流
- 问答接口：5 次/分钟
- 上传接口：3 次/分钟

### 7.3 日志脱敏
- 不记录完整 API Key
- 不记录用户敏感信息
