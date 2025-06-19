# Code Coverage Guide for GOES_VFI

## Overview

GOES_VFI uses comprehensive code coverage analysis to ensure code quality and identify untested code paths. Our coverage setup includes multiple reporting formats, CI/CD integration, and visualization tools.

## Coverage Goals

- **Minimum Coverage**: 80% (enforced in CI/CD)
- **Target Coverage**: 85%+ for core modules
- **Branch Coverage**: Enabled for all tests

## Quick Start

### Running Coverage Locally

```bash
# Basic coverage run
python run_coverage.py

# Run with specific tests
python run_coverage.py tests/unit/

# Run with markers
python run_coverage.py -m "not slow"

# Run in parallel for faster execution
python run_coverage.py --parallel

# Clean and run fresh
python run_coverage.py --clean

# Generate HTML report and open in browser
python run_coverage.py --html --open
```

### Coverage Reports

#### Terminal Report
```bash
# Quick coverage summary in terminal
coverage report
```

#### HTML Report
```bash
# Generate interactive HTML report
coverage html
# Open htmlcov/index.html in browser
```

#### XML Report (for CI/CD)
```bash
# Generate XML report for tools like Codecov
coverage xml
```

#### JSON Report (for analysis)
```bash
# Generate JSON report with detailed metrics
coverage json --pretty-print
```

## Configuration

### `.coveragerc` File

Our coverage configuration (`.coveragerc`) includes:

- **Source specification**: Only measure `goesvfi` package
- **Branch coverage**: Enabled by default
- **Exclusions**: Test files, migrations, `__init__.py`
- **Report settings**: 80% minimum, show missing lines
- **Context tracking**: For parallel test execution

### Key Exclusions

The following patterns are excluded from coverage:

