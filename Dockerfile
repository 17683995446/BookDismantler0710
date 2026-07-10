FROM python:3.12-slim AS base

LABEL org.opencontainers.image.title="Book Dismantler"
LABEL org.opencontainers.image.description="AI 驱动的开源拆书工具"
LABEL org.opencontainers.image.license="MIT"

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件以利用 Docker 缓存
COPY pyproject.toml README.md LICENSE ./
COPY config/ ./config/
COPY src/ ./src/

# 安装依赖
RUN pip install --no-cache-dir -e ".[web,export]"

# 安装 Playwright 浏览器（用于 PNG 导出，可选）
RUN playwright install chromium --with-deps || true

# 创建输出目录
RUN mkdir -p /app/output

ENV BOOK_DISMANTLER_OUTPUT_DIR=/app/output
ENV BOOK_DISMANTLER_LOG_LEVEL=INFO

EXPOSE 8000

# 默认启动 Web 服务
CMD ["python", "-m", "book_dismantler", "serve", "--host", "0.0.0.0", "--port", "8000"]
