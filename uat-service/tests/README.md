# UAT Automation Service - Test Suite

This directory contains the comprehensive test suite for the UAT automation service, including unit tests, integration tests, and end-to-end tests.

## Test Structure

```
tests/
├── unit/                      # Unit tests (fast, isolated)
│   └── test_groq_client.py   # Groq API client tests
├── integration/               # Integration tests (multiple components)
│   └── test_complete_flow.py # Complete flow integration tests
├── e2e/                       # End-to-end tests (full system)
│   └── test_sample_app.py    # Tests against sample application
├── conftest.py               # Shared fixtures and configuration
└── README.md                 # This file
```

## Test Categories

### Unit Tests
- **Purpose**: Test individual components in isolation
- **Speed**: Fast (< 1 second per test)
- **Dependencies**: Minimal, uses mocks
- **Marker**: `@pytest.mark.unit`
- **Run**: `pytest -m unit`

### Integration Tests
- **Purpose**: Test interaction between multiple components
- **Speed**: Medium (1-10 seconds per test)
- **Dependencies**: May require Redis, database
- **Marker**: `@pytest.mark.integration`
- **Run**: `pytest -m integration`

### End-to-End Tests
- **Purpose**: Test complete system against sample application
- **Speed**: Slow (10-60 seconds per test)
- **Dependencies**: Requires sample app running, Groq API (optional)
- **Marker**: `@pytest.mark.e2e`
- **Run**: `pytest -m e2e`

### Smoke Tests
- **Purpose**: Quick validation of critical functionality
- **Speed**: Fast to medium
- **Dependencies**: Minimal
- **Marker**: `@pytest.mark.smoke`
- **Run**: `pytest -m smoke`

## Running Tests

### Prerequisites

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio pytest-cov pytest-html pytest-xdist
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start sample application** (for e2e tests):
   ```bash
   cd ../sample-app
   npm install
   npm run dev
   ```

### Quick Start

```bash
# Run all tests
pytest

# Run specific test category
pytest -m unit
pytest -m integration
pytest -m e2e
pytest -m smoke

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run in parallel (faster)
pytest -n auto

# Run specific test file
pytest tests/integration/test_complete_flow.py

# Run specific test
pytest tests/integration/test_complete_flow.py::TestCompleteFlow::test_story_parsing_with_llm_success
```

### Using Test Runner Script

```bash
# Run unit tests
python run_tests.py unit

# Run integration tests
python run_tests.py integration

# Run e2e tests (requires sample app)
python run_tests.py e2e

# Run smoke tests
python run_tests.py smoke

# Run all tests with coverage
python run_tests.py all --coverage

# Run tests in parallel
python run_tests.py all --parallel

# Generate HTML report
python run_tests.py all --html
```

## Test Markers

Tests are marked with pytest markers for easy filtering:

- `unit` - Unit tests
- `integration` - Integration tests
- `e2e` - End-to-end tests
- `smoke` - Smoke tests
- `slow` - Tests that take longer to run
- `requires_groq` - Tests that require Groq API access
- `requires_sample_app` - Tests that require sample app running

### Running Tests by Marker

```bash
# Run only fast tests (exclude slow)
pytest -m "not slow"

# Run tests that don't require Groq API
pytest -m "not requires_groq"

# Run integration tests that don't require sample app
pytest -m "integration and not requires_sample_app"

# Run smoke tests or unit tests
pytest -m "smoke or unit"
```

## Test Coverage

### Generating Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
xdg-open htmlcov/index.html  # Linux

# Generate terminal coverage report
pytest --cov=app --cov-report=term-missing

