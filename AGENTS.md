# AGENTS.md - 漏洞验证工具开发指南 (中文版)

## 1. 项目概览

本项目是一个统一的漏洞验证外部工具框架 (VulnVerify Tools)。
- **服务类型**: 基于 FastAPI + Uvicorn 的 ASGI 服务
- **运行模式**: Docker 容器化部署 (默认端口 8000)
- **核心组件**: 从 `core/` 目录加载，工具插件从 `tools/` 目录动态加载
- **统一功能**: 提供 REST API 和 MCP (Model Context Protocol) 两种接口

## 2. 构建与测试命令

### 🚀 启动服务
```bash
# 推荐方式: 使用 Docker Compose 一键启动
docker-compose up -d --build

# 本地开发模式 (需 Python 3.9+)
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 🧪 运行测试
项目配置了 `pytest` (详见 `pytest.ini`)，请使用以下命令：

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/test_config.py

# 运行特定测试用例
pytest tests/unit/test_config.py::test_load_config -v

# 运行集成测试
pytest -m integration

# 运行指定标记的测试
pytest -m unit
```

### 🧹 代码检查
- 无强制性的 CI 检查，但请严格遵循 PEP 8 规范
- 建议对所有函数进行类型注解

## 3. 代码风格指南

### Python 规范
- **版本**: Python 3.9+
- **导入顺序**:
  1. 标准库 (`import os`, `from typing import ...`)
  2. 第三方库 (`from fastapi import ...`)
  3. 本地模块 (`from core.base_tool_service import ...`)
- **命名**:
  - 类名: `PascalCase` (如 `BaseToolService`)
  - 函数/变量: `snake_case` (如 `validate_params`)
  - 常量: `UPPER_CASE`

### 类型注解 (Typing)
**强制**对所有函数参数和返回值进行类型注解。

```python
# ✅ 正确
async def process_data(self, data: Dict[str, Any]) -> List[str]:
    ...

# ❌ 错误
def process_data(self, data):
    ...
```

### 异步编程 (Async/Await)
所有 I/O 操作必须是异步的。
- 使用 `async def` 定义函数
- 使用 `aiohttp` 或 `httpx` 代替 `requests` (除非在独立线程中)
- 使用 `await` 调用异步函数

### 错误处理
- 显式抛出异常 (如 `ValueError`)，框架会自动捕获并返回 400/500 错误。
- 使用 `self.logger.error("msg", exc_info=True)` 记录异常堆栈。

## 4. 架构与开发模式

### 📂 目录结构
```
/opt/datas/Code/work-mss/vulnverify_tools/
├── core/                   # 核心框架 (勿动)
│   ├── base_tool_service.py # 基类定义
│   └── ...
├── tools/                  # 工具插件目录 (在此开发)
│   ├── my_tool/            # 新工具目录
│   │   ├── main.py         # 入口文件
│   │   ├── Dockerfile      # 独立构建文件
│   │   └── requirements.txt
├── template/               # 模板代码
└── tests/                  # 测试代码
```

### 🛠️ 开发新工具 (New Tool Pattern)

1. **创建目录**: 在 `tools/` 下创建新目录。
2. **继承基类**: 继承 `BaseToolService`。
3. **使用装饰器**: 使用 `@tool_action` 定义功能 (不要重写 `_execute`)。

**示例模版**:
```python
from typing import Dict, Any
from core.base_tool_service import BaseToolService, tool_action

class MyTool(BaseToolService):
    def __init__(self):
        super().__init__("my-tool", "1.0.0")

    # 必须实现，但对新模式通常返回 True 即可
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        return True

    # 必须实现，但抛出异常以强制使用 action 模式
    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Use action-based methods")

    @tool_action("my_action", "Action description")
    async def run_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # 业务逻辑
        return {"status": "success"}
```

### 🤖 MCP 支持
所有使用 `@tool_action` 装饰的方法会自动注册为 MCP (Model Context Protocol) 工具，无需额外配置。

## 5. 常见陷阱

1. 未经审查，不要修改核心框架。
2. 不要硬编码秘密信息。
3. 不要在异步上下文中使用同步I/O。
4. 始终验证参数。
5. 不要忘记日志记录。
6. 使用日志记录而非 `print()`。

## 6. Docker 部署

- 所有工具在单个 Docker 容器 (`8000` 端口) 中运行。
- `docker-compose.yml` 用于编排。
- 健康检查配置在 `/health` 端点。
- 环境变量通过 `.env` 文件或 `docker-compose` 配置。