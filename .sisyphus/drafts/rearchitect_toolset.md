# Draft: Re-architect Vulnerability Verification Toolset

## Requirements (confirmed)
- Core Objective: Re-architect the project code for a vulnerability verification toolset.
- API Endpoints: `/tools` (GET), `/execute/{tool_name}` (POST), `/health` (GET).
- Authentication: Bearer Token authentication (from `TOOL_TOKEN` env var) for all except `/health`. `Authorization: Bearer <token>` format.
- Dynamic Tool Loading: Scan `vulnverify_services/tools/` at service startup to load `_tool.py` files.
- Tool File Naming: Files ending with `_tool.py`.
- Tool Class Inheritance: Tools must contain a class inheriting `BaseToolService`.
- `BaseToolService` Attributes: `name` (str), `version` (str), `description` (str), `parameters` (Dict[str, Any] using Pydantic models).
- `BaseToolService` Abstract Methods: `validate_params(self, params: Dict[str, Any]) -> bool`, `execute(self, params: Dict[str, Any]) -> Dict[str, Any]`.
- Pydantic Models: Use Pydantic models to define tool parameters for `BaseToolService.parameters` for robust validation.
- Logging: Unified `logging` (JSON structured), including `tool_name`, `request_id`, `duration_ms`.
- Error Handling: Unified error response format (`{"success": False, "error": {"code": ..., "message": ...}}`).
- Example Tool: Implement an `EchoTool` inheriting `BaseToolService`, accepting a `message` parameter (defined via Pydantic) and returning the message.
- Desired Directory Structure:
  ```
  vulnverify_tools/
  ├── vulnverify_services/
  │   ├── core/
  │   │   ├── __init__.py
  │   │   ├── base_tool_service.py   # BaseToolService 抽象类
  │   │   ├── config.py              # 配置管理，例如日志配置、Token 配置
  │   │   ├── auth.py                # 认证中间件
  │   │   └── logger.py              # 日志配置
  │   ├── tools/
  │   │   ├── __init__.py
  │   │   └── echo_tool.py           # Echo 工具实现
  │   ├── main.py                    # FastAPI 应用程序入口
  │   └── __init__.py
  ├── tests/                         # Pytest tests
  │   ├── __init__.py
  │   └── test_echo_tool.py
  ├── .env                           # 环境变量配置
  ├── docker-compose.yml             # Docker Compose 配置
  └── requirements.txt               # 项目依赖
  ```
- Testing: Include unit tests using `pytest` for the core framework and `EchoTool`.
- Python Version: 3.9+
- Core Dependencies: FastAPI, Uvicorn, Pydantic v2, aiohttp, requests.
- Dependency Management: `requirements.txt`.

## Technical Decisions
- FastAPI will be used for the API framework.
- Pydantic v2 will be used for data validation and settings management.

## Research Findings
- The `AGENTS.md` file provides context on existing structure and requirements for tool development.

## Open Questions
- None at this time.

## Scope Boundaries
- INCLUDE: All items listed under "Requirements (confirmed)".
- EXCLUDE: Any changes to `curl_exec` service or other parts of the repository not explicitly mentioned.
