# Issues Encountered

## Test Framework Setup (2026-01-29)

### Dependency Conflicts
- **Issue**: Version conflict between httpx requirements
- **Details**: 
  - requirements-test.txt initially specified `httpx==0.25.2`
  - Other packages require `httpx>=0.28.1`
- **Resolution**: Updated to `httpx>=0.28.1` in requirements-test.txt

### LSP Errors in Existing Code
- **Issue**: Multiple LSP errors detected in existing codebase
- **Details**:
  - Missing arguments in main.py and test_instantiation.py
  - Import resolution issues in tools/dnslog/main.py and tools/curl_exec/main.py
- **Impact**: These are pre-existing issues not related to test framework setup
- **Action**: Documented for awareness but not addressed as part of this task