```ini
exclude_lines =
    pragma: no cover
    def __repr__
    def __str__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

## CI/CD Integration

### GitHub Actions

Coverage is automatically measured in CI/CD:

1. **Main CI Pipeline** (`ci.yml`):
   - Runs tests with coverage
   - Uploads to Codecov
   - Generates artifacts

2. **Coverage Workflow** (`coverage.yml`):
   - Dedicated coverage analysis
   - Multiple report formats
   - PR comments with coverage delta
   - Integration with Codecov and Coveralls

### Coverage Services

#### Codecov
- Automatic PR comments
- Coverage trends
- Flag-based reporting
- Badge generation

```yaml
# In your README.md
[![codecov](https://codecov.io/gh/username/GOES_VFI/branch/main/graph/badge.svg)](https://codecov.io/gh/username/GOES_VFI)
```

#### Coveralls
- Alternative coverage tracking
- Historical trends
- Branch coverage visualization

```yaml
# In your README.md
[![Coverage Status](https://coveralls.io/repos/github/username/GOES_VFI/badge.svg?branch=main)](https://coveralls.io/github/username/GOES_VFI?branch=main)
```

## Improving Coverage

### Finding Uncovered Code

1. **HTML Report**:
   ```bash
   python run_coverage.py --html --open
   ```
   - Red highlights show uncovered lines
   - Click files to see line-by-line coverage

2. **Terminal Report**:
   ```bash
   coverage report --show-missing
   ```
   - Shows line numbers of missing coverage

3. **JSON Analysis**:
   ```python
   import json

   with open('coverage.json') as f:
       data = json.load(f)

   # Find files with low coverage
   for file, info in data['files'].items():
       if info['summary']['percent_covered'] < 80:
           print(f"{file}: {info['summary']['percent_covered']:.1f}%")
   ```

### Writing Effective Tests

#### Unit Test Example
```python
import pytest
from goesvfi.utils.config import get_output_dir

def test_get_output_dir_default():
    """Test default output directory."""
    output_dir = get_output_dir()
    assert output_dir.exists()
    assert output_dir.name == "output"

def test_get_output_dir_custom(tmp_path):
    """Test custom output directory."""
    custom_dir = tmp_path / "custom_output"
    output_dir = get_output_dir(str(custom_dir))
    assert output_dir == custom_dir
```

#### Testing Error Paths
```python
def test_error_handling():
    """Test error handling paths for coverage."""
    with pytest.raises(ValueError):
        process_invalid_data(None)

    # Test defensive programming
    result = safe_process("")
    assert result is None
```

#### Testing Branch Coverage
```python
def test_conditional_logic():
    """Test all branches of conditional logic."""
    # Test true branch
    result = conditional_function(True, "value")
    assert result == "processed"

    # Test false branch
    result = conditional_function(False, "value")
    assert result == "skipped"

    # Test edge cases
    result = conditional_function(True, None)
    assert result == "default"
```

## Coverage Best Practices

### 1. Regular Monitoring
- Check coverage before committing
- Review coverage trends in CI/CD
- Address coverage drops immediately

### 2. Meaningful Coverage
- Don't just aim for 100%
- Focus on critical paths
- Test edge cases and error handling

### 3. Exclude Appropriately
```python
# Mark code that shouldn't be covered
if TYPE_CHECKING:  # pragma: no cover
    from typing import Protocol

def debug_only():  # pragma: no cover
    """This function is only for debugging."""
    pass
```

### 4. Test Organization
```python
# Group related tests
class TestImageProcessor:
    """Test image processing functionality."""

    def test_load_image(self):
        """Test image loading."""
        pass

    def test_process_image(self):
        """Test image processing."""
        pass

    def test_error_handling(self):
        """Test error cases."""
        pass
```

## Troubleshooting

### Common Issues

#### 1. Import Errors in Coverage
```bash
# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python run_coverage.py
```

#### 2. Missing Coverage Data
```bash
# Combine parallel coverage data
coverage combine
coverage report
```

#### 3. GUI Test Coverage
```bash
# Use xvfb for headless GUI testing
xvfb-run -a python run_coverage.py tests/gui/
```

#### 4. Async Test Coverage
```python
# Ensure proper async test setup
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

### Performance Tips

1. **Parallel Execution**:
   ```bash
   python run_coverage.py --parallel
   ```

2. **Selective Testing**:
   ```bash
   # Only run changed modules
   python run_coverage.py tests/unit/test_changed_module.py
   ```

3. **Coverage Contexts**:
   ```bash
   # Separate coverage by test type
   CONTEXT=unit coverage run -m pytest tests/unit/
   CONTEXT=integration coverage run -m pytest tests/integration/
   coverage combine
   ```

## Advanced Usage

### Custom Coverage Plugins

Create custom coverage plugins for special cases:

```python
# coverage_plugin.py
import coverage

class CustomCoveragePlugin(coverage.CoveragePlugin):
    """Custom plugin for special coverage cases."""

    def file_tracer(self, filename):
        if filename.endswith('.jinja2'):
            return CustomFileTracer(filename)
        return None
```

### Integration with IDEs

#### VS Code
```json
// .vscode/settings.json
{
    "python.testing.pytestArgs": [
        "--cov=goesvfi",
        "--cov-report=xml",
        "--cov-report=term"
    ],
    "coverage-gutters.xmlname": "coverage.xml"
}
```

#### PyCharm
- Run Configuration → Add `--cov=goesvfi` to parameters
- Use Coverage tool window for visualization

## Maintenance

### Regular Tasks

1. **Weekly**: Review coverage trends
2. **Per PR**: Check coverage changes
3. **Monthly**: Analyze uncovered code
4. **Quarterly**: Update coverage goals

### Coverage Reports Archive

Store historical coverage data:

```bash
# Archive coverage reports
mkdir -p coverage-archive/$(date +%Y-%m-%d)
cp coverage.* coverage-archive/$(date +%Y-%m-%d)/
cp -r htmlcov coverage-archive/$(date +%Y-%m-%d)/
```

## Resources

- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Codecov Documentation](https://docs.codecov.com/)
- [Coveralls Documentation](https://docs.coveralls.io/)

---

Remember: Code coverage is a tool, not a goal. Focus on writing meaningful tests that verify behavior, and coverage will follow naturally.
