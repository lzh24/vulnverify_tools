# 漏洞验证工具服务框架 (VulnVerify Tools)

本项目是一个统一的漏洞验证外部工具框架。所有工具运行在一个独立的 Docker 容器中（默认端口 8000），遵循统一的 API 规范、认证机制和部署模式。

核心代码位于 `core/` 目录，具体工具插件位于 `tools/` 目录。

## ✨ 特性

- 🚀 统一的 REST API 接口
- 🔌 支持 MCP (Model Context Protocol) 协议
- 🛡️ Bearer Token 认证机制
- 📦 动态工具加载和管理
- 🐳 Docker 容器化部署

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker 容器 (端口 8000)                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    FastAPI 主应用                        │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │ │
│  │  │ REST API    │    │ MCP 服务    │    │ 工具管理器   │  │ │
│  │  │ /           │    │ /mcp        │    │ /core        │  │ │
│  │  │ /health     │    │ /mcp/       │    │              │  │ │
│  │  │ /execute/*  │    │ /mcp/mcp/   │    │              │  │ │
│  │  │             │    │ /mcp/mcp/   │    │              │  │ │
│  │  │             │    │ messages    │    │              │  │ │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │ │
│  │                           │                            │ │
│  │                           ▼                            │ │
│  │  ┌─────────────────────────────────────────────────────┐│ │
│  │  │                  工具插件目录 (tools/)              ││ │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ││ │
│  │  │  │ curl-exec   │  │ dnslog      │  │ screenshot  │  ││ │
│  │  │  │             │  │             │  │             │  ││ │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘  ││ │
│  │  └─────────────────────────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**架构说明**：
- 所有服务（REST API 和 MCP）运行在同一个 ASGI 应用中，共享端口 8000
- MCP 服务通过 `/mcp` 路径挂载到主应用上
- 工具管理器负责动态加载和管理所有工具插件
- 每个工具插件都是独立的 Python 模块，可动态扩展

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Docker & Docker Compose (可选，推荐)

### 1. 配置环境变量

复制 `.env.example` 到 `.env` 并配置：

```bash
cp .env.example .env
```

主要配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TOOL_TOKEN` | API 认证 Token（必需） | - |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 监听端口 | `8000` |
| `WEB_CONCURRENCY` | Uvicorn worker 数 | `2` |
| `ENABLE_REQUEST_LOGGING` | 是否开启请求级日志 | `false` |
| `SCREENSHOT_MAX_CONCURRENCY` | 截图工具最大并发数 | `2` |
| `SCREENSHOT_EXECUTOR_WORKERS` | 截图工具线程池大小 | `2` |
| `SCREENSHOT_PAGE_LOAD_TIMEOUT` | 截图页面加载超时秒数 | `20` |
| `SCREENSHOT_ELEMENT_WAIT_TIMEOUT` | 截图等待页面元素超时秒数 | `10` |
| `SCREENSHOT_REQUEST_TIMEOUT` | 截图复杂请求 HTTP 超时秒数 | `15` |
| `SCREENSHOT_MAX_SLEEP_TIME` | 截图 `sleep_time` 最大允许值 | `3` |
| `SCREENSHOT_UPLOAD_ENABLED` | 是否上传截图到图床 | `true` |
| `SCREENSHOT_RETURN_BASE64_BY_DEFAULT` | screenshot 默认是否返回 Base64 | `false` |
| `TERMINAL_HUB_RETURN_BASE64_BY_DEFAULT` | terminal_hub 默认是否返回 Base64 | `false` |
| `CHROMEDRIVER_PATH` | ChromeDriver 路径（截图工具） | `/usr/bin/chromedriver` |
| `CHROMIUM_BINARY` | Chromium 二进制路径（截图工具） | `/usr/bin/chromium` |
| `DNSLOG_TYPE` | DNSLog provider：`internal`（默认，私有化自建）/ `callback_red`（公共 callback.red）/ `dnslog_cn`（公共 dnslog.cn） | `internal` |
| `DNSLOG_DOMAIN` | `internal` 时自建 DNSLog 主域名（如 `your-dnslog.example.com`） | - |
| `DNSLOG_TOKEN` | `internal` 时自建 DNSLog 鉴权 token | - |
| `DNSLOG_WEBSERVER` | `internal` 时自建 DNSLog 服务地址 `<host:port>` | - |
| `CALLBACK_RED_BASE_URL` | `callback_red` 时的公共 DNSLog 服务地址 | `https://callback.red` |
| `DNSLOG_CN_BASE_URL` | `dnslog_cn` 时的公共 DNSLog 服务地址 | `http://www.dnslog.cn` |

### 2. 启动服务

#### 方式一：Docker Compose (推荐)

```bash
# 启动服务 (构建并后台运行)
docker-compose up -d --build
```

`docker-compose.yml` 默认映射为宿主机 `8001 -> 容器 8000`。
本地 `docker-compose.yml` 已同步到与 Swarm 接近的性能参数，可直接用于预发布验证。

#### 方式二：本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
# 或使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 健康检查

确保服务已正常启动：

```bash
curl http://localhost:8001/health
```

如果是本地直接运行 `python main.py` 或 `uvicorn`，则使用 `http://localhost:8000/health`。

响应示例：
```json
{
  "status": "healthy",
  "service": "unified-tools",
  "version": "1.0.0",
  "tools": {
    "curl-exec": "1.1.0",
    "dnslog-service": "1.2.1",
    "screenshot": "1.0.0"
  }
}
```

## 🐳 Docker Swarm 集群部署

项目已经补充了 Swarm 部署文件和脚本，适合你这种多台机器的 Docker Swarm 环境。

### 1. 文件说明

- `docker-stack.yml`: 用于 `docker stack deploy` 的 Swarm 栈文件
- `docker-stack-global.yml`: 每个节点 1 个实例的 Swarm 栈文件
- `docker-stack-replicated.yml`: 指定副本数的 Swarm 栈文件
- `docker-cluster.yml`: 与 `docker-stack.yml` 保持兼容，可作为备用栈文件
- `scripts/build-and-push.sh`: 构建并推送镜像到私有仓库
- `scripts/swarm-deploy.sh`: 在 manager 节点部署或更新 stack
- `scripts/swarm-status.sh`: 查看 stack、task 和服务日志
- `.env.swarm.example`: Swarm 环境变量模板

### 2. 集群前置准备

你的 10 台机器既然已经组成 Swarm，下一步重点是让每台节点都能拉取私有仓库镜像。

如果你的私有镜像库是 `http://<registry-host>:5000`，每个 Swarm 节点都需要配置 `insecure-registries`：

```json
{
  "insecure-registries": ["<registry-host>:5000"]
}
```

配置位置通常是 `/etc/docker/daemon.json`，然后重启 Docker：

```bash
sudo systemctl restart docker
```

如果你的仓库已经做了 HTTPS 证书，则不需要 `insecure-registries`，直接保证各节点能访问该仓库即可。

建议先在每台节点验证一次：

```bash
docker login <registry-host>:5000
docker pull <registry-host>:5000/vulnverify/vulnverify-tools:latest
```

### 3. 构建并上传镜像到 5000 私库

先复制模板：

```bash
cp .env.swarm.example .env.swarm
```

然后至少修改这些变量：

- `IMAGE_REGISTRY=你的仓库IP或域名:5000`
- `TOOL_TOKEN=生产环境认证令牌`
- `DEPLOY_MODE=global` 或 `replicated`
- `SERVICE_REPLICAS=期望副本数`（仅 `replicated` 模式生效）
- `PUBLISHED_PORT=对外暴露端口`

执行构建推送：

```bash
REGISTRY=192.168.1.10:5000 \
IMAGE_NAMESPACE=vulnverify \
IMAGE_NAME=vulnverify-tools \
IMAGE_TAG=20260527 \
PUSH_LATEST=true \
./scripts/build-and-push.sh
```

如果仓库需要认证，可以一起带上：

```bash
REGISTRY=192.168.1.10:5000 \
REGISTRY_USERNAME=admin \
REGISTRY_PASSWORD='your-password' \
IMAGE_TAG=20260527 \
PUSH_LATEST=true \
./scripts/build-and-push.sh
```

推送完成后，脚本会输出最终镜像名，可直接写回 `.env.swarm` 的 `IMAGE_TAG`。

### 4. 在 Swarm manager 上部署

在 manager 节点执行：

```bash
cp .env.swarm.example .env.swarm
# 编辑 .env.swarm
./scripts/swarm-deploy.sh ./.env.swarm
```

默认会执行：

```bash
docker stack deploy --with-registry-auth -c docker-stack-global.yml vulnverify-tools
```

`docker-stack-global.yml` 当前使用 `ports.mode=host`。  
这表示访问某个节点的 `${PUBLISHED_PORT}` 时，会直接进入该节点本机上的服务实例，适合做逐节点可达性排查。

部署后查看状态：

```bash
./scripts/swarm-status.sh vulnverify-tools
```

查看某个服务日志：

```bash
./scripts/swarm-status.sh vulnverify-tools vulnverify-tools
```

### 5. 脚本使用方式

下面这 4 个脚本是常用入口：

#### `scripts/build-and-push.sh`

用途：构建镜像并推送到私有仓库。

```bash
# 推送指定 tag
REGISTRY=***REMOVED*** \
IMAGE_NAMESPACE=vulnverify \
IMAGE_NAME=vulnverify-tools \
IMAGE_TAG=20260527 \
./scripts/build-and-push.sh
```

```bash
# 同时推送 latest
REGISTRY=***REMOVED*** \
IMAGE_NAMESPACE=vulnverify \
IMAGE_NAME=vulnverify-tools \
IMAGE_TAG=20260527 \
PUSH_LATEST=true \
./scripts/build-and-push.sh
```

```bash
# 私库需要认证时
REGISTRY=***REMOVED*** \
REGISTRY_USERNAME=admin \
REGISTRY_PASSWORD='your-password' \
IMAGE_NAMESPACE=vulnverify \
IMAGE_NAME=vulnverify-tools \
IMAGE_TAG=20260527 \
./scripts/build-and-push.sh
```

#### `scripts/swarm-deploy.sh`

用途：在 Swarm manager 节点部署或更新服务。

```bash
# 使用默认 .env.swarm
./scripts/swarm-deploy.sh ./.env.swarm
```

```bash
# 使用自定义环境文件
./scripts/swarm-deploy.sh /path/to/your.env.swarm
```

部署前建议先确认 `.env.swarm` 中这些变量：

```env
IMAGE_REGISTRY=***REMOVED***
IMAGE_NAMESPACE=vulnverify
IMAGE_NAME=vulnverify-tools
IMAGE_TAG=20260527
TOOL_TOKEN=your-prod-token
PUBLISHED_PORT=8883
DEPLOY_MODE=global
WEB_CONCURRENCY=2
ENABLE_REQUEST_LOGGING=false
SCREENSHOT_MAX_CONCURRENCY=2
SCREENSHOT_EXECUTOR_WORKERS=2
SCREENSHOT_PAGE_LOAD_TIMEOUT=20
SCREENSHOT_ELEMENT_WAIT_TIMEOUT=10
SCREENSHOT_REQUEST_TIMEOUT=15
SCREENSHOT_MAX_SLEEP_TIME=3
SCREENSHOT_UPLOAD_ENABLED=true
SCREENSHOT_RETURN_BASE64_BY_DEFAULT=false
TERMINAL_HUB_RETURN_BASE64_BY_DEFAULT=false
PLACEMENT_CONSTRAINT='node.platform.os == linux'
```

#### `scripts/swarm-status.sh`

用途：查看 stack 状态、task 状态和服务日志。

```bash
# 查看 stack 服务与 task
./scripts/swarm-status.sh vulnverify-tools
```

```bash
# 追踪服务日志
./scripts/swarm-status.sh vulnverify-tools vulnverify-tools
```

#### `scripts/test-endpoint.sh`

用途：测试接口可达性、稳定性和基础性能指标。

```bash
# 默认测试 http://203.0.113.10:8883/
./scripts/test-endpoint.sh
```

```bash
# 500 次请求，20 并发
REQUESTS=500 CONCURRENCY=20 ./scripts/test-endpoint.sh
```

```bash
# 指定 URL
./scripts/test-endpoint.sh http://203.0.113.10:8883/health
```

```bash
# 指定超时、并发和状态码
TIMEOUT=10 CONCURRENCY=30 EXPECTED_STATUS=200 ./scripts/test-endpoint.sh http://203.0.113.10:8883/
```

输出包含：

- 总请求数
- 成功数 / 失败数
- 成功率
- 平均延迟
- P95 延迟
- 最大延迟
- 状态码分布
- 错误样例

#### `scripts/test-screenshot.sh`

用途：本地压测 `screenshot` 工具接口，重点验证截图接口在持续并发下是否会变卡。

```bash
# 默认压测 burp_screenshot，目标是本地 http://localhost:8001
./scripts/test-screenshot.sh
```

```bash
# 100 次请求，10 并发，压测 burp_screenshot
REQUESTS=100 CONCURRENCY=10 ./scripts/test-screenshot.sh
```

```bash
# 压测 web_screenshot，截图目标为本地 health 页面
MODE=web TARGET_URL=http://localhost:8001/health REQUESTS=50 CONCURRENCY=5 ./scripts/test-screenshot.sh
```

```bash
# 连 Base64 返回一起压，负载更高
INCLUDE_SCREENSHOT_BASE64=true REQUESTS=20 CONCURRENCY=2 ./scripts/test-screenshot.sh
```

输出会包含：

- 总请求数
- 成功数 / 失败数
- 成功率
- 平均延迟
- P95 延迟
- 最大延迟
- 状态码分布
- 主要错误类型
- 最慢请求样本

### 6. 滚动更新

发布新版本时，重新构建并推送一个新标签：

```bash
REGISTRY=192.168.1.10:5000 IMAGE_TAG=20260527-2 ./scripts/build-and-push.sh
```

然后修改 `.env.swarm` 中的 `IMAGE_TAG`，再次执行：

```bash
./scripts/swarm-deploy.sh ./.env.swarm
```

当前栈文件已经配置了：

- `deploy.mode`
- `replicas`
- `restart_policy`
- `update_config`
- `rollback_config`
- `placement.constraints`
- `resources limits/reservations`

也就是说，Swarm 会按滚动更新方式逐个替换副本，失败时自动回滚。

如果你希望 **每个节点都部署一个容器**，使用：

```env
DEPLOY_MODE=global
PLACEMENT_CONSTRAINT='node.platform.os == linux'
```

这样每个满足约束的 Swarm 节点都会启动 1 个实例。  
如果是 10 台 Linux 节点，最终通常会看到 10 个 task。

如果你要逐节点确认 `8883` 是否真的命中了该节点本机实例，建议使用：

```bash
python3 scripts/check_http_on_8883.py --path /health --json
```

返回结果里会带上：

- `instance_node_hostname`
- `instance_task_name`

这样可以确认某个节点的 `8883` 请求到底有没有进入对应节点自己的容器。

如果你希望按固定副本数部署，使用：

```env
DEPLOY_MODE=replicated
SERVICE_REPLICAS=3
PLACEMENT_CONSTRAINT='node.platform.os == linux'
```

### 7. 可达性与稳定性测试

仓库内已提供一个轻量测试脚本：

```bash
chmod +x scripts/test-endpoint.sh
./scripts/test-endpoint.sh
```

默认测试目标：

```text
http://203.0.113.10:8883/
```

常用示例：

```bash
# 基础可达性 + 100 次请求统计
./scripts/test-endpoint.sh

# 500 次请求，20 并发
REQUESTS=500 CONCURRENCY=20 ./scripts/test-endpoint.sh

# 指定 URL 和 10 秒超时
TIMEOUT=10 ./scripts/test-endpoint.sh http://203.0.113.10:8883/health
```

输出会包含：

- 总请求数
- 成功/失败数
- 成功率
- 平均延迟、P95、最大延迟
- 各状态码分布
- 错误样例

### 8. 性能优化建议

如果服务运行一段时间后开始变卡，优先检查并使用以下配置：

```env
WEB_CONCURRENCY=2
ENABLE_REQUEST_LOGGING=false
RESERVE_CPUS=0.5
LIMIT_CPUS=2.00
RESERVE_MEMORY=1024M
LIMIT_MEMORY=2G
```

当前仓库已经做了这几项优化：

- 容器默认使用 `uvicorn` 多 worker 启动
- 默认关闭每个请求的访问日志
- `dnslog` 工具从同步 `requests` 改为异步 `httpx`
- `screenshot` 工具增加了独立并发上限与专用线程池
- 截图后的图床上传改为在线程池中执行，避免阻塞事件循环
- 截图相关超时和 `sleep_time` 做了上限收口
- `screenshot` 和 `terminal_hub` 的 Base64 返回支持通过环境变量控制默认行为

如果仍然出现“运行一段时间后变卡”，建议继续排查：

- 是否某个工具接口被高频调用，尤其是截图工具
- `docker service logs` 中是否存在大量超时、异常堆栈
- 节点 CPU / 内存是否持续被打满
- 某些上游依赖是否响应很慢，导致 worker 堵塞

## 🔌 REST API 接口

### 认证方式

所有非公开接口（除 `/` 和 `/health` 外）均需要 Bearer Token 认证。
Token 在 `.env` 文件中通过 `TOOL_TOKEN` 配置。

Header 示例：
```
Authorization: Bearer <your-token>
```

### 工具执行接口

框架支持两种路由模式，推荐使用 **多层路由模式**。

#### 1. 多层路由模式 (推荐)

格式：`POST /execute/{tool_name}/{action_name}`

**示例：DNSLog 注册并获取随机子域名**
```bash
curl -X POST http://localhost:8000/execute/dnslog-service/register \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "length": 5
    }
  }'
```

#### 2. 基础路由模式 (兼容旧版)

格式：`POST /execute/{tool_name}`
需要在参数 `params` 中包含 `action` 字段（如果工具支持多动作）。

### 常用工具及参数说明

#### 🌐 Curl 执行工具 (`curl-exec`)

**功能 1: 执行 Curl 命令 (`curl_args`)**
```bash
POST /execute/curl-exec/curl_args

{
  "params": {
    "curl_args": ["-L", "http://example.com"],
    "timeout": 10
  }
}
```

**功能 2: 发送原始 HTTP 请求 (`rawhttp`)**
```bash
POST /execute/curl-exec/rawhttp

{
  "params": {
    "url": "http://example.com",
    "raw_http": "GET / HTTP/1.1\nHost: example.com\n\n"
  }
}
```

#### 🔍 DNSLog 工具 (`dnslog-service`)

> 本工具不再内置任何 DNSLog 服务地址/token。所有配置一律从 `.env`（或容器环境变量）读取：
> - `DNSLOG_TYPE=internal`（默认）：私有化自建 DNSLog，需配置 `DNSLOG_DOMAIN` / `DNSLOG_TOKEN` / `DNSLOG_WEBSERVER`
> - `DNSLOG_TYPE=callback_red`：公共 callback.red DNSLog，仅需 `CALLBACK_RED_BASE_URL`
> - `DNSLOG_TYPE=dnslog_cn`：公共 dnslog.cn DNSLog，仅需 `DNSLOG_CN_BASE_URL`
> 三个 provider 的 `register` / `verifydns` 行为一致，底层实现由 `DNSLOG_TYPE` 自动切换。

**功能 1: 注册并获取子域名 (`register`)**
```bash
POST /execute/dnslog-service/register
{
  "params": {
    "length": 6
  }
}
```

可选参数：
- `length`：随机子域名前缀长度，默认 `5`
- `webserver`：DNSLog 服务地址（不传则走服务端配置）
- `token`：DNSLog 令牌（不传则走服务端配置）

**功能 2: 验证 DNS 记录 (`verifydns`)**
```bash
POST /execute/dnslog-service/verifydns
{
  "params": {
    "query": "abcde.<your-dnslog-domain>"
  }
}
```

> 示例中的 `query` 域名仅为占位：实际请使用 `register` 返回的 `subdomain`，主域名取自 `DNSLOG_DOMAIN` 配置。

可选参数：
- `query`：待验证的完整域名（必需）
- `webserver`：DNSLog 服务地址（不传则走服务端配置）
- `token`：DNSLog 令牌（不传则走服务端配置）

#### 📸 截图工具 (`screenshot`)

**功能 1: 网页截图 (`web_screenshot`)**
```bash
POST /execute/screenshot/web_screenshot
{
  "params": {
    "url": "https://example.com/api/profile",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <token>"
    },
    "body": {
      "id": 1001
    },
    "cookies": {
      "sessionid": "abc123"
    },
    "loading_strategy": "normal",
    "sleep_time": 2,
    "window_size": "1920,1080"
  }
}
```

说明：当只传 `url`（且 method=GET、无 headers/body/cookies）时走浏览器直接访问模式；否则走“先发请求再渲染响应”的复杂请求截图模式。

**功能 2: Burp 风格截图 (`burp_screenshot`)**
```bash
POST /execute/screenshot/burp_screenshot
{
  "params": {
    "request_data": "GET / HTTP/1.1\nHost: example.com\n\n",
    "response_data": "HTTP/1.1 200 OK\n...",
    "request_highlights": ["vulnerable_param"],
    "response_highlights": ["sensitive_data"]
  }
}
```

---

## 🤖 MCP (Model Context Protocol) 支持

本项目完整支持 MCP 协议，允许通过 MCP 客户端（如 Claude Desktop、Cline 等）直接调用所有工具。

### MCP 服务配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| **默认端口** | MCP 服务与主服务共用端口 | `8000` |
| **挂载路径** | MCP 服务挂载在主服务下 | `/mcp` |
| **传输协议** | Streamable HTTP | HTTP POST |
| **认证方式** | Bearer Token 或查询参数 | 与主服务一致 |

### MCP 端点

| 端点 | 说明 |
|------|------|
| `GET /mcp/` | MCP 服务状态（无需认证） |
| `POST /mcp/mcp/messages` | MCP Streamable HTTP 消息端点（需认证） |

### MCP 认证方式

MCP 端点支持两种认证方式：

#### 1. Header 认证 (推荐)
```
Authorization: Bearer <your-token>
```

#### 2. 查询参数认证
```
/mcp/mcp?token=<your-token>
```

**注意**：`/mcp/` 根路径（GET 请求）无需认证，可用于检查 MCP 服务状态。

### MCP 客户端配置示例

#### Claude Desktop 配置

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "vulnverify-tools": {
      "url": "http://localhost:8000/mcp/mcp",
      "headers": {
        "Authorization": "Bearer <your-token>"
      }
    }
  }
}
```

#### Cline / VS Code 扩展配置

```json
{
  "mcpServers": {
    "vulnverify-tools": {
      "transport": {
        "type": "streamableHttp",
        "url": "http://localhost:8000/mcp/mcp?token=<your-token>"
      }
    }
  }
}
```

### 可用 MCP 工具

所有工具会按 `{tool_name}_{action_name}` 注册为 MCP 工具（`-` 会自动转换为 `_`）：

| MCP 工具名称 | 描述 |
|--------------|------|
| `curl_exec_curl_args` | Curl 执行工具 - 执行 HTTP 请求 |
| `curl_exec_rawhttp` | Curl 执行工具 - 原始 HTTP 请求转换执行 |
| `dnslog_service_register` | DNSLog 服务 - 注册并获取随机子域名 |
| `dnslog_service_verifydns` | DNSLog 服务 - 验证 DNS 记录是否存在 |
| `screenshot_web_screenshot` | 截图工具 - 网页截图（支持复杂请求） |
| `screenshot_burp_screenshot` | 截图工具 - Burp 风格请求/响应截图 |

每个工具的详细参数说明会自动包含在 MCP 工具描述中（中文）。

### MCP 工具调用示例

通过 MCP 调用 DNSLog 注册会话：

```json
{
  "name": "dnslog_service_register",
  "arguments": {
    "length": 5
  }
}
```

通过 MCP 执行 Curl 命令：

```json
{
  "name": "curl_exec_curl_args",
  "arguments": {
    "curl_args": ["http://example.com", "-X", "GET"],
    "timeout": 10
  }
}
```

---

## 🛠️ 开发指南

### 添加新工具

1. 在 `tools/` 目录下创建新目录，例如 `tools/my_tool/`。
2. 创建 `main.py` 并继承 `BaseToolService`。
3. 使用 `@tool_action` 装饰器定义功能。

**示例代码 (`tools/my_tool/main.py`)**:

```python
from typing import Dict, Any
from core.base_tool_service import BaseToolService, tool_action

class MyTool(BaseToolService):
    def __init__(self):
        super().__init__("my-tool", "1.0.0")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        return True

    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Use action-based methods instead")

    @tool_action("greet", "Say hello")
    async def greet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "World")
        return {"message": f"Hello, {name}!"}
```

框架会自动发现并加载该工具，路由为 `/execute/my-tool/greet`。

### 为新工具添加 MCP 中文描述

在 `core/mcp_server.py` 的 `TOOL_DESCRIPTIONS` 字典中添加工具描述：

```python
TOOL_DESCRIPTIONS = {
    # ... 现有工具 ...
    "my-tool": {
        "name": "我的工具",
        "description": "工具的详细描述",
        "actions": {
            "greet": {
                "name": "打招呼",
                "description": "向指定用户打招呼",
                "params": {
                    "name": {
                        "type": "string",
                        "description": "用户名称（可选），默认为 'World'",
                        "required": False
                    }
                }
            }
        }
    }
}
```

---

## 📂 项目结构

```
.
├── core/                   # 核心框架代码
│   ├── auth.py             # 认证模块
│   ├── base_tool_service.py # 工具基类
│   ├── config.py           # 配置管理
│   ├── mcp_server.py       # MCP Server 集成
│   ├── image_hosting.py    # 图片存储（MinIO）
│   ├── logger.py           # 日志模块
│   └── tool_manager.py     # 工具加载和管理
├── tools/                  # 工具插件目录
│   ├── curl_exec/          # Curl 执行工具
│   ├── dnslog/             # DNSLog 工具
│   └── screenshot/         # 截图工具
├── tests/                  # 测试目录
│   └── test_mcp_integration.py  # MCP 集成测试
├── template/               # 工具开发模板
├── docs/                   # 详细文档
├── main.py                 # 服务入口
├── docker-compose.yml      # 容器编排配置
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量示例
└── README.md               # 项目说明
```

---

## 📋 依赖说明

### 核心依赖

- `fastapi`: Web 框架
- `uvicorn`: ASGI 服务器
- `pydantic-settings`: 配置管理

### MCP 依赖

- `mcp[sse]`: Model Context Protocol SDK (SSE 支持)
- `starlette`: ASGI 中间件支持

### 截图工具依赖

- `selenium`: 浏览器自动化
- `webdriver-manager`: ChromeDriver 管理

---

## 🔧 常见问题

### Q: MCP 连接失败，返回 401？

确保：
1. 配置了正确的 Token（`TOOL_TOKEN` 环境变量）
2. POST 请求头包含 `Authorization: Bearer <token>` 或使用查询参数 `?token=<token>`
3. `GET /mcp/` 根路径无需认证，可先访问确认服务正常

### Q: 工具未注册到 MCP？

检查：
1. 工具是否正确放置在 `tools/` 目录
2. 工具类是否继承 `BaseToolService`
3. 查看启动日志确认工具加载状态

### Q: 截图工具无法使用？

确保：
1. 安装了 Chrome/Chromium 浏览器
2. 配置了正确的 `CHROMEDRIVER_PATH` 和 `CHROMIUM_BINARY`
3. 参考 `docs/Mac本地开发环境配置.md` 进行配置
