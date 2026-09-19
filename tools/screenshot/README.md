# Screenshot Tool - 截图工具

本工具提供两种截图功能，用于漏洞验证和报告生成：
1. **无头浏览器网页截图** - 捕获网页的完整截图
2. **Burp风格HTTP截图** - 生成类似BurpSuite的HTTP请求/响应截图

## 📋 功能说明

### 功能 1: 无头浏览器网页截图 (web_screenshot)

使用Selenium无头浏览器捕获网页截图，支持自定义加载策略、等待时间和窗口大小。

**主要特性：**
- 支持多种页面加载策略（none, eager, normal）
- 支持复杂请求参数（method/headers/body/cookies）
- 可配置页面加载后的等待时间
- 自定义用户代理字符串
- 可调整浏览器窗口大小
- 可选返回Base64编码的截图数据

### 功能 2: Burp风格HTTP截图 (burp_screenshot)

生成类似BurpSuite风格的HTTP请求/响应截图，用于漏洞验证报告。

**主要特性：**
- 语法高亮显示（HTTP方法、Header、Cookie等）
- 支持自定义高亮文本
- 显示请求/响应行数和耗时
- 支持重新测试标记
- 可选返回Base64编码的截图数据

## 🚀 快速开始

### 1. 集成到统一服务（推荐）

本工具已集成到统一服务框架中，无需额外配置。

重启统一服务，工具将自动加载：

```bash
docker-compose up -d --build
```

### 2. 独立部署（可选）

如果需要独立部署此工具：

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置 TOOL_TOKEN

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行服务
python main.py
```

## 📡 API 调用示例

### 认证

所有请求需要携带 Bearer Token：

```bash
Authorization: Bearer your-secret-token-here
```

### 功能 1: 网页截图

**路由:** `POST /execute/screenshot/web_screenshot`

**请求参数：**
- `url` (string, 必需): 目标网页URL
- `method` (string, 可选): HTTP 请求方法（默认: GET，支持 GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS）
- `headers` (object, 可选): 自定义请求头
- `body` (string/object/array, 可选): 请求体
- `cookies` (object, 可选): 请求 Cookie
- `loading_strategy` (string, 可选): 页面加载策略，可选值: none, eager, normal（默认: none）
- `sleep_time` (integer, 可选): 页面加载后的等待时间（秒）（默认: 0）
- `user_agent` (string, 可选): 自定义用户代理字符串
- `window_size` (string, 可选): 浏览器窗口大小，格式: "宽,高"（默认: "1920,1080"）
- `include_screenshot_base64` (boolean, 可选): 是否在响应中返回 `screenshot` Base64 字段（默认跟随环境变量 `SCREENSHOT_RETURN_BASE64_BY_DEFAULT`，当前默认 `false`）

> 兼容性说明：如果仅传 `url`（以及原有可选参数），仍沿用原来的 GET 浏览器导航截图逻辑。

**示例请求：**

```bash
curl -X POST http://localhost:8000/execute/screenshot/web_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "https://example.com",
      "loading_strategy": "none",
      "sleep_time": 2,
      "window_size": "1920,1080",
      "include_screenshot_base64": false
    }
  }'
```

**复杂请求示例（POST + headers + body + cookies）：**

```bash
curl -X POST http://localhost:8000/execute/screenshot/web_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "https://httpbin.org/post",
      "method": "POST",
      "headers": {
        "Content-Type": "application/json",
        "X-Test": "vulnverify"
      },
      "body": {
        "probe": "screenshot",
        "level": "complex"
      },
      "cookies": {
        "session": "abc123"
      },
      "loading_strategy": "normal",
      "sleep_time": 1
    }
  }'
```

**响应示例：**

```json
{
  "success": true,
  "data": {
    "image_url": "https://image-host.example/screenshot.png",
    "message": "Screenshot captured successfully",
    "request_mode": "navigate"
  },
  "execution_time_ms": 3245,
  "timestamp": "2026-01-29T09:00:00Z",
  "action": "web_screenshot"
}
```

**保存截图到文件：**

```bash
# 使用 jq 提取并保存截图
curl -X POST http://localhost:8000/execute/screenshot/web_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "https://example.com"
    }
  }' | jq -r '.data.screenshot' | base64 -d > screenshot.png
```

### 功能 2: Burp风格HTTP截图

**路由:** `POST /execute/screenshot/burp_screenshot`

**请求参数：**
- `request_data` (string, 必需): HTTP请求数据
- `response_data` (string, 必需): HTTP响应数据
- `request_highlights` (array, 可选): 请求中需要高亮的字符串列表
- `response_highlights` (array, 可选): 响应中需要高亮的字符串列表
- `width` (integer, 可选): 截图宽度（默认: 1920）
- `height` (integer, 可选): 截图高度（默认: 1080）
- `elapsed_ms` (integer, 可选): 请求耗时（毫秒）
- `is_retest` (boolean, 可选): 是否为重新测试（默认: false）
- `original_status` (string, 可选): 原始状态
- `include_screenshot_base64` (boolean, 可选): 是否在响应中返回 `screenshot` Base64 字段（默认跟随环境变量 `SCREENSHOT_RETURN_BASE64_BY_DEFAULT`，当前默认 `false`）

**示例请求：**

```bash
curl -X POST http://localhost:8000/execute/screenshot/burp_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "request_data": "GET /api/users HTTP/1.1\nHost: example.com\nUser-Agent: Mozilla/5.0\n\n",
      "response_data": "HTTP/1.1 200 OK\nContent-Type: application/json\n\n{\"users\": []}",
      "request_highlights": ["GET", "api/users"],
      "response_highlights": ["200 OK"],
      "elapsed_ms": 123,
      "width": 1920,
      "height": 1080,
      "include_screenshot_base64": false
    }
  }'
