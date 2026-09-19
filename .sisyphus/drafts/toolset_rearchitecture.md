# Draft: Toolset Rearhitecture

## Requirements (confirmed)
- Overall Goal: Re-design code architecture for a vulnerability verification toolset with dynamic tool loading, unified API, authentication, and deployment.
- Deployment: All tools run in Docker containers on port 8000.
- Dynamic Tool Loading: Tools loaded from `vulnverify_services/tools/` directory.
- API Endpoints:
  - GET /tools: Lists all loaded tools and their metadata.
  - POST /execute/{tool_name}: Executes a tool with parameters.
- Authentication: Bearer Token authentication for all endpoints except `/health`. Token from `TOOL_TOKEN` environment variable.
- Health Check: GET /health.
- Tool Loading Mechanism: Scan `vulnverify_services/tools/` for `_tool.py` files containing `BaseToolService` inherited classes.
- Tool Specification:
  - Tools must inherit `BaseToolService`.
  - `BaseToolService` attributes: `name`, `version`, `description`, `parameters`.
  - `BaseToolService` abstract methods: `validate_params(self, params: Dict[str, Any]) -> bool`, `execute(self, params: Dict[str, Any]) -> Dict[str, Any]`.
- Logging: Unified `logging` module, structured (JSON format), including tool name, request ID, execution time.
- Error Handling: Unified error response format (error code, message).
- Example Tool: `EchoTool` (receives `message`, returns `message`).
- Desired Directory Structure: Provided.

## Open Questions
- Parameter Definition Format: For the `parameters` attribute in `BaseToolService` (e.g., `/tools` API response and for validating `execute` requests), what format should `Dict[str, Any]` take to define tool parameters? (Options: Simple dict, JSON Schema, Pydantic models)
- Testing Strategy: Should unit tests and/or integration tests be included in this re-design for the core framework and the example `EchoTool`? If so, what testing framework should be used (e.g., `pytest`)?

## Scope Boundaries
- INCLUDE: All specified API endpoints, auth, logging, error handling, dynamic loading, tool spec, example tool, and directory structure. FastAPI for the web framework, Pydantic for settings, Python's `logging` for logging, `asyncio` for async operations. Docker for deployment.
- EXCLUDE: Specific vulnerability verification logic (only framework).
