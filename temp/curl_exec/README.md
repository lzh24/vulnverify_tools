# Curl Execute Service

一个基于 FastAPI 的 curl 执行服务，支持并发请求和认证保护。

## 功能特性

- 执行任意 curl 命令
- 并发控制（最大 300 个并发）
- Header 认证保护
- 健康检查端点
- CORS 支持

## 快速开始

### 使用 Docker 部署

构建镜像：
```bash
docker build -t curl-exec-service .
```

运行容器：
```bash
docker run -d \
  --name curl-exec \
  -p 8000:8000 \
  -e CURL_EXEC_AUTH_TOKEN=your-secure-token \
  curl-exec-service
```

### 本地开发

安装依赖：
```bash
pip install -r requirements.txt
```

启动服务：
```bash
uvicorn curl_exec:app --host 0.0.0.0 --port 8000 --reload
```

## 环境变量

| 变量名 | 默认值 | 描述 |
|-------|--------|------|
| `CURL_EXEC_AUTH_TOKEN` | `default-token-please-change` | 认证令牌 |
| `CURL_EXEC_AUTH_HEADER` | `X-Auth-Token` | 认证头名称 |

## API 接口

### 执行 curl 命令

**POST** `/execute-curl`

请求体：
```json
{
  "curl_args": ["https://httpbin.org/get"],
  "timeout": 15
}
```

示例：
```bash
curl -X POST 'http://127.0.0.1:8000/execute-curl' -H 'Content-Type: application/json' -H 'X-Auth-Token: your-secure-token-here' -d '{
  "curl_args": ["https://www.baidu.com",
    "-X", "POST",
    "-H", "Host: example.com",
    "-H", "Content-Type: application/json",
    "-H", "Authorization: Bearer token123",
    "--data", "{\"usernam\": \"admin\", \"password\": \"password\"}"],
  "timeout": 15
}'
```

### 健康检查

**GET** `/health`

```bash
curl http://localhost:8000/health
```

## 认证

除了健康检查端点外，所有 API 都需要通过 Header 认证：

- `GET /health` (健康检查) - **无需认证**

以下端点**需要认证**：
- `GET /` (根路径)
- `POST /execute-curl` (执行 curl 命令)
- `/docs` (API 文档)
- `/openapi.json` (OpenAPI 规范)

默认使用 `X-Auth-Token` 头，可以通过 `CURL_EXEC_AUTH_HEADER` 环境变量修改。

## 使用 docker-compose 部署

创建 `.env` 文件设置环境变量：
```bash
CURL_EXEC_AUTH_TOKEN=your-secure-token-here
CURL_EXEC_AUTH_HEADER=X-Auth-Token
```

启动服务：
```bash
docker-compose up -d
```

查看日志：
```bash
docker-compose logs -f
```

停止服务：
```bash
docker-compose down
```

## 生产令牌

```
replace-with-a-strong-token
```
