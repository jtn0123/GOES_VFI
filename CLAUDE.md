# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Development Partnership

We're building production-quality code together. Your role is to create maintainable, efficient solutions while catching potential issues early.

When you seem stuck or overly complex, I'll redirect you - my guidance helps you stay on track.

## 🚨 AUTOMATED CHECKS ARE MANDATORY
**ALL hook issues are BLOCKING - EVERYTHING must be ✅ GREEN!**  
No errors. No formatting issues. No linting problems. Zero tolerance.  
These are not suggestions. Fix ALL issues before continuing.

## CRITICAL WORKFLOW - ALWAYS FOLLOW THIS!

### Research → Plan → Implement
**NEVER JUMP STRAIGHT TO CODING!** Always follow this sequence:
1. **Research**: Explore the codebase, understand existing patterns
2. **Plan**: Create a detailed implementation plan and verify it with me  
3. **Implement**: Execute the plan with validation checkpoints

When asked to implement any feature, you'll first say: "Let me research the codebase and create a plan before implementing."

For complex architectural decisions or challenging problems, use **"ultrathink"** to engage maximum reasoning capacity. Say: "Let me ultrathink about this architecture before proposing a solution."

### USE MULTIPLE AGENTS!
*Leverage subagents aggressively* for better results:

* Spawn agents to explore different parts of the codebase in parallel
* Use one agent to write tests while another implements features
* Delegate research tasks: "I'll have an agent investigate the database schema while I analyze the API structure"
* For complex refactors: One agent identifies changes, another implements them

Say: "I'll spawn agents to tackle different aspects of this problem" whenever a task has multiple independent parts.

### Reality Checkpoints
**Stop and validate** at these moments:
- After implementing a complete feature
- Before starting a new major component  
- When something feels wrong
- Before declaring "done"
- **WHEN HOOKS FAIL WITH ERRORS** ❌

Run: `python run_linters.py && ./run_all_tests.py`

> Why: You can lose track of what's actually working. These checkpoints prevent cascading failures.

### 🚨 CRITICAL: Hook Failures Are BLOCKING
**When hooks report ANY issues (exit code 2), you MUST:**
1. **STOP IMMEDIATELY** - Do not continue with other tasks
2. **FIX ALL ISSUES** - Address every ❌ issue until everything is ✅ GREEN
3. **VERIFY THE FIX** - Re-run the failed command to confirm it's fixed
4. **CONTINUE ORIGINAL TASK** - Return to what you were doing before the interrupt
5. **NEVER IGNORE** - There are NO warnings, only requirements

This includes:
- Formatting issues (Ruff, Black)
- Linting violations (Ruff, Pylint)
- Type checking errors (MyPy)
- Security issues (Bandit)
- Complexity violations (Xenon)
- ALL other checks

Your code must be 100% clean. No exceptions.

**Recovery Protocol:**
- When interrupted by a hook failure, maintain awareness of your original task
- After fixing all issues and verifying the fix, continue where you left off
- Use the todo list to track both the fix and your original task

## Working Memory Management

### When context gets long:
- Re-read this CLAUDE.md file
- Summarize progress in a PROGRESS.md file
- Document current state before major changes

### Maintain TODO.md:
```
## Current Task
- [ ] What we're doing RIGHT NOW

## Completed  
- [x] What's actually done and tested

## Next Steps
- [ ] What comes next
```

## Problem-Solving Together

When you're stuck or confused:
1. **Stop** - Don't spiral into complex solutions
2. **Delegate** - Consider spawning agents for parallel investigation
3. **Ultrathink** - For complex problems, say "I need to ultrathink through this challenge" to engage deeper reasoning
4. **Step back** - Re-read the requirements
5. **Simplify** - The simple solution is usually correct
6. **Ask** - "I see two approaches: [A] vs [B]. Which do you prefer?"

My insights on better approaches are valued - please ask for them!

## Communication Protocol