# Generate XML coverage report (for CI/CD)
pytest --cov=app --cov-report=xml
```

### Coverage Goals

- **Overall**: 80%+ code coverage
- **Core Services**: 90%+ coverage
- **API Endpoints**: 85%+ coverage
- **Models**: 95%+ coverage

## Integration Tests (Task 14.1)

### Test Complete Flow

**File**: `tests/integration/test_complete_flow.py`

Tests the complete UAT automation flow:
1. Story submission
2. Story parsing (LLM with fallback)
3. Test scenario generation
4. Test execution
5. Report generation

**Key Tests**:
- `test_story_parsing_with_llm_success` - Verify LLM parsing works
- `test_story_parsing_with_fallback_to_nlp` - Verify fallback to NLP
- `test_scenario_generation_from_criteria` - Verify scenario generation
- `test_parallel_execution_with_retry_logic` - Verify parallel execution
- `test_report_generation_with_traceability` - Verify report generation
- `test_complete_flow_end_to_end` - Full integration test

**Run**:
```bash
pytest tests/integration/test_complete_flow.py -v
```

### Test Fallback Mechanisms

Tests LLM → NLP fallback chain:
- Rate limit handling
- API error handling
- Graceful degradation

**Run**:
```bash
pytest tests/integration/test_complete_flow.py::TestFallbackMechanisms -v
```

### Test Retry Logic

Tests retry logic and flaky test detection:
- Smart retry on failure
- Flaky test flagging
- Retry count tracking

**Run**:
```bash
pytest tests/integration/test_complete_flow.py::TestRetryLogic -v
```

## End-to-End Tests (Task 14.2)

### Test Sample Application

**File**: `tests/e2e/test_sample_app.py`

Tests the complete system against the sample application using all 15+ sample user stories.

**Key Tests**:
- `test_all_sample_stories` - Run all sample stories (main e2e test)
- `test_login_module_stories` - Test Login module stories
- `test_user_management_module_stories` - Test User Management stories
- `test_element_finding_strategies` - Verify element finding works
- `test_report_traceability` - Verify report traceability

**Prerequisites**:
1. Sample app must be running at `http://localhost:5173`
2. Sample stories fixture must exist at `fixtures/sample-stories.json`

**Run**:
```bash
# Start sample app first
cd ../sample-app
npm run dev

# In another terminal, run e2e tests
cd ../uat-service
pytest tests/e2e/test_sample_app.py -v

# Or run specific test
pytest tests/e2e/test_sample_app.py::TestSampleApplicationE2E::test_all_sample_stories -v
```

### Smoke Tests

Quick validation tests:
- `test_sample_app_accessible` - Verify sample app is running
- `test_single_story_end_to_end` - Quick smoke test with one story

**Run**:
```bash
pytest -m smoke
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run unit tests
      run: pytest -m unit --cov=app --cov-report=xml
    
    - name: Run integration tests
      run: pytest -m "integration and not requires_groq"
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        file: ./coverage.xml
```

## Troubleshooting

### Common Issues

**Issue**: Tests fail with "Sample app not accessible"
- **Solution**: Start the sample app: `cd ../sample-app && npm run dev`

**Issue**: Tests fail with "Groq API key not configured"
- **Solution**: Set `GROQ_API_KEY` in `.env` file or skip tests: `pytest -m "not requires_groq"`

**Issue**: Async tests fail on Windows
- **Solution**: Tests automatically configure Windows event loop policy

**Issue**: Tests are slow
- **Solution**: Run in parallel: `pytest -n auto` or run only fast tests: `pytest -m "not slow"`

**Issue**: Import errors
- **Solution**: Ensure you're in the `uat-service` directory and dependencies are installed

### Debug Mode

Run tests with debug output:
```bash
# Verbose output with logging
pytest -vv --log-cli-level=DEBUG

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb
```

## Writing New Tests

### Test Template

```python
import pytest
from app.models.story import StoryInput

@pytest.mark.asyncio
@pytest.mark.unit
async def test_my_feature():
    """Test description."""
    # Arrange
    story_input = StoryInput(text="As a user...", source="manual")
    
    # Act
    result = await my_function(story_input)
    
    # Assert
    assert result is not None
    assert result.status == "success"
```

### Best Practices

1. **Use descriptive test names**: `test_story_parsing_with_invalid_input`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Use fixtures**: Reuse common setup code
4. **Mock external dependencies**: Don't call real APIs in unit tests
5. **Test edge cases**: Not just happy path
6. **Keep tests independent**: Each test should run in isolation
7. **Use appropriate markers**: Mark tests with correct categories

## Test Metrics

After running tests, check these metrics:

- **Pass Rate**: Should be 100% for committed code
- **Coverage**: Should be 80%+ overall
- **Speed**: Unit tests < 1s, integration < 10s, e2e < 60s
- **Flakiness**: No flaky tests in CI/CD

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Pytest Markers](https://docs.pytest.org/en/stable/example/markers.html)
- [Coverage.py](https://coverage.readthedocs.io/)
