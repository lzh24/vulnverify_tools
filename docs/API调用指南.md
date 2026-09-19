# API 调用指南

本文档提供漏洞验证工具服务的完整 API 调用示例和说明。

## 📋 目录

- [认证方式](#认证方式)
- [基础接口](#基础接口)
- [工具执行接口](#工具执行接口)
- [工具详细说明](#工具详细说明)
- [错误处理](#错误处理)
- [完整示例](#完整示例)

---

## 🔐 认证方式

所有非公开接口（除 `/` 和 `/health` 外）均需要 Bearer Token 认证。

### Token 配置

默认 Token: `unified-tools-token-12345`

可通过环境变量 `TOOL_TOKEN` 自定义：
```bash
# .env 文件
TOOL_TOKEN=your-custom-token-here
```

### 请求头格式

```http
Authorization: Bearer unified-tools-token-12345
```

### 认证失败示例

```bash
curl -X POST http://localhost:8000/execute/curl-exec/curl_args \
  -H "Content-Type: application/json" \
  -d '{"params": {"curl_args": ["http://example.com"]}}'
```

响应：
```json
{
  "detail": "Missing or invalid authorization header"
}
```

---

## 🌐 基础接口

### 1. 服务信息

```bash
GET /
```

**响应示例：**
```json
{
  "message": "Unified External Tools Service",
  "version": "1.0.0",
  "tools": {
    "curl-exec": "1.1.0",
    "dnslog-service": "1.2.1",
    "screenshot": "1.0.0"
  }
}
```

### 2. 整体健康检查

```bash
GET /health
```

**响应示例：**
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

### 3. 工具健康检查

```bash
GET /health/{tool_name}
```

**示例：**
```bash
curl http://localhost:8000/health/curl-exec
```

**响应示例：**
```json
{
  "status": "healthy",
  "tool_name": "curl-exec",
  "version": "1.1.0",
  "uptime_seconds": 3600,
  "actions": {
    "curl_args": "Execute curl command with provided arguments",
    "rawhttp": "Execute raw HTTP request by converting it to curl"
  }
}
```

### 4. 查询工具功能列表

```bash
GET /actions/{tool_name}
```

**示例：**
```bash
curl http://localhost:8000/actions/dnslog-service
```

**响应示例：**
```json
{
  "tool_name": "dnslog-service",
  "actions": {
    "register": "Register and get a random DNS subdomain",
    "verifydns": "Verify whether DNS record exists"
  }
}
```

---

## ⚙️ 工具执行接口

框架支持两种路由模式：

### 模式 1: 多层路由 (推荐)

格式：`POST /execute/{tool_name}/{action_name}`

**优点：**
- ✅ URL 直观，符合 RESTful 设计
- ✅ 无需在参数中指定 action
- ✅ 更易于理解和调试

### 模式 2: 基础路由 (兼容旧版)

格式：`POST /execute/{tool_name}`

需要在 `params` 中包含 `action` 字段。

**优点：**
- ✅ 向后兼容旧版调用方式
- ✅ 适用于单功能工具

---

## 🛠️ 工具详细说明

### 1. Curl 执行工具 (`curl-exec`)

#### 功能 1: 执行 Curl 命令 (`curl_args`)

**路由：**
```bash
POST /execute/curl-exec/curl_args
```

**请求参数：**
```json
{
  "params": {
    "curl_args": ["-L", "http://example.com"],
    "timeout": 10
  }
}
```

**参数说明：**
- `curl_args` (必需): curl 命令参数列表，第一个元素为 URL
- `timeout` (可选): 超时时间（秒），默认 15

**完整示例：**
```bash
curl -X POST http://localhost:8000/execute/curl-exec/curl_args \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "curl_args": ["-L", "https://httpbin.org/get"],
      "timeout": 10
    }
  }'
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "status_code": 200,
    "elapsed_ms": 1234,
    "raw_response": "HTTP/1.1 200 OK\n...",
    "error": null
  },
  "execution_time_ms": 1234,
  "timestamp": "2026-01-29T08:00:00Z",
  "action": "curl_args"
}
```

#### 功能 2: 发送原始 HTTP 请求 (`rawhttp`)

**路由：**
```bash
POST /execute/curl-exec/rawhttp
```

**请求参数：**
```json
{
  "params": {
    "url": "http://example.com",
    "raw_http": "GET / HTTP/1.1\nHost: example.com\n\n",
    "timeout": 15,
    "drop_headers": ["Content-Length"],
    "mask_headers": ["Authorization"]
  }
}
```

**参数说明：**
- `url` (必需): 目标 URL
- `raw_http` (必需): 原始 HTTP 请求文本
- `timeout` (可选): 超时时间（秒），默认 15
- `drop_headers` (可选): 要丢弃的 header 列表
- `mask_headers` (可选): 要脱敏的 header 列表

**完整示例：**
```bash
curl -X POST http://localhost:8000/execute/curl-exec/rawhttp \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "https://httpbin.org/post",
      "raw_http": "POST /post HTTP/1.1\nHost: httpbin.org\nContent-Type: application/json\n\n{\"key\":\"value\"}",
      "timeout": 10
    }
  }'
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "status_code": 200,
    "elapsed_ms": 567,
    "raw_response": "HTTP/1.1 200 OK\n...",
    "error": null,
    "converted_from_rawhttp": true,
    "original_url": "https://httpbin.org/post"
  },
  "execution_time_ms": 567,
  "timestamp": "2026-01-29T08:00:00Z",
  "action": "rawhttp"
}
```

---

### 2. DNSLog 工具 (`dnslog-service`)

> **Provider 配置（全部走 env，代码无硬编码）**
> - `DNSLOG_TYPE=internal`（默认）：私有化自建 DNSLog，配置 `DNSLOG_DOMAIN` / `DNSLOG_TOKEN` / `DNSLOG_WEBSERVER`
> - `DNSLOG_TYPE=callback_red`：公共 callback.red DNSLog，仅配置 `CALLBACK_RED_BASE_URL`
> - `DNSLOG_TYPE=dnslog_cn`：公共 dnslog.cn DNSLog，仅配置 `DNSLOG_CN_BASE_URL`
> 下文示例中的 `your-domain.com` 仅为示意，实际返回的 `domain`/`subdomain` 由上述 env 决定。

#### 功能 1: 注册并获取随机子域名 (`register`)

**路由：**
```bash
POST /execute/dnslog-service/register
```

**请求参数：**
```json
{
  "params": {
    "length": 6
  }
}
```

**参数说明：**
- `length` (可选): 随机子域名前缀长度，默认 `5`
- `webserver` (可选): DNSLog 服务地址，不传时使用服务端配置
- `token` (可选): DNSLog 鉴权 token，不传时使用服务端配置

**完整示例：**
```bash
curl -X POST http://localhost:8000/execute/dnslog-service/register \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "length": 6
    }
  }'
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "status": "registered",
    "domain": "<your-dnslog-domain>",
    "subdomain": "abcde.<your-dnslog-domain>"
  },
  "execution_time_ms": 12,
  "timestamp": "2026-01-29T08:00:00Z",
  "action": "register"
}
```

#### 功能 2: 验证 DNS 记录 (`verifydns`)

**路由：**
```bash
POST /execute/dnslog-service/verifydns
```

**请求参数：**
```json
{
  "params": {
    "query": "abcde.<your-dnslog-domain>"
  }
}
```

**参数说明：**
- `query` (必需): 待验证的完整域名
- `webserver` (可选): DNSLog 服务地址，不传时使用服务端配置
- `token` (可选): DNSLog 鉴权 token，不传时使用服务端配置

**完整示例：**
```bash
curl -X POST http://localhost:8000/execute/dnslog-service/verifydns \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "query": "abcde.<your-dnslog-domain>"
    }
  }'
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "status": "verified",
    "query": "abcde.<your-dnslog-domain>",
    "exists": true,
    "data": {
      "records": []
    }
  },
  "execution_time_ms": 8,
  "timestamp": "2026-01-29T08:00:00Z",
  "action": "verifydns"
}
```

---

### 3. 截图工具 (`screenshot`)

#### 功能 1: 无头浏览器网页截图 (`web_screenshot`)

**路由：**
```bash
POST /execute/screenshot/web_screenshot
```

**请求参数：**
```json
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
    "window_size": "1920,1080",
    "include_screenshot_base64": false
  }
}
```

**参数说明：**
- `url` (必需): 目标网页 URL
- `method` (可选): HTTP 方法，默认 `GET`，支持 `GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS`
- `headers` (可选): 请求头对象
- `body` (可选): 请求体，支持 `string/object/array`
- `cookies` (可选): Cookie 对象
- `loading_strategy` (可选): 页面加载策略，可选值: `none`, `eager`, `normal`（默认: `none`）
- `sleep_time` (可选): 页面加载后的等待时间（秒），默认 0
- `user_agent` (可选): 自定义用户代理字符串
- `window_size` (可选): 浏览器窗口大小，格式 "宽,高"（默认: "1920,1080"）
- `include_screenshot_base64` (可选): 是否在响应中返回 `screenshot` Base64 字段，默认跟随环境变量 `SCREENSHOT_RETURN_BASE64_BY_DEFAULT`，当前默认 `false`
 
 说明：当仅传 `url`（且 `method=GET` 且未传 `headers/body/cookies`）时，走浏览器直接访问模式；否则走复杂请求渲染截图模式。
**完整示例：**
```bash
curl -X POST http://localhost:8000/execute/screenshot/web_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "https://example.com/api/profile",
      "method": "POST",
      "headers": {
        "Content-Type": "application/json"
      },
      "body": {
        "id": 1001
      },
      "sleep_time": 2
    }
  }'
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "image_url": "screenshots/<uuid>.png",
    "message": "Screenshot captured successfully",
    "request_mode": "complex"
  },
  "execution_time_ms": 3245,
  "timestamp": "2026-01-29T09:00:00Z",
  "action": "web_screenshot"
}
```

#### 功能 2: Burp 风格 HTTP 截图 (`burp_screenshot`)

**路由：**
```bash
POST /execute/screenshot/burp_screenshot
```

**请求参数：**
```json
{
  "params": {
    "request_data": "GET / HTTP/1.1\\nHost: example.com\\n\\n",
    "response_data": "HTTP/1.1 200 OK\\n\\nHello World",
    "request_highlights": ["GET", "example.com"],
    "response_highlights": ["200 OK"],
    "include_screenshot_base64": false
  }
}
```

**参数说明：**
- `request_data` (必需): HTTP 请求数据
- `response_data` (必需): HTTP 响应数据
- `request_highlights` (可选): 请求中需要高亮的字符串列表
- `response_highlights` (可选): 响应中需要高亮的字符串列表
- `width` (可选): 截图宽度（默认: 1920）
- `height` (可选): 截图高度（默认: 1080）
- `elapsed_ms` (可选): 请求耗时（毫秒）
- `is_retest` (可选): 是否为重新测试（默认: false）
- `original_status` (可选): 原始状态字符串
- `include_screenshot_base64` (可选): 是否在响应中返回 `screenshot` Base64 字段，默认跟随环境变量 `SCREENSHOT_RETURN_BASE64_BY_DEFAULT`，当前默认 `false`

**完整示例：**
```bash
curl -X POST http://localhost:8000/execute/screenshot/burp_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "request_data": "GET /api/users HTTP/1.1\\nHost: example.com\\n\\n",
      "response_data": "HTTP/1.1 200 OK\\nContent-Type: application/json\\n\\n[]",
      "request_highlights": ["GET"],
      "elapsed_ms": 123,
      "include_screenshot_base64": false
    }
  }'
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "filename": "vuln_screenshot_20260129_090000_123456.png",
    "file_size": 45678,
    "message": "Burp-style screenshot created successfully"
  },
  "execution_time_ms": 1234,
  "timestamp": "2026-01-29T09:00:00Z",
  "action": "burp_screenshot"
}
```

---

### 4. 终端执行工具 (`terminal_hub`)

终端执行工具提供 CLI 命令执行、输出采集、终端截图与图床上传的一站式能力，适用于漏洞验证环节中需要执行任意命令行工具并取证留痕的场景。

#### 功能 1: 一站式执行 CLI 并返回完整结果 (`run_cli`)

**路由：**
```bash
POST /execute/terminal_hub/run_cli
```

**请求参数：**
```json
{
  "params": {
    "tool": "nmap",
    "args": ["-p", "8002", "127.0.0.1"],
    "timeout": 60
  }
}
```

**交互式命令示例 (如 telnet)：**
```json
{
  "params": {
    "tool": "telnet",
    "args": ["127.0.0.1", "6379"],
    "inputs": [
      "info",
      "quit"
    ],
    "timeout": 10
  }
}
```

**参数说明：**
- `tool` (必需): CLI 工具名称，如 `nmap`、`curl`、`ping`、`telnet`
- `args` (可选): CLI 参数列表，默认 `[]`
- `timeout` (可选): 超时秒数，默认 `60`
- `inputs` (可选): 交互式输入序列（字符串数组）。对于需要交互的命令，可以在连接后按顺序发送这些字符串，每个字符串会自动加上换行符。如果输入为 `"quit"`，则会发送 Ctrl+C 信号中断执行。
- `include_screenshot_base64` (可选): 是否在响应中返回 `screenshot_base64` 字段，默认跟随环境变量 `TERMINAL_HUB_RETURN_BASE64_BY_DEFAULT`，当前默认 `false`

**完整示例：**
```bash
curl -X POST http://localhost:8000/execute/terminal_hub/run_cli \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "tool": "nmap",
      "args": ["-p", "8002", "127.0.0.1"],
      "timeout": 60
    }
  }'
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "command": "nmap -p 8002 127.0.0.1",
    "stdout": "Starting Nmap 7.94...\nPORT     STATE  SERVICE\n8002/tcp open   unknown\nNmap done: 1 IP address scanned",
    "stderr": "",
    "return_code": 0,
    "status": "finished",
    "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "image_url": "screenshots/<uuid>.png"
  },
  "execution_time_ms": 2341,
  "timestamp": "2026-04-27T10:00:00Z",
  "action": "run_cli"
}
```

**返回字段说明：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `command` | string | 完整命令字符串 |
| `stdout` | string | 标准输出 |
| `stderr` | string | 标准错误 |
| `return_code` | int | 进程退出码 |
| `status` | string | finished / failed |
| `screenshot_base64` | string/null | 终端截图 Base64（纯黑底终端样式，关闭时为 `null`） |
| `image_url` | string | 图床上传后的 URL |

#### 功能 2: 创建异步会话 (`create_session`)

**路由：**
```bash
POST /execute/terminal_hub/create_session
```

**请求参数：**
```json
{
  "params": {
    "token": "unified-tools-token-12345",
    "cmd": "nmap",
    "args": ["-p", "8002", "127.0.0.1"],
    "auto_screenshot": true
  }
}
```

**参数说明：**
- `token` (必需): 鉴权 token，需与 `TOOL_TOKEN` 或 `TERMINAL_HUB_TOKEN` 一致
- `cmd` (必需): CLI 工具名称
- `args` (可选): CLI 参数列表，默认 `[]`
- `auto_screenshot` (可选): 执行完成后是否自动截图，默认 `true`
- `include_screenshot_base64` (可选): 是否在会话结果中保留 `screenshot_base64` 字段，默认跟随环境变量 `TERMINAL_HUB_RETURN_BASE64_BY_DEFAULT`，当前默认 `false`

**成功响应：**
```json
{
  "success": true,
  "data": {
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "running",
    "view_url": "/terminal-hub/ui?session_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  },
  "execution_time_ms": 5,
  "timestamp": "2026-04-27T10:00:00Z",
  "action": "create_session"
}
```

#### 功能 3: 查询会话详情 (`get_session`)

**路由：**
```bash
POST /execute/terminal_hub/get_session
```

**请求参数：**
```json
{
  "params": {
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "include_screenshot_base64": false
  }
}
```

`include_screenshot_base64` 不传时，默认跟随环境变量 `TERMINAL_HUB_RETURN_BASE64_BY_DEFAULT`，当前默认 `false`。

**成功响应：**
```json
{
  "success": true,
  "data": {
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "command": ["nmap", "-p", "8002", "127.0.0.1"],
    "status": "finished",
    "return_code": 0,
    "stdout": "Starting Nmap 7.94...",
    "stderr": "",
    "created_at": "2026-04-27T10:00:00",
    "finished_at": "2026-04-27T10:00:02",
    "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "screenshot_path": "artifacts/terminal/a1b2c3d4-e5f6-7890-abcd-ef1234567890/terminal.png",
    "image_url": "screenshots/<uuid>.png"
  },
  "execution_time_ms": 12,
  "timestamp": "2026-04-27T10:00:00Z",
  "action": "get_session"
}
```

#### 功能 4: 列出所有会话 (`list_sessions`)

**路由：**
```bash
POST /execute/terminal_hub/list_sessions
```

**请求参数：**
```json
{
  "params": {}
}
```

**成功响应：**
```json
{
  "success": true,
  "data": {
    "count": 2,
    "items": [
      {
        "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": "finished",
        "command": ["nmap", "-p", "8002", "127.0.0.1"],
        "created_at": "2026-04-27T10:00:00"
      }
    ]
  },
  "execution_time_ms": 3,
  "timestamp": "2026-04-27T10:00:00Z",
  "action": "list_sessions"
}
```

#### WebUI 访问

终端执行工具提供 WebUI 页面，支持通过 URL 参数直接触发命令执行并实时回显输出。

**访问地址：**
```
http://localhost:8000/terminal-hub/ui
```

**URL 参数说明：**
| 参数 | 必填 | 说明 |
|------|------|------|
| `token` | 是 | 鉴权 token |
| `cmd` | 创建时必填 | CLI 工具名称 |
| `args` | 否 | JSON 数组字符串，如 `["-p","8002","127.0.0.1"]` |
| `session_id` | 否 | 已有会话 ID，传入时直接查询该会话 |
| `autorun` | 否 | 设为 `1` 时自动创建并执行 |

**示例：直接执行 nmap 扫描**
```
http://localhost:8000/terminal-hub/ui?token=unified-tools-token-12345&cmd=nmap&args=%5B%22-p%22%2C%228002%22%2C%22127.0.0.1%22%5D
```

**示例：回放已有会话**
```
http://localhost:8000/terminal-hub/ui?token=unified-tools-token-12345&session_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

#### 截图样式说明

终端截图采用纯黑底终端样式（无 session 元信息），模拟真实终端界面：
- 背景色：`#000000`（纯黑）
- 前景色：`#d1ffd1`（浅绿）
- Prompt：`$ nmap -p 8002 127.0.0.1`（绿色）
- stdout：浅绿色
- stderr：红色 `#ff6b6b`

---

## ❌ 错误处理

### 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述信息"
  },
  "execution_time_ms": 10,
  "timestamp": "2026-01-29T08:00:00Z"
}
```

### 常见错误码

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| `AUTHENTICATION_FAILED` | 认证失败 | 401 |
| `INVALID_TOKEN` | Token 无效 | 403 |
| `TOOL_NOT_FOUND` | 工具不存在 | 404 |
| `INVALID_PARAMETERS` | 参数无效 | 400 |
| `ACTION_EXECUTION_ERROR` | 动作执行失败 | 500 |
| `SERVICE_NOT_INITIALIZED` | 服务未初始化 | 503 |

### 错误示例

**1. 认证失败**
```bash
curl -X POST http://localhost:8000/execute/curl-exec/curl_args \
  -H "Content-Type: application/json" \
  -d '{"params": {"curl_args": ["http://example.com"]}}'
```

响应：
```json
{
  "detail": "Missing or invalid authorization header"
}
```

**2. 工具不存在**
```bash
curl -X POST http://localhost:8000/execute/non-existent-tool/action \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"params": {}}'
```

响应：
```json
{
  "detail": "Tool not found: non-existent-tool"
}
```

**3. 参数无效**
```bash
curl -X POST http://localhost:8000/execute/curl-exec/curl_args \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"params": {}}'
```

响应：
```json
{
  "success": false,
  "error": {
    "code": "ACTION_EXECUTION_ERROR",
    "message": "curl_args parameter is required and must be a list"
  },
  "execution_time_ms": 1,
  "timestamp": "2026-01-29T08:00:00Z"
}
```

---

## 📝 完整示例

### 示例 1: 完整的 DNSLog 使用流程

```bash
# 1. 注册并获取随机子域名
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/execute/dnslog-service/register \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"params": {"length": 6}}')

SUBDOMAIN=$(echo "$REGISTER_RESPONSE" | jq -r '.data.subdomain')

echo "Subdomain: $SUBDOMAIN"

# 2. 在漏洞验证点使用 $SUBDOMAIN 后，调用 verifydns 查询是否有回连
curl -X POST http://localhost:8000/execute/dnslog-service/verifydns \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d "{\"params\": {\"query\": \"$SUBDOMAIN\"}}"
```

### 示例 2: 使用原始 HTTP 请求测试漏洞

```bash
# 测试 SQL 注入漏洞
curl -X POST http://localhost:8000/execute/curl-exec/rawhttp \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "http://target.com",
      "raw_http": "GET /search?q=1'\'' OR 1=1-- HTTP/1.1\nHost: target.com\n\n",
      "timeout": 10
    }
  }'
```

### 示例 3: 批量执行 Curl 请求

```bash
#!/bin/bash

TARGETS=(
  "http://example1.com"
  "http://example2.com"
  "http://example3.com"
)

for target in "${TARGETS[@]}"; do
  echo "Testing: $target"
  curl -X POST http://localhost:8000/execute/curl-exec/curl_args \
    -H "Authorization: Bearer unified-tools-token-12345" \
    -H "Content-Type: application/json" \
    -d "{\"params\": {\"curl_args\": [\"$target\"], \"timeout\": 5}}"
  echo "---"
done
```

---

## 🔍 调试技巧

### 1. 查看服务日志

```bash
docker-compose logs -f
```

### 2. 查看特定工具日志

```bash
docker-compose logs | grep "curl-exec"
```

### 3. 使用 jq 格式化 JSON 响应

```bash
curl -s http://localhost:8000/health | jq .
```

### 4. 测试认证

```bash
curl -v http://localhost:8000/execute/curl-exec/curl_args \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"params": {"curl_args": ["http://example.com"]}}'
```

---

## 📚 相关文档

- [项目 README](../README.md)
- [开发指南](./开发指南.md)
- [架构设计](./架构设计.md)

---

### 5. DNSLog Provider 实跑冒烟（真实服务验证）

仓库提供真实服务冒烟脚本 `scripts/dnslog_smoke.py`，对三种 provider 依次实跑
`register → 触发一次 DNS 解析 → verifydns 断言 exists=true`，单节失败不中断其它类型。

```bash
# 只跑某一种
DNSLOG_DOMAIN=your-domain DNSLOG_TOKEN=your-token DNSLOG_WEBSERVER=host:port \
  python scripts/dnslog_smoke.py --type internal

DNSLOG_CN_BASE_URL=http://www.dnslog.cn \
  python scripts/dnslog_smoke.py --type dnslog_cn

python scripts/dnslog_smoke.py --type callback_red   # 用 CALLBACK_RED_BASE_URL(默认 https://callback.red)
```

**关于 internal 的 DNS 解析**：`DNSLOG_WEBSERVER` 的主机 IP 同时就是 DNS 服务器（UDP/53）。
脚本会直接用该 IP 发原始 DNS 报文查询子域名（绕过系统 resolver 的缓存/私有域判定），
因此**不需要**系统 DNS 能解析到你的私有域名——只要 `verifyToken` 可达即可完成验证。

**callback.red 说明**：该公共服务的 DNS 会话极短（域名存活约 1 天，且 `key` 一旦查询即失效
返回 `{"code":403,"data":["Domain Expired"]}`），不适合作为稳定回归用例；因此
`callback_red` 在冒烟中可能因上游会话过期而失败，这**不是**代码问题。生产建议优先用
`internal`（自建）或 `dnslog_cn`（公共、会话较长）做外带验证。
