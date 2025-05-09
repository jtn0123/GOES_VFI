# Legacy Tests Evaluation Checklist

This document provides a checklist for evaluating the legacy tests in this directory. For each test, we need to determine whether to update it, move it, or remove it.

## Test Files

### 1. `test_s3_unsigned_access.py`

- [ ] Compared with `tests/unit/test_s3_unsigned_access.py`
- [ ] Determined if functionality is fully covered by newer test
- [ ] Decision:
  - [ ] Update and move to proper test directory
  - [ ] Convert to example
  - [ ] Remove (redundant)

### 2. `test_real_s3_paths.py`

- [ ] Compared with `tests/unit/test_real_s3_patterns.py`
- [ ] Determined if functionality is fully covered by newer test
- [ ] Decision:
  - [ ] Update and move to proper test directory
  - [ ] Convert to example
  - [ ] Remove (redundant)

### 3. `test_real_s3_path.py`

- [ ] Compared with `tests/unit/test_real_s3_patterns.py`
- [ ] Determined if functionality is fully covered by newer test
- [ ] Decision:
  - [ ] Update and move to proper test directory
  - [ ] Convert to example
  - [ ] Remove (redundant)

### 4. `test_imagery_simplified.py`

- [ ] Compared with `tests/gui/imagery/test_imagery_simple.py`
- [ ] Determined if functionality is fully covered by newer test
- [ ] Decision:
  - [ ] Update and move to proper test directory
  - [ ] Convert to example
  - [ ] Remove (redundant)

## Evaluation Process

For each test file, follow these steps:

1. **Review test contents** - Understand what the test is checking
2. **Compare with newer equivalent** - Determine if all test cases are covered in newer tests
3. **Check test quality** - Assess whether the test follows good testing practices
4. **Make decision** - Decide whether to update, move, or remove the test
5. **Update checklist** - Check off the appropriate boxes and record decision

## Once Evaluation Is Complete

After all tests have been evaluated:

1. **Update relevant test runners** - Ensure test runners reference the correct paths
2. **Run tests** - Verify all tests still pass after reorganization
3. **Update documentation** - Update any documentation that references test paths