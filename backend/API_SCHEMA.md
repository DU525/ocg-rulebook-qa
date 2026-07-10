# OCG 规则书问答系统 API 文档

**版本**：1.0.0  
**基础路径**：`/api/v1`  
**更新时间**：2026-05-19

---

## 目录

1. [健康检查](#1-get-apiv1health)
2. [系统指标](#2-get-apiv1metrics)
3. [问答接口](#3-post-apiv1chatquestion)
4. [对话列表](#4-get-apiv1conversations)
5. [对话详情](#5-get-apiv1conversationsid)
6. [错误码说明](#错误码说明)

---

## 1. GET /api/v1/health

健康检查接口，用于监控服务状态和向量库状态。

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| - | - | - | 无 |

### 成功响应

```json
{
  "status": "healthy",
  "vector_store_count": 1234,
  "timestamp": "2026-05-19T01:30:55.123456"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 服务状态，`healthy` 表示正常 |
| vector_store_count | integer | 向量库中文档块数量 |
| timestamp | string | ISO 8601 格式时间戳 |

### 响应示例

**成功 (200 OK)**
```json
{
  "status": "healthy",
  "vector_store_count": 1547,
  "timestamp": "2026-05-19T01:30:55.000000"
}
```

---

## 2. GET /api/v1/metrics

获取系统运行指标，包括对话统计和知识库规模。

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| - | - | - | 无 |

### 成功响应

```json
{
  "success": true,
  "data": {
    "total_conversations": 42,
    "total_messages": 156,
    "knowledge_base_size": 1547
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| data.total_conversations | integer | 历史对话总数 |
| data.total_messages | integer | 消息总数（含问答双方） |
| data.knowledge_base_size | integer | 知识库文档块数量 |

### 响应示例

**成功 (200 OK)**
```json
{
  "success": true,
  "data": {
    "total_conversations": 42,
    "total_messages": 156,
    "knowledge_base_size": 1547
  }
}
```

---

## 3. POST /api/v1/chat/question

问答接口，发送问题并获取 RAG 增强的回答。会自动保存对话历史。

### 请求

**Headers**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| Content-Type | string | 是 | `application/json` |

**Body**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 用户问题，最长 2000 字符 |
| conversation_id | string | 否 | 对话 ID，新对话时可不传，系统自动生成 UUID |

### 请求示例

```json
{
  "question": "怪兽的效果被无效后还会破坏吗？",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 成功响应

```json
{
  "success": true,
  "data": {
    "answer": "根据规则，当怪兽效果被『效果无效』或『效果被无效』的字句效果无效时...",
    "citations": [
      {
        "source": "c02/master_rule.md",
        "title": "大师规则·怪兽效果",
        "text": "怪兽在场上发动的效果被无效时，该效果不产生任何效果...",
        "relevance": 0.923
      }
    ],
    "confidence": 0.923,
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "response_time_ms": 1250
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| data.answer | string | LLM 生成的回答 |
| data.citations | array | 引用来源列表 |
| data.citations[].source | string | 来源文件路径 |
| data.citations[].title | string | 章节标题 |
| data.citations[].text | string | 引用文本（最多 200 字符） |
| data.citations[].relevance | float | 相关度评分 (0-1) |
| data.confidence | float | 回答置信度 (0-1) |
| data.conversation_id | string | 对话 ID（新建或传入的） |
| data.response_time_ms | integer | 响应耗时（毫秒） |

### 失败响应

**空问题 (400 Bad Request)**
```json
{
  "success": false,
  "error": {
    "code": "EMPTY_QUESTION",
    "message": "问题不能为空"
  }
}
```

### 完整响应示例

**成功 (200 OK)**
```json
{
  "success": true,
  "data": {
    "answer": "当怪兽效果被『效果无效』或『效果被无效』的字句效果无效时，该效果不产生任何效果。但需注意，被无效的是「效果」，而非「怪兽的存在」，所以如果该怪兽有「不会被战斗破坏」等永续效果，即使效果被无效，那些永续效果仍在适用。",
    "citations": [
      {
        "source": "c02/master_rule.md",
        "title": "大师规则·怪兽效果",
        "text": "怪兽在场上发动的效果被无效时，该效果不产生任何效果。但怪兽本身仍然留在场上，如果存在不受该效果影响的怪兽，则效果仍然适用。",
        "relevance": 0.945
      },
      {
        "source": "c01/game_flow.md",
        "title": "变更的规则·效果处理",
        "text": "「效果无效」指的是使怪兽或魔法陷阱的效果无法发动或适用的状态。被无效的效果不再产生任何效果。",
        "relevance": 0.812
      }
    ],
    "confidence": 0.945,
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "response_time_ms": 1380
  }
}
```

---

## 4. GET /api/v1/conversations

获取对话列表，按最后更新时间倒序排列，最多返回 50 条。

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| - | - | - | 无 |

### 成功响应

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "怪兽的效果被无效后还会破坏吗？",
      "created_at": "2026-05-19T01:25:00",
      "updated_at": "2026-05-19T01:28:30"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| data | array | 对话列表 |
| data[].id | string | 对话 UUID |
| data[].title | string | 对话标题（取自第一条用户问题前 50 字符） |
| data[].created_at | string | 创建时间 ISO 8601 |
| data[].updated_at | string | 最后更新时间 ISO 8601 |

### 响应示例

**成功 (200 OK)**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "怪兽的效果被无效后还会破坏吗？",
      "created_at": "2026-05-19T01:25:00",
      "updated_at": "2026-05-19T01:28:30"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "title": "仪式召唤需要什么条件？",
      "created_at": "2026-05-18T15:20:00",
      "updated_at": "2026-05-18T15:22:45"
    }
  ]
}
```

---

## 5. GET /api/v1/conversations/:id

获取指定对话的完整消息列表，包含问答历史和引用信息。

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id (路径参数) | string | 是 | 对话 UUID |

### 成功响应

```json
{
  "success": true,
  "data": [
    {
      "id": "msg-uuid-001",
      "role": "user",
      "content": "怪兽的效果被无效后还会破坏吗？",
      "citations": null,
      "created_at": "2026-05-19T01:25:00"
    },
    {
      "id": "msg-uuid-002",
      "role": "assistant",
      "content": "当怪兽效果被无效时...",
      "citations": [
        {
          "source": "c02/master_rule.md",
          "title": "大师规则·怪兽效果",
          "text": "怪兽在场上发动的效果被无效时...",
          "relevance": 0.945
        }
      ],
      "created_at": "2026-05-19T01:25:05"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| data | array | 消息列表（按时间正序） |
| data[].id | string | 消息 UUID |
| data[].role | string | 角色，`user` 或 `assistant` |
| data[].content | string | 消息内容 |
| data[].citations | array/null | 引用列表（assistant 消息有，用户消息为 null） |
| data[].created_at | string | 创建时间 ISO 8601 |

### 响应示例

**成功 (200 OK)**
```json
{
  "success": true,
  "data": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440001",
      "role": "user",
      "content": "怪兽的效果被无效后还会破坏吗？",
      "citations": null,
      "created_at": "2026-05-19T01:25:00"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "role": "assistant",
      "content": "当怪兽效果被『效果无效』或『效果被无效』的字句效果无效时，该效果不产生任何效果。但需注意，被无效的是「效果」，而非「怪兽的存在」。",
      "citations": [
        {
          "source": "c02/master_rule.md",
          "title": "大师规则·怪兽效果",
          "text": "怪兽在场上发动的效果被无效时，该效果不产生任何效果。但怪兽本身仍然留在场上...",
          "relevance": 0.945
        }
      ],
      "created_at": "2026-05-19T01:25:05"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440003",
      "role": "user",
      "content": "那灵灭封印呢？",
      "citations": null,
      "created_at": "2026-05-19T01:27:00"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440004",
      "role": "assistant",
      "content": "『灵灭封印』的效果是使那只怪兽不能作为召唤·反转召唤·特殊召唤的结果上场...",
      "citations": [
        {
          "source": "c01/rule_changes.md",
          "title": "变更的规则·禁止·限制表",
          "text": "灵灭封印：使那只怪兽不能作为召唤·反转召唤·特殊召唤的结果上场...",
          "relevance": 0.891
        }
      ],
      "created_at": "2026-05-19T01:27:08"
    }
  ]
}
```

---

## 错误码说明

| HTTP 状态码 | 错误码 | 错误信息 | 说明 |
|-------------|--------|----------|------|
| 400 | `EMPTY_QUESTION` | 问题不能为空 | 问答接口 `question` 参数为空 |
| 400 | `NO_FILE` | 未找到上传文件 | 文档上传接口未检测到文件 |
| 400 | `INVALID_FILE_TYPE` | 不支持的文件格式 | 上传文件格式不是 pdf/docx/txt/rst |
| 500 | - | 服务器内部错误 | RAG 引擎或数据库异常 |

### 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 固定为 `false` |
| error.code | string | 错误码，用于程序化处理 |
| error.message | string | 人类可读的错误描述 |

---

## 附录：数据模型

### Conversation（对话）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string(36) | UUID，主键 |
| title | string(255) | 对话标题 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 最后更新时间 |

### Message（消息）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string(36) | UUID，主键 |
| conversation_id | string(36) | 所属对话 ID |
| role | string(20) | 角色：`user` 或 `assistant` |
| content | text | 消息内容 |
| citations | json | 引用列表 |
| created_at | datetime | 创建时间 |

---

*文档由 knowledge-expert 自动生成，2026-05-19*