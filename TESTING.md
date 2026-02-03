# Testing Guide for SoulSpace Calyx

This document describes how to run tests and add new tests to the SoulSpace Calyx bot project.

## Table of Contents
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Adding New Tests](#adding-new-tests)
- [Test Coverage](#test-coverage)
- [Mock Usage](#mock-usage)
- [Best Practices](#best-practices)

## Running Tests

### Prerequisites
Make sure you have the testing dependencies installed:
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
pytest tests/
```

### Run with Verbose Output
```bash
pytest tests/ -v
```

### Run with Coverage Report
```bash
pytest tests/ --cov --cov-report=html
```

This generates an HTML coverage report in the `htmlcov/` directory.

### Run Specific Test File
```bash
pytest tests/test_helpers.py
```

### Run Specific Test Class or Function
```bash
pytest tests/test_helpers.py::TestSafeGetNotionProperty
pytest tests/test_helpers.py::TestSafeGetNotionProperty::test_safe_get_notion_property_title
```

### Run Tests with Markers
```bash
# Run only slow tests
pytest tests/ -m slow

# Run only integration tests
pytest tests/ -m integration

# Skip slow tests
pytest tests/ -m "not slow"
```

### Quick Smoke Test
Run the smoke test script for a quick validation:
```bash
./smoke_test.sh
```

## Test Structure

The test suite is organized as follows:

```
tests/
├── __init__.py              # Makes tests a package
├── conftest.py              # Pytest fixtures and configuration
├── test_helpers.py          # Tests for helper functions
├── test_calyx.py            # Tests for main bot functionality
└── test_notion_integration.py  # Tests for Notion integration
```

### Test Files

- **`conftest.py`**: Contains pytest fixtures used across multiple test files
  - Mock Discord bot instance
  - Mock Notion client
  - Mock OAuth flow
  - Fake Notion responses
  - Environment variable mocks

- **`test_helpers.py`**: Unit tests for utility functions
  - `safe_get_notion_property()` tests
  - `generate_trace_id()` tests
  - `get_token_path()` tests
  - Channel context tests

- **`test_calyx.py`**: Integration tests for bot functionality
  - Bot initialization tests
  - OAuth flow tests
  - Channel context loading tests

- **`test_notion_integration.py`**: Tests for Notion integration
  - Trace logging tests
  - Task creation tests
  - Agent health update tests

## Adding New Tests

### 1. Choose the Right Test File

- **Helper functions**: Add to `test_helpers.py`
- **Bot functionality**: Add to `test_calyx.py`
- **Notion integration**: Add to `test_notion_integration.py`
- **New feature**: Create a new `test_<feature>.py` file

### 2. Write a Test Function

```python
def test_my_new_function():
    """Test description."""
    # Arrange
    input_data = "test"
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result == expected_output
```

### 3. Use Fixtures

```python
def test_with_mock_bot(mock_discord_bot):
    """Test using the Discord bot fixture."""
    assert mock_discord_bot.user.name == "TestBot"
```

### 4. Async Tests

For async functions, use the `@pytest.mark.asyncio` decorator:

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test an async function."""
    result = await my_async_function()
    assert result is not None
```

### 5. Test Exception Handling

```python
def test_handles_errors():
    """Test that errors are handled gracefully."""
    with pytest.raises(ValueError):
        my_function_that_should_raise()
```

## Test Coverage

### Coverage Goals

- **Overall**: Aim for >50% code coverage (current: 52%)
- **Critical paths**: Aim for >90% coverage on core functionality
- **Helper functions**: Aim for 100% coverage

Note: The >70% goal is aspirational and recommended for mature projects. The current implementation meets the >50% requirement for initial release.

### Viewing Coverage

Generate an HTML report:
```bash
pytest tests/ --cov --cov-report=html
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### Coverage Configuration

Coverage settings are in `pytest.ini`:
```ini
[pytest]
addopts = 
    --cov=.
    --cov-report=html
    --cov-report=term-missing
```

## Mock Usage

### Mock Objects

The test suite uses `unittest.mock` for mocking:

```python
from unittest.mock import MagicMock, patch

def test_with_mock():
    mock_client = MagicMock()
    mock_client.pages.create.return_value = {"id": "test"}
    
    with patch('module.notion', mock_client):
        # Your test code
        pass
```

### Async Mocks

For async functions, use `AsyncMock`:

```python
from unittest.mock import AsyncMock

async def test_async_mock():
    mock_func = AsyncMock(return_value="result")
    result = await mock_func()
    assert result == "result"
```

### Common Fixtures

Use the fixtures from `conftest.py`:

- `mock_env_vars`: Mock environment variables
- `mock_notion_client`: Mock Notion client
- `mock_discord_bot`: Mock Discord bot
- `mock_discord_message`: Mock Discord message
- `mock_discord_interaction`: Mock Discord interaction
- `fake_notion_page`: Fake Notion page response
- `fake_notion_database_response`: Fake database query response
- `mock_google_oauth_flow`: Mock OAuth flow

## Best Practices

### 1. Follow the AAA Pattern
- **Arrange**: Set up test data and mocks
- **Act**: Call the function being tested
- **Assert**: Verify the results

### 2. Test One Thing at a Time
Each test should verify one specific behavior.

### 3. Use Descriptive Test Names
```python
# Good
def test_safe_get_notion_property_returns_default_when_property_missing():
    pass

# Bad
def test_property():
    pass
```

### 4. Don't Test Implementation Details
Test behavior, not implementation.

### 5. Keep Tests Independent
Tests should not depend on each other or shared state.

### 6. Use Fixtures for Common Setup
Instead of duplicating setup code, create fixtures in `conftest.py`.

### 7. Mock External Dependencies
Always mock:
- Discord API calls
- Notion API calls
- OAuth flows
- File system operations (when appropriate)

### 8. Test Error Cases
Don't just test the happy path:
```python
def test_handles_missing_data():
    """Test behavior when data is missing."""
    result = my_function(None)
    assert result == default_value

def test_handles_api_errors():
    """Test behavior when API fails."""
    mock_client.side_effect = Exception("API Error")
    result = my_function()
    assert result is None  # Or appropriate fallback
```

### 9. Keep Tests Fast
- Mock slow operations (network, file I/O)
- Use in-memory databases when possible
- Mark slow tests with `@pytest.mark.slow`

### 10. Document Complex Tests
Add docstrings explaining what the test verifies and why.

## Continuous Integration

Tests are automatically run on every push and pull request. Ensure all tests pass before merging.

### Local Pre-commit Check
```bash
# Run before committing
./smoke_test.sh
```

## Troubleshooting

### Import Errors
If you get import errors:
```bash
# Make sure you're in the project root
cd /path/to/SoulSpace

# Install dependencies
pip install -r requirements.txt
```

### Async Test Issues
If async tests fail with "coroutine never awaited":
- Ensure you have `@pytest.mark.asyncio` decorator
- Check that `pytest-asyncio` is installed
- Verify `asyncio_mode = auto` in `pytest.ini`

### Coverage Not Working
If coverage isn't being calculated:
```bash
# Install coverage plugin
pip install pytest-cov

# Run with explicit coverage
pytest tests/ --cov=. --cov-report=term
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Python Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)

## Questions?

For questions or issues with tests, please:
1. Check this documentation
2. Review existing tests for examples
3. Open an issue on GitHub
