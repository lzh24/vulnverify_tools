# ============================================================
# Builder 阶段：Cython 编译核心模块为 .so
# ============================================================
FROM python:3.11-slim AS builder

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt Cython -i https://mirrors.aliyun.com/pypi/simple

COPY . .

RUN python setup.py build_ext --inplace

# ============================================================
# 运行镜像（最终阶段）
# ============================================================
FROM python:3.11-slim

WORKDIR /app

ENV TZ=Asia/Shanghai
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    chromium \
    chromium-driver \
    wget \
    gnupg \
    nmap \
    dnsutils \
    telnet \
    iputils-ping \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# Copy source
COPY . .

# 带入 Cython 编译产物（.so 优先级高于 .pyc，核心模块走 .so）
COPY --from=builder /build/core/auth*.so            ./core/
COPY --from=builder /build/core/base_tool_service*.so ./core/
COPY --from=builder /build/core/image_hosting*.so   ./core/
COPY --from=builder /build/core/logger*.so          ./core/
COPY --from=builder /build/core/mcp_server*.so      ./core/
COPY --from=builder /build/core/tool_manager*.so    ./core/

# 后端源码加固：运行镜像只保留编译产物（.pyc），不带明文 .py
#   core/config.py 是 pydantic BaseSettings，保持 .pyc（不删其 .py 编译产物）
#   mcp_stdio.py 是入口脚本（if __name__ == "__main__"），pyc 化即可
#   tools/*/main.py 是 importlib.import_module 动态加载的工具插件，保留明文 .py
RUN python -m compileall -b -q -f \
        main.py mcp_stdio.py core \
    && find core -type d -name __pycache__ -exec rm -rf {} + \
    && find core -name '*.py' -delete \
    && rm -f main.py mcp_stdio.py setup.py \
    && find tools -type d -name __pycache__ -exec rm -rf {} + \
    && find tools -name 'test_*.py' -delete \
    && find tools -name 'README.md' -delete \
    && find tools -name 'Dockerfile' -delete \
    && find tools -name 'requirements.txt' -delete \
    && find tools -name '.env.example' -delete \
    && rm -f .dockerignore Dockerfile .env.example pyproject.toml

# Expose port
EXPOSE 8000

# Run the unified service
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2}"]
