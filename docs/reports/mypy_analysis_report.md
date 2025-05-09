# MyPy Analysis Report

## Summary
- Total errors: 319
- Files with errors: 26

## Errors by Category
- no-untyped-def (159): Missing function annotations
- no-untyped-call (129): Calls to untyped functions
- type-arg (8): Missing generic type parameters
- import-untyped (8): Untyped imports
- no-any-return (7): Returning Any from typed function
- comparison-overlap (2): Other issues
- attr-defined (2): Undefined attribute access
- call-overload (1): Other issues
- arg-type (1): Argument type mismatches
- redundant-cast (1): Other issues
- name-defined (1): Other issues

## Top Files with Errors
1. goesvfi/integrity_check/enhanced_imagery_tab.py (99 errors)
2. goesvfi/integrity_check/sample_processor.py (33 errors)
3. goesvfi/integrity_check/goes_imagery_tab.py (28 errors)
4. goesvfi/integrity_check/shared_components.py (26 errors)
5. goesvfi/integrity_check/visualization_manager.py (21 errors)
6. goesvfi/integrity_check/combined_tab_refactored.py (21 errors)
7. goesvfi/integrity_check/enhanced_gui_tab.py (15 errors)
8. goesvfi/integrity_check/goes_imagery.py (14 errors)
9. goesvfi/integrity_check/thread_cache_db.py (9 errors)
10. goesvfi/integrity_check/gui_tab.py (8 errors)

## Detailed Analysis of Top Files
### goesvfi/integrity_check/enhanced_imagery_tab.py (99 errors)
- no-untyped-call: 61
- no-untyped-def: 36
- attr-defined: 2

### goesvfi/integrity_check/sample_processor.py (33 errors)
- no-untyped-call: 18
- no-untyped-def: 13
- import-untyped: 2

### goesvfi/integrity_check/goes_imagery_tab.py (28 errors)
- no-untyped-def: 15
- no-untyped-call: 11
- call-overload: 1
- arg-type: 1

## Example Fixes for Common Errors
### Missing Function Annotations (no-untyped-def)
```python
# Before
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result

# After
from typing import List, Any

def process_data(data: List[int]) -> List[int]:
    result: List[int] = []
    for item in data:
        result.append(item * 2)
    return result
```
