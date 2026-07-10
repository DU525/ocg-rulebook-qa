# 🚀 快速开始

本指南将帮助你在5分钟内启动这个项目！

---

## 前置要求

确保你已安装以下工具：

- **Python** 3.9+
- **Node.js** 18+
- **Git**

---

## 步骤1：获取代码

```bash
git clone https://github.com/your-username/ocg-rulebook-qa.git
cd ocg-rulebook-qa
```

---

## 步骤2：启动后端

### 方法A：使用Conda环境（推荐）

```bash
cd backend

# 创建conda环境
conda env create -f environment.yml

# 激活环境
conda activate ocg-qa

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 OpenAI/MiniMax API Key

# 启动后端
python run.py
```

### 方法B：使用Python虚拟环境

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/Mac
source venv/bin/activate
# Windows
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 API Key

# 启动后端
python run.py
```

后端启动成功后会显示：

```
 * Running on http://127.0.0.1:5000
```

---

## 步骤3：启动前端

打开一个新的终端窗口：

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端启动成功后会显示：

```
VITE v5.4.21  ready in 633 ms
➜  Local:   http://localhost:3006/
```

---

## 步骤4：访问应用

在浏览器中打开：

```
http://localhost:3006
```

选择你要使用的游戏规则（OCG或DM），就可以开始提问了！

---

## 常见问题

### Q1: 没有API Key怎么办？

可以先访问以下链接获取：

- OpenAI: https://platform.openai.com/api-keys
- MiniMax: https://platform.minimax.com/

### Q2: 后端启动后，前端无法连接？

检查以下几点：

1. 后端是否真的在运行（访问 http://127.0.0.1:5000/api/v1/health 测试）
2. 前端.env中的API地址是否正确
3. 端口5000和3006是否被占用

### Q3: 知识库如何初始化？

如果你的data目录是空的，可以运行：

```bash
cd backend
python scripts/download_rules.py  # 下载规则书
python scripts/init_knowledge_base.py  # 初始化向量数据库
```

---

## 下一步

- 了解项目技术栈：看 [README.md](README.md)
- 看优化历程：看 [TECHNICAL_BLOG.md](docs/TECHNICAL_BLOG.md)
- 准备面试：看 [INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md)