### Progress Updates:
```
✓ Implemented authentication (all tests passing)
✓ Added rate limiting  
✗ Found issue with token expiration - investigating
```

### Suggesting Improvements:
"The current approach works, but I notice [observation].
Would you like me to [specific improvement]?"

## Working Together

- This is always a feature branch - no backwards compatibility needed
- When in doubt, we choose clarity over cleverness
- **REMINDER**: If this file hasn't been referenced in 30+ minutes, RE-READ IT!

Avoid complex abstractions or "clever" code. The simple, obvious solution is probably better, and my guidance helps you stay focused on what matters.

## Python-Specific Rules

### FORBIDDEN - NEVER DO THESE:
- **NO bare except:** clauses - use specific exception types!
- **NO time.sleep()** in production code without justification - use proper async/await patterns!
- **NO** keeping old and new code together
- **NO** migration functions or compatibility layers
- **NO** versioned function names (process_v2, handle_new)
- **NO** complex inheritance hierarchies
- **NO** TODOs in final code
- **NO** mutable default arguments
- **NO** import * statements

> **AUTOMATED ENFORCEMENT**: Pre-commit hooks will BLOCK commits that violate these rules.  
> When you see `❌ FORBIDDEN PATTERN`, you MUST fix it immediately!

### Required Standards:
- **Delete** old code when replacing it
- **Meaningful names**: `user_id` not `id`
- **Early returns** to reduce nesting
- **Type hints** for all functions: `def process_data(data: List[str]) -> Dict[str, int]:`
- **Docstrings** for all public functions and classes
- **Specific exceptions**: `except ValueError:` not `except Exception:`
- **Context managers** for file operations and resources
- **List comprehensions** for simple transformations
- **Proper logging**: Use `LOGGER.exception()` for errors with stack traces
- **Async/await** for I/O operations, not threads where possible

### Implementation Standards

#### Our code is complete when:
- ✅ All linters pass with zero issues
- ✅ All tests pass  
- ✅ Feature works end-to-end
- ✅ Old code is deleted
- ✅ Type hints on all functions
- ✅ Docstrings on all public APIs

#### Testing Strategy
- Complex business logic → Write tests first
- Simple utilities → Write tests after
- GUI components → Focus on state changes and user interactions
- Network/S3 operations → Mock external dependencies
- Skip tests for simple getters/setters and trivial wrappers

#### Performance & Security

##### **Measure First**:
- No premature optimization
- Use `cProfile` or `line_profiler` for real bottlenecks
- Benchmark before claiming something is faster

##### **Security Always**:
- Validate all inputs with specific types
- Use `secrets` module for randomness
- Parameterized queries for SQL (never string concatenation!)
- Never log sensitive data

## Python Environment
This project uses Python 3.13. A virtual environment should be used:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate the environment
source .venv/bin/activate

# Install dependencies (recommended for development)
pip install -e .[test,dev,typing]

