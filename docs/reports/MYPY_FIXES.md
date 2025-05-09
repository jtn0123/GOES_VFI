Type error fixes completed in multiple files:

## Fixed Issues

1. Fixed union type operation errors in s3_store.py with proper type narrowing
2. Fixed QHeaderView null checks in gui_tab.py
3. Fixed QDateTime conversion to Python datetime in gui_tab.py
4. Added type ignore for Path assignment in gui_tab.py where setter handles conversion
5. Fixed wheelEvent signature in gui_helpers.py
6. Fixed mousePressEvent and mouseReleaseEvent signatures in main_tab.py
7. Fixed None/Any indexing error in main_tab.py with proper None checks
8. Added Optional to function parameter types in main_tab.py
9. Fixed type annotations for ffmpeg_args in main_tab.py
10. Added Dict[str, Any] type annotations for dictionary values
11. Fixed sorter tab view model instantiations in gui_backup.py
12. Fixed log level setting in gui_backup.py

## Remaining Issues

- Missing type stubs for third-party libraries (boto3, aioboto3, botocore)
- These errors can be ignored as they are related to external dependencies

## Plan for Fixing Strict Mode Mypy Issues

With `--strict` and `--check-untyped-defs` flags, we found 319 errors across 26 files. Here's a comprehensive plan to address them:

### Phase 1: Fix Missing Function Annotations (no-untyped-def)
1. Create type annotation templates for common patterns:
   - Event handlers: `def on_click(self) -> None:`
   - Property getters/setters: `def get_value(self) -> Type:`
   - Callbacks: `def callback(self, value: Type) -> None:`

2. Tackle files in order of importance:
   - Start with core utility files (utils/)
   - Then model and view-model classes
   - Finally UI components

3. For each file:
   - Add return type annotations (most commonly `-> None`)
   - Add parameter type annotations
   - Use `Optional[Type]` for nullable parameters
   - Add `self` type annotations in class methods

### Phase 2: Address Untyped Calls (no-untyped-call)
1. Focus on code that calls untyped functions:
   - Add type annotations to called functions first
   - If the called function is from a third-party library without stubs, use `cast()` or `# type: ignore[no-untyped-call]`

### Phase 3: Fix Generic Type Parameters (type-arg)
1. Replace `dict` with `Dict[KeyType, ValueType]`
2. Replace `list` with `List[ItemType]`
3. Add type parameters to `Pattern` and other generic types

### Phase 4: Fix Any Returns (no-any-return)
1. For functions returning Any when a specific type is declared:
   - Fix return types to match declarations
   - Use type narrowing or casting where necessary
   - Add proper null checks before returning

### Implementation Strategy
1. Create a script to track progress:
   - Count errors by category and file
   - Track fixed vs. remaining errors

2. Create file-specific task lists ordered by priority:
   - Focus on files with most errors first
   - Create annotated examples for common patterns

3. Apply fixes systematically:
   - First pass: Add missing annotations
   - Second pass: Fix generic types
   - Third pass: Fix Any returns

4. For each file:
   - Run mypy after changes to verify fixes
   - Create incremental commits to track progress

### Expected Outcome
1. 100% mypy compliance in strict mode for application code
2. Proper type annotations throughout the codebase
3. Improved code readability and maintenance
4. Enhanced IDE type hinting and error detection

This plan will provide a systematic approach to addressing all type issues throughout the codebase while prioritizing the most important fixes first.
