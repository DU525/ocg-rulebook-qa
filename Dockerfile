# OCG规则书问答系统 - Docker多阶段构建
# 使用方法: docker build -t ocg-rulebook-qa .

# ============================================
# Stage 1: Frontend Build
# ============================================
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制前端代码
COPY frontend/package.json frontend/package-lock.json* ./

# 安装前端依赖
RUN npm install

# 复制前端源码
COPY frontend/ ./

# 构建前端
RUN npm run build

# ============================================
# Stage 2: Backend Runtime
# ============================================
FROM python:3.10-slim AS backend

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production \
    HF_ENDPOINT=https://hf-mirror.com

# 安装系统依赖（PDF处理需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# 复制后端代码
COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 创建数据目录
RUN mkdir -p /app/backend/data/vector_db /app/backend/data/conversations

# 安装Python依赖
RUN pip install --no-cache-dir -r backend/requirements.txt

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/v1/health')" || exit 1

# 启动命令
CMD ["python", "backend/run.py"]