# Or install minimal runtime dependencies
pip install -e .
```

-## Build, Lint & Test Commands
- Run all tests (local dev): `./run_all_tests.py`
- Run tests for CI/headless: `./run_non_gui_tests_ci.py`
- Run a single test: `python -m pytest tests/path/to/test_file.py`
- Run a specific test function: `python -m pytest tests/path/to/test_file.py::test_function_name`
- Run with debug options: `./run_all_tests.py --debug-mode`
- Run in parallel: `./run_all_tests.py --parallel 4`
- Launch application: `source .venv/bin/activate && python -m goesvfi.gui`
- Debug mode: `source .venv/bin/activate && python -m goesvfi.gui --debug`

### Linting Commands
The project uses Ruff as the primary linter but maintains all traditional linters as options:
- Run primary linters (default): `python run_linters.py`
- Run ALL linters: `python run_linters.py --all`
- **Primary linters (recommended)**:
  - **Ruff linter**: `python run_linters.py --ruff-only` (handles most linting needs)
  - **MyPy type checking**: `python run_linters.py --mypy-only`
  - **Bandit security scanner**: `python run_linters.py --bandit-only`
  - **Xenon complexity checker**: Integrated with ruff configuration
- **Additional/legacy linters (available as options)**:
  - **Flake8**: `python run_linters.py --flake8-only`
  - **Flake8-Bugbear**: `python run_linters.py --bugbear-only`
  - **Black code formatter**: `python run_linters.py --black-only`
  - **isort import sorter**: `python run_linters.py --isort-only`
  - **Pylint**: `python run_linters.py --pylint-only`
  - **Vulture (dead code)**: `python run_linters.py --vulture-only`
  - **Safety (dependencies)**: `python run_linters.py --safety-only`
  - **Pyright type checker**: `python run_linters.py --pyright-only`
- **Format code**:
  - Check formatting only (default): `python run_linters.py --check`
  - Apply formatting changes: `python run_linters.py --format`
- **Options**:
  - Specific paths: `python run_linters.py path/to/file_or_directory`
  - MyPy strict mode: `python run_linters.py --mypy-only --strict`
  - Auto-fix issues: `python run_linters.py --fix`

**Note**: While Ruff handles most linting needs efficiently, all traditional linters remain available for specific use cases or team preferences.

## Project Structure and Organization

The repository has been reorganized to follow a clean, maintainable structure that separates core code, tests, and documentation. The reorganization focuses on:

1. **Proper Packaging**: Core code is in the `goesvfi` package with appropriate submodules
2. **Test Organization**: Tests are categorized by type (unit, integration, GUI)
3. **Documentation**: Documentation files are stored in the `docs` directory
4. **Data & Logs**: Large data files and logs are separated and excluded from Git

An overview of the directory structure can be found in [DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md).

### Avoiding Large File Commits

When working on this codebase, NEVER commit large data files (.nc files, large .png files). The repository includes a [cleanup.py](cleanup.py) script that can be used to clean up temporary data files before committing:

```bash
# List large files without deleting them
python cleanup.py --list-only

# Clean up all large files automatically
python cleanup.py --delete-data
```

## Test Organization and Strategy

**CRITICAL: Never skip tests. If a test is being skipped, it defeats the purpose of having it. All tests should either pass or fail - skipping tests provides no value and hides potential issues. If a test cannot run in certain environments, it should be fixed or removed, not skipped. Tests that are skipped are essentially dead code that gives a false sense of security.**

The repository has a well-organized structure for tests:

### Test Directories
- `/tests/unit/`: Unit tests for individual components
- `/tests/integration/`: Integration tests for component interactions
- `/tests/gui/`: Tests for the PyQt6 user interface
  - `/tests/gui/imagery/`: Tests for imagery-related GUI components
  - `/tests/gui/tabs/`: Tests for various tab components
- `/tests/utils/`: Test utilities and helpers

### Legacy Tests
- `/legacy_tests/`: Contains potentially redundant or outdated tests for evaluation

### Testing Best Practices
These practices should be followed for all new tests:
1. **Test Independence**: Each test should run independently of others.
2. **Avoid Network Dependencies**: Mock external services and AWS S3 access.
3. **Use Fixtures**: Utilize pytest fixtures for common setup and teardown.
4. **Type Safety**: All test code should follow type hint best practices.
5. **Error Isolation**: Each test should clearly identify what feature is being tested.
6. **Test Naming**: Follow `test_{component}_{functionality}_{condition}` naming convention.


### Test Runner Scripts
Multiple test runners are provided for different testing scenarios:
- `run_all_tests.py`: Complete test suite for local development (includes GUI tests)
- `run_non_gui_tests_ci.py`: Non-GUI tests for CI/headless environments
- `run_coverage.py`: Code coverage analysis and reporting

## Known Test Issues
- Some GUI tests may cause segmentation faults when testing FFmpeg controls directly
- Currently fixed and reliable tests include:
  - `test_initial_state`: Verifies initial UI state
  - `test_successful_completion`: Verifies UI updates after successful process completion
  - `test_change_settings_main_tab`: Tests settings in the main tab safely
  - `test_change_ffmpeg_profile`: Tests FFmpeg profile selection with extra safeguards

### GUI Testing Best Practices
1. Use `QApplication.processEvents()` frequently to ensure UI updates
2. Mock problematic signals to prevent cascading failures
3. Split tests into smaller, focused tests to isolate issues
4. Manually call update methods rather than relying on signal propagation
5. Add explicit `blockSignals(True/False)` around critical widget state changes
6. Restore original widget states at the end of each test
7. Add robust error handling in test teardown

## Code Style Guidelines
- Follow PEP 8 strictly; formatting done with Black (line length: 88)
- Use type hints for all functions/methods with Python's `typing` module
- Imports: Prefer absolute imports (e.g., `from goesvfi.utils import log`)
- Naming: `snake_case` for functions/variables, `CamelCase` for classes, `UPPER_SNAKE_CASE` for constants
- Logging: Use `LOGGER = log.get_logger(__name__)` for module-level logging
- Error handling: Use try/except with specific exceptions, log with `LOGGER.exception()`
- UI components: Follow MVVM pattern with view models for state management
- Testing: Use pytest fixtures for common setup/teardown operations

## Type Safety and Mypy

The codebase now has comprehensive type annotations and passes mypy checks in both standard and strict modes for core files. When adding or modifying code:

- Always include type annotations for function parameters and return values
- Use `Optional[Type]` when a value might be None
- Use `Union[Type1, Type2]` for variables that could have multiple types
- Properly annotate class attributes in `__init__` methods
- For numpy arrays, use `numpy.typing.NDArray[np.float64]` with specific dtype
- For collections, specify contained type: `List[str]`, `Dict[str, int]`, etc.
- Use type narrowing with `isinstance()` checks where needed
- Use `TypeVar` and generic types for polymorphic functions

### Mypy Checks

Run mypy checks with:
```bash
# Standard mode
python -m run_mypy_checks