```

**响应示例：**

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

**保存截图到文件：**

```bash
# 使用 jq 提取并保存截图
curl -X POST http://localhost:8000/execute/screenshot/burp_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "request_data": "GET / HTTP/1.1\nHost: example.com\n\n",
      "response_data": "HTTP/1.1 200 OK\n\nHello World"
    }
  }' | jq -r '.data.screenshot' | base64 -d > burp_screenshot.png
```

## 🛠️ 开发指南

### 核心概念

1. **继承 BaseToolService**
   - 所有工具必须继承 [`BaseToolService`](../../core/base_tool_service.py:35)
   - 在 `__init__` 中指定工具名称和版本

2. **使用 @tool_action 装饰器**
   - 使用 [`@tool_action`](../../core/base_tool_service.py:10) 装饰器注册功能
   - 每个功能对应一个独立的路由
   - 装饰器参数：`action_name` 和 `description`

3. **异步执行**
   - Selenium操作是同步的，使用 `run_in_executor` 在线程池中执行
   - 避免阻塞事件循环

4. **返回格式**
   - action 方法返回 `Dict[str, Any]`
   - 框架会自动包装为标准响应格式

### 技术实现

#### 无头浏览器截图

使用Selenium WebDriver控制Chrome浏览器：

```python
# 配置Chrome选项
options = Options()
options.headless = True
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# 初始化WebDriver
driver = webdriver.Chrome(service=service, options=options)

# 访问URL并截图
driver.get(url)
screenshot = driver.get_screenshot_as_base64()
```

#### Burp风格截图

1. 生成HTML内容，包含请求/响应数据
2. 使用CSS样式实现BurpSuite风格
3. 使用Selenium渲染HTML并截图

```python
# 生成HTML
html_content = self.renderer._generate_html(
    request_html,
    response_html,
    request_lines,
    response_lines,
    elapsed_ms,
    is_retest,
    original_status
)

# 渲染并截图
driver.get(f'file://{html_path}')
driver.save_screenshot(screenshot_path)
```

### 日志记录

工具自动初始化日志记录器，使用方式：

```python
self.logger.info("Capturing screenshot for URL: {url}")
self.logger.warning("Page load timeout or error: {str(e)}")
self.logger.error("Screenshot capture failed: {str(e)}", exc_info=True)
```

日志采用 JSON 格式，便于集中管理和分析。

### 错误处理

框架提供统一的错误处理机制：

- **参数错误**: 抛出 `ValueError`，返回 400 错误
- **执行异常**: 自动捕获，返回 500 错误
- **认证失败**: 返回 401/403 错误

## 📁 文件结构

```
tools/screenshot/
├── .env.example        # 环境变量配置示例
├── Dockerfile          # Docker 镜像构建文件
├── main.py             # 工具服务实现
├── requirements.txt    # Python 依赖
└── README.md          # 本文档
```

## 🔍 健康检查

查看工具健康状态：

```bash
curl http://localhost:8000/health/screenshot
```

响应：

```json
{
  "status": "healthy",
  "tool_name": "screenshot",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "actions": {
    "web_screenshot": "Capture screenshot of a webpage using headless browser",
    "burp_screenshot": "Create Burp-style screenshot of HTTP request/response"
  }
}
```

## 📚 相关文档

- [项目 README](../../README.md)
- [API 调用指南](../../docs/API调用指南.md)
- [开发指南 (AGENTS.md)](../../AGENTS.md)
- [核心框架代码](../../core/)

## 💡 使用场景

### 1. 漏洞验证报告

在漏洞验证过程中，捕获目标网页的截图作为证据：

```bash
# 捕获存在XSS漏洞的页面
curl -X POST http://localhost:8000/execute/screenshot/web_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "url": "https://target.com/page?param=<script>alert(1)</script>",
      "sleep_time": 2
    }
  }'
```

### 2. HTTP请求/响应记录

记录漏洞利用的HTTP请求和响应：

```bash
# 生成Burp风格的截图
curl -X POST http://localhost:8000/execute/screenshot/burp_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "request_data": "POST /api/login HTTP/1.1\nHost: target.com\nContent-Type: application/json\n\n{\"username\":\"admin\",\"password\":\"admin\"}",
      "response_data": "HTTP/1.1 200 OK\nContent-Type: application/json\n\n{\"token\":\"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...\"}",
      "request_highlights": ["admin", "password"],
      "response_highlights": ["token"],
      "elapsed_ms": 234
    }
  }'
```

### 3. 重新测试标记

标记漏洞重新测试的截图：

```bash
curl -X POST http://localhost:8000/execute/screenshot/burp_screenshot \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "request_data": "GET /api/vuln HTTP/1.1\nHost: target.com\n\n",
      "response_data": "HTTP/1.1 403 Forbidden\n\nAccess denied",
      "is_retest": true,
      "original_status": "200 OK"
    }
  }'
```

## ⚠️ 注意事项

1. **性能考虑**
   - 截图操作相对耗时，建议设置合理的超时时间
   - 对于大量截图任务，考虑使用队列和异步处理

2. **资源管理**
   - WebDriver实例在使用后会自动关闭
   - 临时HTML文件会自动清理

3. **浏览器依赖**
   - 需要安装Chromium和ChromeDriver
   - Docker镜像已包含所需依赖

4. **安全性**
   - 确保URL参数经过验证，避免SSRF攻击
   - 不要在日志中记录敏感信息

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目使用与主项目相同的许可证。
