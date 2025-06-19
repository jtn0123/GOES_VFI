# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD  ?= sphinx-build
SOURCEDIR    = .
BUILDDIR     = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Custom targets for common operations
clean:
	@echo "Cleaning build directory..."
	rm -rf $(BUILDDIR)/*

livehtml:
	@echo "Starting live reload server..."
	sphinx-autobuild -b html --watch ../ --ignore "*/.*" --ignore "*/__pycache__/*" $(SOURCEDIR) $(BUILDDIR)/html

install-deps:
	@echo "Installing documentation dependencies..."
	pip install -r requirements.txt

check:
	@echo "Checking documentation for errors..."
	$(SPHINXBUILD) -b linkcheck $(SOURCEDIR) $(BUILDDIR)/linkcheck
	$(SPHINXBUILD) -b html -W --keep-going $(SOURCEDIR) $(BUILDDIR)/html

serve:
	@echo "Starting simple HTTP server..."
	cd $(BUILDDIR)/html && python -m http.server 8000

# Build all formats
all: html pdf epub

pdf:
	@echo "Building PDF documentation..."
	$(SPHINXBUILD) -b latex $(SOURCEDIR) $(BUILDDIR)/latex
	cd $(BUILDDIR)/latex && make all-pdf

epub:
	@echo "Building EPUB documentation..."
	$(SPHINXBUILD) -b epub $(SOURCEDIR) $(BUILDDIR)/epub