# Strict mode
python -m run_mypy_checks --strict
```

Common mypy issues to watch for:
- Missing return type annotations (no-untyped-def)
- Untyped attribute access in class instances
- Improper use of `Optional` without checking for None
- Missing generic type parameters (e.g., `List` vs `List[str]`)
- Incompatible return types in functions

### Type-Related Improvements

Recent type safety improvements include:
- Full type annotation for async methods
- Proper error handling types
- Complete numpy array typing with appropriate dtypes
- Generic type parameters for exception handling
- Type safe logging and configuration utilities

## S3 Access and Network Resilience

The project includes robust patterns for accessing NOAA's S3 buckets. When working with S3 access code:

### Best Practices
1. **Error Handling**: Always use the custom `RemoteStoreError` hierarchy for S3 errors
2. **Retry Logic**: Include configurable retry strategies for transient network issues
3. **Timeouts**: Set appropriate timeouts for all S3 operations (connection and read)
4. **Diagnostics**: Include network diagnostics in error messages (DNS resolution, connectivity)
5. **Anonymous Access**: Use `boto3.UNSIGNED` for public bucket access
6. **Progress Reporting**: Implement progress callbacks for large downloads
7. **Statistics Collection**: Gather download statistics for monitoring
8. **Thread Safety**: Ensure S3 client instances are thread-safe with proper initialization
9. **Cancellation**: Support async cancellation in long-running operations

### S3 Store Implementation
The `S3Store` class in `goesvfi.integrity_check.remote.s3_store` provides a robust implementation with:
- Comprehensive error handling
- Connection diagnostics
- Download statistics
- Async context manager support
- Type-safe interfaces

### Testing S3 Code
When writing tests for S3 code:
- Use the mocking utilities in `tests/utils/mocks.py`
- Create realistic error scenarios
- Test both success and failure paths
- Verify proper handling of network timeouts
- Simulate different AWS error responses

## GOES Satellite Data Processing

The project includes components for handling GOES satellite data, particularly from the Advanced Baseline Imager (ABI) instrument. Understanding these patterns is essential when working with this code:

### GOES Data Access Patterns
- **ABI Bands**: Represented by the `ChannelType` class with band numbers, wavelengths, and descriptions
- **Products**: Various product types (RadF, RadC, RadM) for full disk, CONUS, and mesoscale regions
- **File Patterns**: Standard naming conventions in `time_index.py` for S3 objects
- **Timestamp Handling**: Date/time manipulation with year, day-of-year, and hour components
- **Scan Patterns**: Different scan schedules for full disk (15 min), CONUS (5 min), and mesoscale (1 min)

### NetCDF Processing
When working with NetCDF data files:
- Use the utilities in `goesvfi.integrity_check.render.netcdf` for extraction and processing
- Handle multi-band data appropriately
- Apply proper scaling, normalization, and calibration to raw satellite values
- Consider different visualization approaches for each band (false color, etc.)

### Satellite Imagery Visualization
For visualization components:
- Use the `VisualizationManager` for consistent rendering and comparisons
- Follow consistent colormap usage for specific bands
- Apply proper contrast enhancement and normalization
- Support multi-band composites for true color and false color


## Development Best Practices
- Always run linters on changed code before committing:
  - For quick checks: `python run_linters.py path/to/changed_file.py`
  - For comprehensive checks: `python run_linters.py`
- **Primary linting tools** (used by pre-commit hooks):
  - **Ruff**: Primary linter (style, formatting, import sorting, static analysis)
  - **MyPy**: Type checking
  - **Bandit**: Security vulnerability scanning
  - **Xenon**: Code complexity analysis
- **Additional linters available** (via run_linters.py):
  - **Flake8**: Traditional style checker
  - **Black/isort**: Legacy formatting tools (functionality covered by Ruff)
  - **Pylint**: Comprehensive static analysis
  - **Vulture**: Dead code detection
  - **Safety**: Dependency vulnerability scanning
  - **Pyright**: Alternative type checker
- Ensure consistent formatting with pre-commit hooks:
  - Ruff handles formatting, import ordering, and most style checking
  - MyPy for type checking
  - Bandit for security scanning

## Pre-commit Hooks Policy

**CRITICAL: NEVER EVER SKIP PRE-COMMIT HOOKS. PERIOD.**

Pre-commit hooks are essential for maintaining code quality and consistency. They exist to catch issues before they enter the codebase. The whole point of pre-commit hooks is to enforce standards automatically.

When pre-commit hooks fail:
1. **DO NOT** use `--no-verify` or any flag to bypass them
2. **DO NOT** disable the hooks temporarily
3. **DO NOT** commit anyway and plan to fix later
4. **ALWAYS** fix the issues that pre-commit hooks identify
5. **ALWAYS** ensure all hooks pass before committing

### Active Pre-commit Hooks
- **Ruff**: Primary linter (style, formatting, import sorting, static analysis)
- **MyPy**: Type checking
- **Bandit**: Security vulnerability scanning
- **Xenon**: Code complexity analysis (C grade or better)

### Common pre-commit hook failures and fixes:
- **Ruff violations**: Fix code style, formatting, and static analysis issues identified
- **Ruff formatting**: Run `python run_linters.py --format` to auto-format the code
- **MyPy type errors**: Add proper type annotations
- **Bandit security issues**: Fix security vulnerabilities
- **Xenon complexity**: Refactor overly complex functions (C grade threshold)
- **Trailing whitespace**: Remove all trailing whitespace (handled by Ruff)
- **Missing newlines**: Ensure files end with a newline (handled by Ruff)
- **Large files**: Remove or gitignore large files before committing

### Code Complexity Standards
The project enforces a **C grade or better** complexity threshold for all code using Xenon. Functions with D, E, or F complexity grades will be rejected by pre-commit hooks.

Remember: Pre-commit hooks are there to help maintain code quality. Skipping them defeats their entire purpose and introduces technical debt.
