# Plan for Fixing MyPy Errors

## Priority Order

We'll address the mypy errors in the following order:

1. **Core application files first**
   - Focus on the integrity_check module which contains the main functionality
   - Fix the shared_components.py file which has multiple errors

2. **GUI components second**
   - Fix emergency_button.py which has simple errors
   - Address gui_helpers.py issues

3. **Utilities and other modules last**
   - Address time_index.py for missing generic type parameters

## File-by-File Approach

### 1. goesvfi/integrity_check/shared_components.py (Priority: High)

This file has numerous mypy errors including:
- Missing type annotations for functions
- Missing return type annotations
- Untyped function calls

```python
# Example issues to fix:
def initUI():  # Missing return type annotation
    ...

class PreviewPanel:
    def setImage():  # Missing parameter annotations
        ...
```

### 2. goesvfi/gui_tabs/emergency_button.py (Priority: Medium)

Simple issues that can be fixed quickly:
- Missing return type annotations
- Untyped function calls

```python
# Example issues to fix:
def initUI():  # Should be: def initUI() -> None:
    ...
```

### 3. goesvfi/utils/gui_helpers.py (Priority: Medium)

Contains a few mypy errors:
- Missing type annotations
- Missing return types

```python
# Example issues to fix:
def create_button():  # Missing parameter and return type annotations
    ...
```

### 4. goesvfi/integrity_check/time_index.py (Priority: Low)

Issues related to generic types:
- Missing type parameters for Pattern

```python
# Example issues to fix:
Pattern = re.compile(r'pattern')  # Should be: Pattern[str] = re.compile(r'pattern')
```

## Implementation Approach

For each file:

1. **Create a backup** of the original file
2. **Add missing types** systematically:
   - Add return type annotations (-> None for void functions)
   - Add parameter type annotations
   - Add generic type parameters
3. **Run mypy in strict mode** after each file is updated
4. **Create a commit** after each file is fixed

## Types to Use

- For PyQt widgets: Use specific widget types (QWidget, QPushButton, etc.)
- For callbacks: Use Callable[[param_types], return_type]
- For collections: Use proper generic types (List[str], Dict[str, Any], etc.)
- For optional values: Use Optional[Type]

## Testing Strategy

After each file is fixed:
1. Run mypy in strict mode
2. Run the application to ensure no runtime errors
3. Test the affected functionality
