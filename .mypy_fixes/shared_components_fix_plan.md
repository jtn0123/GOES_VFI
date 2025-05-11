# Plan for Fixing MyPy Issues in shared_components.py

## Issues to Fix

1. Missing type annotation for `__init__` method (line 120)
   - Add proper type for `parent` parameter
   - Return type should be `None`

2. Missing return type for `initUI` method (line 134)
   - Add `-> None` return type

3. Missing return types for other methods:
   - `setImage` (line 205)
   - `clearImage` (line 229)
   - `showMetadata` (line 297)
   - `bookmarkImage` (line 318)
   - `updateButtonStatus` (line 347)
   - `clearMetadata` (line 370)
   - `setInfoText` (line 552)
   - `updateLayout` (line 609)

4. Missing type annotations for methods:
   - `create_presets_section` (line 615)
   - `create_data_section` (line 624)
   - `create_visualization_section` (line 642)
   - `create_processing_section` (line 720)
   - `create_advanced_section` (line 745)
   - `create_output_section` (line 805)
   - `create_controls_section` (line 911)
   - `create_network_section` (line 959)

5. Fix untyped function calls:
   - `initUI` (line 132)
   - `create_presets_section` (line 686)
   - `create_data_section` (line 691)
   - `create_visualization_section` (line 696)
   - `create_processing_section` (line 701)
   - `create_advanced_section` (line 706)

## Type Definitions Needed

1. Define `PreviewMetadata` class or type alias for metadata structures
2. Add proper typing for collections like `preview_cache` and `bookmarks`
3. Use `Optional[QWidget]` for optional parent parameters
4. Use `Optional[str]` for nullable string parameters
5. Add proper return types for all methods (mostly `-> None`)

## Implementation Steps

1. First add necessary imports:
   ```python
   from typing import Dict, Set, List, Optional, Union, Any, Tuple, TypedDict, cast
   ```

2. Define `PreviewMetadata` as a TypedDict:
   ```python
   class PreviewMetadata(TypedDict, total=False):
       """Type definition for preview metadata."""
       channel: Union[int, str]
       product_type: str
       date_time: datetime
       source: str
       filename: str
       resolution: str
       # Other optional fields
       additional_info: Dict[str, Any]
   ```

3. Fix class initialization methods with proper type annotations

4. Add return types to all methods

5. Annotate function parameters for all helper methods

6. Fix untyped function calls by properly annotating the called functions

7. Test with mypy strict mode after each section is fixed
