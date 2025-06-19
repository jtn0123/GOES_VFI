# GOES_VFI Documentation

This directory contains the complete documentation for GOES_VFI, built using [Sphinx](https://www.sphinx-doc.org/).

## Quick Start

### Building Documentation Locally

1. **Install documentation dependencies:**
   ```bash
   pip install -r docs/requirements.txt
   ```

2. **Generate and build documentation:**
   ```bash
   cd docs
   make html
   ```

3. **View documentation:**
   ```bash
   make serve
   # Opens http://localhost:8000
   ```

### Live Reload Development

For documentation development with live reload:

```bash
cd docs
make livehtml
# Opens http://localhost:8000 with auto-refresh
```

## Documentation Structure

```
docs/
├── conf.py                 # Sphinx configuration
├── index.rst              # Main documentation index
├── installation.rst       # Installation guide
├── quickstart.rst         # Quick start guide
├── api/                   # API reference documentation
│   ├── index.rst         # API overview
│   ├── pipeline.rst      # Pipeline API docs
│   └── utils.rst         # Utilities API docs
├── user_guide/           # User guide (to be created)
├── tutorials/            # Tutorials (to be created)
├── development/          # Developer guide (to be created)
├── _static/              # Static assets (CSS, images)
│   └── custom.css       # Custom styling
├── _templates/           # Custom templates
└── _build/               # Generated documentation (auto-created)
```

## Available Build Targets

- `make html` - Build HTML documentation
- `make pdf` - Build PDF documentation (requires LaTeX)
- `make epub` - Build EPUB documentation
- `make clean` - Clean build directory
- `make livehtml` - Live reload development server
- `make check` - Check for broken links and warnings
- `make serve` - Simple HTTP server for built docs

## Automated Documentation Generation

Use the documentation generation script:

```bash
# Generate API documentation from code
python scripts/generate_docs.py

# Generate and build in one step
python scripts/generate_docs.py --build

# Check documentation coverage
python scripts/generate_docs.py --coverage

# Build different formats
python scripts/generate_docs.py --build --format pdf
```

## Writing Documentation

### API Documentation

API documentation is automatically generated from docstrings. Follow these guidelines:

1. **Use Google-style docstrings:**
   ```python
   def example_function(param1: str, param2: int = 10) -> bool:
       """Short description of the function.

       Longer description with more details about what the function does,
       its purpose, and any important implementation notes.

       Args:
           param1: Description of the first parameter.
           param2: Description of the second parameter with default value.

       Returns:
           Description of the return value.

       Raises:
           ValueError: Description of when this exception is raised.
           TypeError: Description of when this exception is raised.

       Example:
           >>> result = example_function("test", 20)
           >>> print(result)
           True
       """
       return True
   ```

2. **Type hints are required:**
   ```python
   from typing import List, Dict, Optional, Union

   def process_data(
       items: List[str],
       config: Dict[str, Any],
       timeout: Optional[float] = None
   ) -> Union[str, None]:
       """Process data with configuration."""
       pass
   ```

3. **Class documentation:**
   ```python
   class ExampleClass:
       """Brief description of the class.

       Detailed description of what the class does, its purpose,
       and how it fits into the larger system.

       Attributes:
           attribute1: Description of the first attribute.
           attribute2: Description of the second attribute.

       Example:
           >>> obj = ExampleClass()
           >>> obj.attribute1 = "value"
       """

       def __init__(self, param: str):
           """Initialize the class.

           Args:
               param: Description of the initialization parameter.
           """
           self.attribute1 = param
   ```

### User Guide Documentation

Write user-facing documentation in RST format:

```rst
Section Title
=============

Subsection
----------

This is a paragraph with **bold** and *italic* text.

Code blocks:

.. code-block:: python

   from goesvfi import example
   result = example.process()

Lists:

- Item 1
- Item 2
- Item 3

Notes and warnings:

.. note::
   This is an informational note.

.. warning::
   This is a warning about potential issues.

.. tip::
   This is a helpful tip for users.
```

### Cross-References

Link to other parts of the documentation:

```rst
See :doc:`installation` for setup instructions.
See :ref:`api-reference` for API details.
See :class:`goesvfi.pipeline.VfiWorker` for the main worker class.
See :func:`goesvfi.utils.config.get_output_dir` for configuration.
```

## Documentation Standards

### Style Guide

1. **Tone**: Professional but approachable
2. **Audience**: Assume users have basic Python knowledge
3. **Examples**: Always include practical examples
4. **Completeness**: Document all public APIs
5. **Accuracy**: Keep documentation in sync with code

### Required Sections

Every module should document:

- **Purpose**: What the module does
- **Key Classes/Functions**: Main entry points
- **Examples**: Basic usage patterns
- **Error Handling**: Common exceptions
- **Configuration**: Relevant settings

### Quality Checks

Before submitting documentation:

1. **Build without warnings:**
   ```bash
   make clean && make html
   ```

2. **Check links:**
   ```bash
   make check
   ```

3. **Test examples:**
   ```bash
   python -m doctest docs/examples/*.py
   ```

4. **Review coverage:**
   ```bash
   python scripts/generate_docs.py --coverage
   ```

## Deployment

Documentation is automatically built and deployed via CI/CD:

- **Development**: Builds on every push to `main`
- **Production**: Published to GitHub Pages or Read the Docs
- **Versioning**: Tagged releases get versioned documentation

## Contributing

1. **Fork and clone** the repository
2. **Create a branch** for your documentation changes
3. **Write/update** documentation following the style guide
4. **Test locally** with `make html`
5. **Submit a pull request** with clear description

### Documentation-Only Changes

For documentation-only changes, prefix your commit message with `docs:`:

```bash
git commit -m "docs: add installation troubleshooting section"
```

## Troubleshooting

### Common Issues

**"Module not found" errors during build:**
```bash
# Make sure GOES_VFI modules are importable
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
cd docs && make html
```

**"Sphinx not found" error:**
```bash
pip install -r docs/requirements.txt
```

**Broken internal links:**
```bash
# Check for broken references
make check
```

**LaTeX/PDF build errors:**
```bash
# Install LaTeX (for PDF output)
# macOS: brew install --cask mactex
# Ubuntu: sudo apt-get install texlive-latex-recommended
```

### Getting Help

- **Sphinx Documentation**: https://www.sphinx-doc.org/
- **reStructuredText Guide**: https://docutils.sourceforge.io/rst.html
- **GitHub Issues**: https://github.com/username/GOES_VFI/issues

## License

Documentation is licensed under the same MIT license as the main project.
