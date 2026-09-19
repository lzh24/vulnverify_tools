# 使用 Python 3.9 镜像
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖 - Chromium 和相关工具
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 注意：在统一服务框架中，工具不需要单独部署
# 此 Dockerfile 仅作为参考，实际部署时工具会被集成到主服务中
# 如需独立部署，请参考下面的配置

# 复制核心框架代码
COPY ../../core ./core

# 复制工具代码
COPY main.py .

# 复制环境配置（可选）
COPY .env* ./

# 暴露服务端口
EXPOSE 8000

# 启动服务
CMD ["python", "main.py"]