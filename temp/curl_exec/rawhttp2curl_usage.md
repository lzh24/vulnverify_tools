# RawHttpToCurl 使用说明

## 功能介绍

`RawHttpToCurl` 类可以将原始 HTTP 请求包转换为可执行的 curl 命令，支持两种输出格式：

1. 传统的完整 curl 命令字符串
2. 符合 curl_exec.py 服务入参格式的参数列表

## 主要方法

### 1. `to_curl(pretty: bool = True) -> str`

生成传统的完整 curl 命令字符串。

参数：
- `pretty`: 是否美化输出（添加换行和缩进）

### 2. `to_curl_args() -> List[str]`

生成符合 curl_exec.py 服务入参格式的参数列表。

返回：
- `List[str]`: 不包含 "curl" 命令本身的参数列表

## 使用示例

### 基本用法

```python
from backend.utils.rawhttp2curl import RawHttpToCurl

# 原始 HTTP 请求包
raw_http = """POST /api/login HTTP/1.1
Host: example.com
Content-Type: application/json
Authorization: Bearer token123

{"username": "admin", "password": "password"}
"""

# 目标 URL
url = "https://example.com/api/login"

# 创建转换器实例
converter = RawHttpToCurl(url=url, raw_http=raw_http)

# 生成传统 curl 命令
curl_command = converter.to_curl()
print(curl_command)

# 生成 curl_exec.py 入参格式
curl_args = converter.to_curl_args()
print(curl_args)
```

### 发送到 curl_exec 服务

```python
import requests
import json

# 生成 curl_exec.py 入参格式
curl_args = converter.to_curl_args()

# 构造请求数据
request_data = {
    "curl_args": curl_args,
    "timeout": 30
}

# 发送到 curl_exec 服务
response = requests.post(
    "http://curl-exec-service:8000/execute-curl",
    headers={"X-Auth-Token": "your-auth-token"},
    json=request_data
)

# 处理响应
if response.status_code == 200:
    result = response.json()
    print(f"状态码: {result['status_code']}")
    print(f"响应内容: {result['raw_response']}")
    print(f"耗时: {result['elapsed_ms']}ms")
else:
    print(f"请求失败: {response.status_code} - {response.text}")
```

### 高级用法

```python
# 丢弃某些头部（如 Content-Length）
converter = RawHttpToCurl(
    url=url,
    raw_http=raw_http,
    drop_headers=["content-length", "connection"]
)

# 脱敏某些敏感头部
converter = RawHttpToCurl(
    url=url,
    raw_http=raw_http,
    mask_headers=["authorization", "cookie"]
)
```

## 输出示例

### 传统 curl 命令格式

```bash
curl 'https://example.com/api/login' \
  -X POST \
  -H 'Host: example.com' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer token123' \
  --data '{"username": "admin", "password": "password"}'
```

### curl_exec.py 入参格式

```python
{
  "curl_args": ["https://example.com",
    "-X", "POST",
    "-H", "Host: example.com",
    "-H", "Content-Type: application/json",
    "-H", "Authorization: Bearer token123",
    "--data", "{\"usernam\": \"admin\", \"password\": \"password\"}"],
  "timeout": 15
}
```

## 注意事项

1. `to_curl_args()` 方法返回的参数列表不包含 "curl" 命令本身，这正好符合 curl_exec.py 服务的要求。
2. curl_exec.py 服务会自动添加一些通用参数，如 `-i`, `--raw`, `--compressed` 等。
3. 如果需要自定义 User-Agent，可以在原始 HTTP 请求中包含 `User-Agent` 头部。
4. 对于敏感信息，建议使用 `mask_headers` 参数进行脱敏处理。