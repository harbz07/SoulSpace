# Testing

This page explains how to run the test suite and how to write new tests.

---

## Running Tests

### Prerequisites

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest tests/
```

### Verbose Output

```bash
pytest tests/ -v
```

### Run with Coverage Report

```bash
pytest tests/ --cov --cov-report=html
```

HTML report is generated in `htmlcov/`. Open `htmlcov/index.html` to view it.

### Run a Specific File

```bash
pytest tests/test_helpers.py
```

### Run a Specific Class or Function

```bash
pytest tests/test_helpers.py::TestSafeGetNotionProperty
pytest tests/test_helpers.py::TestSafeGetNotionProperty::test_safe_get_notion_property_title
```

### Run Tests by Marker

```bash
pytest tests/ -m slow          # Only slow tests
pytest tests/ -m integration   # Only integration tests
pytest tests/ -m "not slow"    # Skip slow tests
```

### Quick Smoke Test

```bash
./smoke_test.sh
```

---

## Test Structure

```
tests/
├── __init__.py                   # Package marker
├── conftest.py                   # Shared fixtures
├── test_calyx.py                 # Bot initialisation and OAuth flow
├── test_helpers.py               # Utility function unit tests
├── test_notion_integration.py    # Notion write helper tests
└── test_notion_validator.py      # Schema validation tests
```

### conftest.py — Shared Fixtures

| Fixture | Description |
|---------|-------------|
| `mock_env_vars` | Mock environment variables |
| `mock_notion_client` | Mock Notion API client |
| `mock_discord_bot` | Mock Discord bot instance |
| `mock_discord_message` | Mock Discord message |
| `mock_discord_interaction` | Mock Discord interaction |
| `fake_notion_page` | Fake Notion page response |
| `fake_notion_database_response` | Fake database query response |
| `mock_google_oauth_flow` | Mock Google OAuth flow |

---

## Writing New Tests

### Choose the Right File

| What you're testing | Test file |
|--------------------|-----------|
| Helper / utility functions | `test_helpers.py` |
| Bot slash commands or events | `test_calyx.py` |
| Notion write operations | `test_notion_integration.py` |
| Database schema validation | `test_notion_validator.py` |
| New standalone feature | Create `test_<feature>.py` |

### Test Structure (AAA Pattern)

```python
def test_my_function():
    """Describe what this test verifies."""
    # Arrange
    input_data = "test"

    # Act
    result = my_function(input_data)

    # Assert
    assert result == expected_output
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result is not None
```

> `asyncio_mode = auto` is set in `pytest.ini` so `@pytest.mark.asyncio` is optional for most tests.

### Exception Handling

```python
def test_raises_on_invalid_input():
    with pytest.raises(ValueError):
        my_function_that_should_raise(None)
```

### Mocking External Dependencies

```python
from unittest.mock import MagicMock, patch

def test_with_mocked_notion():
    mock_client = MagicMock()
    mock_client.pages.create.return_value = {"id": "test"}

    with patch("calyx_notion_integration.notion", mock_client):
        # test code
        pass
```

### Async Mocks

```python
from unittest.mock import AsyncMock

async def test_async_mock():
    mock_func = AsyncMock(return_value="result")
    result = await mock_func()
    assert result == "result"
```

---

## Coverage Goals

| Scope | Target |
|-------|--------|
| Overall | >50% |
| Core functionality | >90% |
| Helper functions | 100% |

---

## Best Practices

1. **One assertion per test** — each test verifies a single behaviour.
2. **Descriptive names** — `test_safe_get_notion_property_returns_default_when_missing` not `test_property`.
3. **Independent tests** — tests must not depend on execution order or shared mutable state.
4. **Mock all external I/O** — Discord API, Notion API, OAuth, filesystem (where appropriate).
5. **Test error paths** — always include tests for missing data and API failures.
6. **Use fixtures** — extract common setup into `conftest.py` fixtures.
7. **Mark slow tests** — add `@pytest.mark.slow` so they can be skipped during rapid iteration.

---

## Troubleshooting Tests

### Import Errors

```bash
# Ensure you are in the project root with the virtual environment active
cd /path/to/SoulSpace
source venv/bin/activate
pip install -r requirements.txt
```

### Async Test Failures (`coroutine never awaited`)

- Add `@pytest.mark.asyncio` to the test function.
- Verify `pytest-asyncio` is installed.
- Check that `asyncio_mode = auto` is present in `pytest.ini`.

### Coverage Not Calculating

```bash
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term
```

---

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Python Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
