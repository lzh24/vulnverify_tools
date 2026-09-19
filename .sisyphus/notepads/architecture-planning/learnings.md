# Learnings

## Test Framework Setup (2026-01-29)

### Configuration
- **Framework**: pytest
- **Async Support**: pytest-asyncio (mode=auto)
- **Coverage**: pytest-cov
- **HTTP Client**: httpx (for integration tests)

### Directory Structure
```
tests/
  ├── unit/          # Unit tests for individual components
  ├── integration/   # Integration tests for API endpoints
  └── conftest.py    # Shared fixtures and configuration
```

### Key Configuration (pytest.ini)
- `pythonpath = .`: Ensures project root is in python path
- `asyncio_mode = auto`: Simplifies async test markers
- `addopts = ... --cov=.`: Default coverage reporting

## Config Module Testing (2026-01-29)

### Pydantic Settings Behavior
- Pydantic Settings automatically loads from environment variables matching field names (case-sensitive)
- When `env_file = ".env"` is specified, it also loads from a .env file in the current working directory
- Environment variables take precedence over .env file values
- Required fields without defaults will raise a ValidationError if not provided

### Testing Strategies
- Use `unittest.mock.patch.dict` to temporarily modify environment variables for testing
- Use `tmp_path` pytest fixture to create temporary directories for testing .env file loading
- Change working directory with `os.chdir(tmp_path)` to isolate .env file loading tests
- Always restore original working directory using try/finally blocks
- Test both positive cases (values loaded correctly) and negative cases (missing required values)
- Test precedence: environment variables should override .env file values

### Error Handling
- Pydantic v2 raises `pydantic_core._pydantic_core.ValidationError` instead of `ValueError`
- Error messages contain "Field required" for missing required fields
- Use `pytest.raises(Exception)` and check error message string for validation

### Coverage Achievement
- **core/config.py**: 100% coverage with 6 test cases
- Tests cover: required field validation, env var loading, defaults, override behavior, .env file loading, precedence rules
