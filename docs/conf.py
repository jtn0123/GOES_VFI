"""Sphinx configuration file for GOES_VFI documentation."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path so Sphinx can import modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# -- Project information -----------------------------------------------------
project = "GOES_VFI"
copyright = "2024, GOES_VFI Contributors"
author = "GOES_VFI Contributors"

# The full version, including alpha/beta/rc tags
release = "1.0.0"
version = "1.0.0"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.githubpages",
    "myst_parser",  # For Markdown support
]

# Add any paths that contain templates here, relative to this directory
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The suffix(es) of source filenames
source_suffix = {
    ".rst": None,
    ".md": None,
}

# The master toctree document
master_doc = "index"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages
html_theme = "sphinx_rtd_theme"

# Theme options are theme-specific and customize the look and feel of a theme
html_theme_options = {
    "canonical_url": "",
    "analytics_id": "",
    "logo_only": False,
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
    "vcs_pageview_mode": "",
    "style_nav_header_background": "#2980B9",
    # Toc options
    "collapse_navigation": True,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Custom sidebar templates, must be a dictionary that maps document names
# to template names
html_sidebars = {
    "**": [
        "relations.html",  # needs 'show_related': True theme option to display
        "searchbox.html",
    ]
}

# -- Options for autodoc ----------------------------------------------------

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Mock imports for modules that aren't available during documentation building
autodoc_mock_imports = [
    "PyQt6",
    "numpy",
    "PIL",
    "cv2",
    "ffmpeg",
    "psutil",
    "aiohttp",
    "aioboto3",
    "botocore",
    "xarray",
    "netCDF4",
    "matplotlib",
    "aiofiles",
    "imageio",
]

# -- Options for napoleon (Google/NumPy style docstrings) -------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- Options for intersphinx ------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pillow": ("https://pillow.readthedocs.io/en/stable/", None),
}

# -- Options for todo extension ---------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Options for autosummary ------------------------------------------------

autosummary_generate = True
autosummary_imported_members = True

# -- Custom configuration ---------------------------------------------------


# Add custom CSS
def setup(app):
    """Custom setup function for Sphinx."""
    app.add_css_file("custom.css")


# Suppress warnings for missing references in docstrings
suppress_warnings = ["ref.any"]

# Enable numbered figures
numfig = True

# -- Options for LaTeX output -----------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    "papersize": "letterpaper",
    # The font size ('10pt', '11pt' or '12pt').
    "pointsize": "10pt",
    # Additional stuff for the LaTeX preamble.
    "preamble": "",
    # Latex figure (float) alignment
    "figure_align": "htbp",
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "GOES_VFI.tex",
        "GOES VFI Documentation",
        "GOES_VFI Contributors",
        "manual",
    ),
]

# -- Options for manual page output -----------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "goes_vfi", "GOES VFI Documentation", [author], 1)]

# -- Options for Texinfo output ---------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "GOES_VFI",
        "GOES VFI Documentation",
        author,
        "GOES_VFI",
        "GOES satellite data processing and video frame interpolation.",
        "Miscellaneous",
    ),
]

# -- Options for Epub output ------------------------------------------------

# Bibliographic Dublin Core info.
epub_title = project
epub_author = author
epub_publisher = author
epub_copyright = copyright

# A list of files that should not be packed into the epub file.
epub_exclude_files = ["search.html"]
