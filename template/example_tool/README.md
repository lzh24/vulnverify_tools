# Example Tool - 示例工具模板

本工具是一个完整的示例模板，演示如何基于漏洞验证工具框架创建新的工具服务。

## 📋 功能说明

本示例工具提供三个文本处理功能：

1. **uppercase** - 将文本转换为大写
2. **lowercase** - 将文本转换为小写
3. **reverse** - 反转文本

## 🚀 快速开始

### 1. 集成到统一服务（推荐）

将本工具复制到 `tools/` 目录：

```bash
# 从项目根目录执行
cp -r template/example_tool tools/my_tool
cd tools/my_tool
```

修改 [`main.py`](main.py:16) 中的工具名称和版本：

```python
super().__init__("my-tool", "1.0.0")
```

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

### 功能 1: 转换为大写

**路由:** `POST /execute/example-tool/uppercase`

```bash
curl -X POST http://localhost:8000/execute/example-tool/uppercase \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "text": "hello world"
    }
  }'
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "processed_text": "HELLO WORLD",
    "length": 11,
    "message": "Successfully converted 11 characters to uppercase"
  },
  "execution_time_ms": 2,
  "timestamp": "2026-01-29T08:00:00Z",
  "action": "uppercase"
}
```

### 功能 2: 转换为小写

**路由:** `POST /execute/example-tool/lowercase`

```bash
curl -X POST http://localhost:8000/execute/example-tool/lowercase \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "text": "HELLO WORLD"
    }
  }'
```

### 功能 3: 反转文本

**路由:** `POST /execute/example-tool/reverse`

```bash
curl -X POST http://localhost:8000/execute/example-tool/reverse \
  -H "Authorization: Bearer unified-tools-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "text": "hello"
    }
  }'
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "processed_text": "olleh",
    "length": 5,
    "message": "Successfully reversed 5 characters"
  },
  "execution_time_ms": 1,
  "timestamp": "2026-01-29T08:00:00Z",
  "action": "reverse"
}
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

3. **参数验证**
   - 在每个 action 方法中进行参数验证
   - 使用 `raise ValueError()` 抛出参数错误
   - 框架会自动捕获并返回标准错误响应

4. **返回格式**
   - action 方法返回 `Dict[str, Any]`
   - 框架会自动包装为标准响应格式

### 添加新功能

在 [`main.py`](main.py) 中添加新的 action 方法：

```python
@tool_action("count_words", "Count words in text")
async def count_words(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """统计文本中的单词数"""
    text = params.get("text")
    if not text:
        raise ValueError("text parameter is required")
    
    word_count = len(text.split())
    
    return {
        "word_count": word_count,
        "character_count": len(text),
        "message": f"Found {word_count} words"
    }
```

新功能会自动注册到路由 `/execute/example-tool/count_words`。

### 日志记录

工具自动初始化日志记录器，使用方式：

```python
self.logger.info("Processing request")
self.logger.warning("Parameter validation warning")
self.logger.error("Execution failed", exc_info=True)
```

日志采用 JSON 格式，便于集中管理和分析。

### 错误处理

框架提供统一的错误处理机制：

- **参数错误**: 抛出 `ValueError`，返回 400 错误
- **执行异常**: 自动捕获，返回 500 错误
- **认证失败**: 返回 401/403 错误

## 📁 文件结构

```
template/example_tool/
├── .env.example        # 环境变量配置示例
├── Dockerfile          # Docker 镜像构建文件
├── main.py             # 工具服务实现
├── requirements.txt    # Python 依赖
└── README.md          # 本文档
```

## 🔍 健康检查

查看工具健康状态：

```bash
curl http://localhost:8000/health/example-tool
```

响应：

```json
{
  "status": "healthy",
  "tool_name": "example-tool",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "actions": {
    "uppercase": "Convert text to uppercase",
    "lowercase": "Convert text to lowercase",
    "reverse": "Reverse the text"
  }
}
```

## 📚 相关文档

- [项目 README](../../README.md)
- [API 调用指南](../../docs/API调用指南.md)
- [开发指南 (AGENTS.md)](../../AGENTS.md)
- [核心框架代码](../../core/)

## 💡 最佳实践

1. **命名规范**
   - 工具名使用小写加连字符（如 `my-tool`）
   - Action 名使用下划线（如 `convert_text`）

2. **参数验证**
   - 始终验证必需参数
   - 提供清晰的错误消息
   - 使用类型检查确保数据正确

3. **日志记录**
   - 记录关键操作和决策点
   - 包含必要的上下文信息
   - 错误时使用 `exc_info=True` 记录堆栈

4. **文档注释**
   - 为每个 action 编写清晰的文档字符串
   - 说明参数要求和返回值格式
   - 提供使用示例

5. **性能考虑**
   - 使用异步操作处理 I/O
   - 避免阻塞操作
   - 对耗时操作添加超时控制

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目使用与主项目相同的许可证。