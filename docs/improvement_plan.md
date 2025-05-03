# GOES_VFI Refactoring Plan

**Overall Goal:** Optimize the codebase for significantly improved maintainability, modularity, testability, and ease of future development.

**Prioritization Legend:**
*   **High:** Critical for core functionality, stability, or major maintainability gains.
*   **Medium:** Important for improving structure, reducing technical debt, or enhancing developer experience.
*   **Low:** Nice-to-have improvements, can be deferred.

---

## 1. FFmpeg Command Generation (Priority: High)

*   **Analysis:** FFmpeg command generation logic is likely embedded within `goesvfi/pipeline/run_ffmpeg.py` and potentially duplicated or tightly coupled within `goesvfi/run_vfi.py` or other pipeline steps. This makes it hard to test, modify, or reuse the command generation logic independently.
*   **Proposed Solution:**
    *   Implement a dedicated `FFmpegCommandBuilder` class following the Builder design pattern.
    *   This class will encapsulate the logic for constructing FFmpeg commands based on various configuration options (input files, output format, resolution, frame rate, quality settings, etc.).
    *   Define a clear interface for the builder, accepting configuration parameters and returning the final command string or list of arguments.
*   **Concrete Steps:**
    1.  Identify all locations where FFmpeg commands are constructed.
    2.  Define the `FFmpegCommandBuilder` class structure and its methods (e.g., `setInputFiles()`, `setOutputFormat()`, `setResolution()`, `build()`).
    3.  Implement the command construction logic within the builder methods.
    4.  Refactor existing code to instantiate and use the `FFmpegCommandBuilder` instead of constructing commands directly.
    5.  Remove the old command generation logic.
*   **Benefits:**
    *   **Isolation:** Command generation logic is centralized and decoupled.
    *   **Testability:** The builder class can be unit-tested easily with various configurations.
    *   **Reusability:** The builder can be reused in different parts of the application or in future tools.
    *   **Maintainability:** Easier to update or add new FFmpeg options.
*   **Potential Risks:**
    *   Ensuring the builder covers all existing command variations and options.
    *   Complexity in handling conditional logic for different FFmpeg features.
*   **Testing Strategy:**
    *   **Unit Tests:** Create comprehensive unit tests for the `FFmpegCommandBuilder` covering various valid and invalid configurations, edge cases, and option combinations. Verify the generated command strings are correct.

---

## 2. Image Processing Decoupling (Priority: High)

*   **Analysis:** Image processing tasks (loading, Sanchez processing via `goesvfi/sanchez/runner.py`, potential cropping) seem distributed. Loading might be in `goesvfi/pipeline/loader.py`, Sanchez processing is external, and cropping logic location is unclear (could be GUI or pipeline). This tight coupling makes it difficult to swap implementations, test individual steps, or manage dependencies.
*   **Proposed Solution:**
    *   Define an `ImageProcessor` interface (or abstract base class) with methods like `load()`, `process()`, `crop()`, `save()`.
    *   Create concrete implementations for each step:
        *   `ImageLoader` (handles reading image files).
        *   `SanchezProcessor` (wraps the call to `goesvfi/sanchez/runner.py`, potentially managing the external process).
        *   `ImageCropper` (encapsulates cropping logic).
    *   Refactor the pipeline or relevant components to use these interfaces, potentially via Dependency Injection.
*   **Concrete Steps:**
    1.  Define the `ImageProcessor` interface and associated data structures (e.g., an `ImageData` class).
    2.  Implement the `ImageLoader`, `SanchezProcessor`, and `ImageCropper` classes conforming to the interface.
    3.  Identify where image loading, Sanchez processing, and cropping occur currently.
    4.  Refactor these locations to use the new processor classes through their interface.
    5.  Inject dependencies where appropriate (e.g., pass processor instances to pipeline stages).
*   **Benefits:**
    *   **Modularity:** Each processing step is a distinct, replaceable component.
    *   **Testability:** Individual processors can be unit-tested in isolation (using mock inputs/outputs for `SanchezProcessor`).
    *   **Flexibility:** Easier to add new processing steps or replace existing ones (e.g., use a different reprojection library instead of Sanchez).
    *   **Maintainability:** Code for specific tasks is localized.
