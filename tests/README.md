# Tests

This directory will contain proper test suites for the MindGraph application.

## Structure

The test directory is currently set up with:
- `conftest.py` - Pytest configuration and fixtures
- `pytest.ini` - Pytest settings (in project root)
- Empty subdirectories for organizing tests by category:
  - `agents/` - Agent tests
  - `integration/` - Integration tests
  - `performance/` - Performance tests
  - `services/` - Service unit tests

## Adding Tests

When adding tests, follow these conventions:
- Test files should start with `test_` prefix
- Test classes should start with `Test` prefix
- Test functions should start with `test_` prefix
- Use pytest fixtures from `conftest.py` for common setup

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/path/to/test_file.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/path/to/test_file.py::test_function_name
```

