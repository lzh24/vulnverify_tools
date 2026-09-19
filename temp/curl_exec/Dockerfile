# 使用官方 Python 运行时作为基础镜像
FROM  docker.m.ixdev.cn/library/python:3.11-slim

# 设置工作目录
WORKDIR /app

RUN  ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（包括 curl）
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# 复制应用代码
COPY curl_exec.py .

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV CURL_EXEC_AUTH_TOKEN=your-secure-token-here
ENV CURL_EXEC_AUTH_HEADER=X-Auth-Token

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "curl_exec:app", "--host", "0.0.0.0", "--port", "8000"]