*   **Potential Risks:**
    *   Designing a flexible enough `ImageProcessor` interface to accommodate different step requirements.
    *   Managing the state (image data) between processing steps efficiently.
    *   Complexity in managing the external Sanchez process wrapper.
*   **Testing Strategy:**
    *   **Unit Tests:** Test `ImageLoader` with various file types/paths. Test `ImageCropper` with different parameters. Test `SanchezProcessor` by mocking the external process call and verifying arguments/outputs.
    *   **Integration Tests:** Test the sequence of processors working together within the pipeline using sample images.

---

## 3. GUI Refactoring (`MainWindow`) (Priority: High)

*   **Analysis:** The `MainWindow` class in `goesvfi/gui.py` is likely a large, monolithic class handling UI elements, event handling, application logic, and state management, typical of GUI applications without a clear architectural pattern. This makes the GUI difficult to test, maintain, and extend. The presence of `gui_tab.py` files in sorter modules suggests attempts at modularity, but the core `MainWindow` might still be overburdened.
*   **Proposed Solution:**
    *   Refactor `MainWindow` using a suitable GUI architectural pattern like Model-View-ViewModel (MVVM) or Model-View-Controller (MVC).
    *   **View:** Keep `MainWindow` (and other UI components) responsible only for displaying data and routing user input events. Minimize logic here.
    *   **ViewModel/Controller:** Create separate classes to handle presentation logic, state management, and interactions with the backend/model. This layer fetches data, processes user commands, and updates the View.
    *   **Model:** Represent the application's data and business logic (potentially interacting with the refactored image processing, FFmpeg, and config components).
*   **Concrete Steps:**
    1.  Choose a GUI pattern (MVVM is often suitable for Python GUI toolkits like PyQt/PySide if used, MVC is more general).
    2.  Identify distinct responsibilities currently within `MainWindow`: UI rendering, event handling, data manipulation, backend calls.
    3.  Create new ViewModel/Controller classes to encapsulate non-UI logic.
    4.  Create Model classes or interfaces to represent application data and business rules.
    5.  Gradually move logic from `MainWindow` to the appropriate ViewModel/Controller or Model layers.
    6.  Establish clear communication channels between View, ViewModel/Controller, and Model (e.g., data binding, signals/slots, observer pattern).
    7.  Refactor GUI tabs (`gui_tab.py`) to integrate cleanly with the chosen pattern.
*   **Benefits:**
    *   **Testability:** ViewModel/Controller and Model layers can be unit-tested independently of the UI.
    *   **Maintainability:** Separation of concerns makes code easier to understand, modify, and debug.
    *   **Scalability:** Easier to add new features or modify existing ones without breaking unrelated parts.
    *   **Reusability:** ViewModel/Controller logic might be reusable if the UI toolkit changes.
*   **Potential Risks:**
    *   Significant structural changes required, potentially time-consuming.
    *   Learning curve associated with the chosen GUI pattern.
    *   Complexity in managing state and communication between layers.
*   **Testing Strategy:**
    *   **Unit Tests:** Test ViewModel/Controller logic thoroughly. Test Model logic.
    *   **Integration Tests:** Test interactions between View, ViewModel/Controller, and Model.
    *   **(Optional) UI Tests:** Use UI testing frameworks if available for the toolkit to simulate user interactions, though these can be brittle.

---

## 4. Configuration Management Standardization (Priority: Medium)

*   **Analysis:** A `goesvfi/utils/config.py` exists, suggesting some centralized configuration handling. However, the user suspects configuration might be scattered or inconsistently accessed. Settings could be hardcoded, read from multiple file types, or managed differently across modules.
*   **Proposed Solution:**
    *   Implement a `ConfigManager` class, possibly as a Singleton or managed via Dependency Injection, to be the single source of truth for all configuration settings.
    *   Standardize on a single configuration file format (e.g., YAML, JSON, or TOML - `pyproject.toml` already exists, consider using it or a dedicated file).
    *   The `ConfigManager` should handle loading configuration from the chosen source, providing type-safe accessors, and potentially handling defaults and validation.
