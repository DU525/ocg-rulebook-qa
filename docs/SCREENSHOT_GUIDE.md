# 📸 OCG/DM RAG问答系统 - 演示截图清单

本清单指导你截图哪些界面，用于GitHub README、技术博客、内推展示。

---

## 必截截图（6张）

### 截图1：首页 - 双游戏规则选择
**文件命名**：`01-home-game-switch.png`
**截取内容**：
- 打开 http://localhost:3006
- 显示OCG/DM切换按钮
- 展示游戏Logo
- 截图整个浏览器窗口（含URL）
**标注重点**：双知识库、一键切换

### 截图2：问答界面 - 流式输出
**文件命名**：`02-chat-streaming-response.png`
**截取内容**：
- 输入问题："什么是连锁？"
- 系统正在生成回答（显示打字机效果）
- 显示"思考中"加载动画
**标注重点**：SSE流式、83字/秒、流畅体验

### 截图3：回答+引用 - 知识溯源
**文件命名**：`03-answer-with-citations.png`
**截取内容**：
- 完整回答显示
- 下方引用来源（含相似度评分）
- 规则原文引用
**标注重点**：RAG溯源、忠实度保证

### 截图4：配置面板 - 实时调整
**文件命名**：`04-config-panel.png`
**截取内容**：
- 打开配置面板
- 显示Top-K、Temperature、Prompt模板等参数
- 可实时调整
**标注重点**：工程化能力、无需重启

### 截图5：性能监控 - 量化指标
**文件命名**：`05-performance-metrics.png`
**截取内容**：
- 性能监控面板
- QPS、延迟、缓存命中率等数据
- RAGAS指标趋势
**标注重点**：可观测性、数据驱动

### 截图6：对话历史 - 用户体验
**文件命名**：`06-conversation-history.png`
**截取内容**：
- 侧边栏对话列表
- 搜索历史对话
- 继续对话功能
**标注重点**：完整用户体验

---

## 可选截图（4张）

### 截图7：文档上传 - 知识库扩展
**文件命名**：`07-document-upload.png`
**截取内容**：文档上传界面，支持PDF/DOCX/TXT/RST

### 截图8：Markdown渲染 - 代码高亮
**文件命名**：`08-markdown-code-highlight.png`
**截取内容**：包含代码块的回答，显示语法高亮和复制按钮

### 截图9：移动端响应式
**文件命名**：`09-mobile-responsive.png`
**截取内容**：浏览器开发者工具切换到移动端视图

### 截图10：API文档 - Swagger/OpenAPI
**文件命名**：`10-api-docs.png`
**截取内容**：http://127.0.0.1:5000/api/v1/health 返回JSON

---

## 截图技巧

### 工具推荐
- **Windows**：Win+Shift+S 区域截图
- **浏览器插件**：GoFullPage 全页面截图
- **标注工具**：Snipaste（贴图+标注）

### 截图规范
1. **统一尺寸**：建议1920x1080或1600x900
2. **干净背景**：关闭无关标签页
3. **中文界面**：保持中文，展示本土化
4. **标注工具**：用红色箭头/框标注重点
5. **文件命名**：按编号排序，方便管理

### 优化建议
- **截图前清理数据**：确保没有敏感API Key
- **使用示例数据**：准备几个典型问题和回答
- **展示亮点**：优先展示RAG溯源、性能数据、配置面板

---

## 截图存放位置

```
ocg-rulebook-qa/
└── docs/
    └── screenshots/
        ├── 01-home-game-switch.png
        ├── 02-chat-streaming-response.png
        ├── 03-answer-with-citations.png
        ├── 04-config-panel.png
        ├── 05-performance-metrics.png
        ├── 06-conversation-history.png
        └── ...（可选截图）
```

创建目录：
```bash
mkdir -p docs/screenshots
```

---

## 截图后更新README

在README.md中添加截图展示：

```markdown
## 📸 界面展示

### 双知识库切换
![游戏规则切换](docs/screenshots/01-home-game-switch.png)

### 流式问答
![流式输出](docs/screenshots/02-chat-streaming-response.png)

### 知识溯源
![回答与引用](docs/screenshots/03-answer-with-citations.png)
```