*   **Concrete Steps:**
    1.  Audit the codebase to identify all sources and access points for configuration settings.
    2.  Define the structure and format for the standardized configuration file(s).
    3.  Implement the `ConfigManager` class with methods for loading, accessing, and potentially saving configuration. Include validation logic.
    4.  Refactor all parts of the codebase to obtain configuration exclusively through the `ConfigManager`.
    5.  Remove old configuration loading/access logic and hardcoded values.
    6.  Document the configuration file structure and usage.
*   **Benefits:**
    *   **Centralization:** All configuration logic is in one place.
    *   **Consistency:** Uniform way to access settings across the application.
    *   **Maintainability:** Easier to find, understand, and modify configuration settings.
    *   **Testability:** `ConfigManager` can be tested, and components using it can be tested by providing mock configurations.
*   **Potential Risks:**
    *   Missing some scattered configuration access points during the audit.
    *   Deciding on the best configuration format and structure.
    *   Managing default values and user overrides effectively.
*   **Testing Strategy:**
    *   **Unit Tests:** Test the `ConfigManager` for loading valid/invalid files, accessing different setting types, handling defaults, and validation rules.

---

## 5. General Enhancements (Priority: Medium - Ongoing)

*   **Analysis:** The project has existing structures for logging (`goesvfi/utils/log.py`) and testing (`tests/`), but their consistency, coverage, and effectiveness might vary. Error handling, code style, and documentation practices may not be standardized across the codebase.
*   **Proposed Solution:**
    *   **Error Handling:** Define a consistent strategy. Use specific custom exception classes for application-domain errors instead of generic exceptions. Ensure errors are caught and handled gracefully (e.g., logged, reported to the user).
    *   **Logging:** Standardize log formats (e.g., include timestamp, level, module name). Configure logging levels appropriately (e.g., INFO for general flow, DEBUG for details). Use the existing `goesvfi/utils/log.py` consistently.
    *   **Testing:** Increase test coverage, particularly for refactored components (unit tests) and critical workflows (integration tests). Ensure tests in `tests/` are well-organized and follow best practices. Add tests for GUI components if feasible.
    *   **Code Style:** Adopt and enforce a specific Python style guide (e.g., PEP 8). Use tools like `Black` for auto-formatting and `Flake8` or `Pylint` for linting. Integrate these into the development workflow (e.g., pre-commit hooks).
    *   **Documentation:** Improve docstrings for modules, classes, and functions according to a standard (e.g., Google style, NumPy style). Enhance the `README.md` with clear setup, usage, and contribution guidelines. Maintain the `CHANGELOG.md`. Add architectural diagrams or documentation where helpful (e.g., in the `docs/` directory).
*   **Concrete Steps:**
    1.  Define custom exception classes. Refactor `try...except` blocks.
    2.  Review and configure the logging setup in `goesvfi/utils/log.py`. Ensure consistent usage.
    3.  Analyze test coverage (e.g., using `pytest-cov`). Write new unit and integration tests, focusing on areas with low coverage or high complexity.
    4.  Configure `Black` and `Flake8`/`Pylint`. Run them across the codebase. Set up pre-commit hooks.
    5.  Review and update docstrings. Improve `README.md` and other documentation in `docs/`.
*   **Benefits:**
    *   **Robustness:** Better error handling leads to a more stable application.
    *   **Maintainability:** Consistent logging, style, and good documentation make the code easier to understand and work with.
    *   **Reliability:** Higher test coverage increases confidence in code correctness.
    *   **Collaboration:** Standardized practices improve team collaboration.
*   **Potential Risks:**
    *   Can be time-consuming to apply consistently across a large codebase.
    *   Debates over specific style rules or documentation standards.
    *   Writing effective tests, especially for GUI and external process interactions, can be challenging.
*   **Testing Strategy:**
    *   Relies heavily on implementing the testing improvements themselves (unit, integration tests).
    *   Static analysis tools (`Flake8`, `Pylint`, `MyPy`) verify style and type hints.
    *   Code reviews ensure adherence to standards.

---