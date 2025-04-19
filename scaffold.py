#!/usr/bin/env python3
"""Scaffold generator for the GOES‑VFI project (v0.1)

Run this once inside an empty folder:
    python scaffold.py

It creates the directory tree and placeholder files discussed in the
project outline.  Existing files are never overwritten (safe writes).
"""
from __future__ import annotations
import os, pathlib, sys, textwrap, datetime

TREE = {
    "models": [
        ("README.md", "# models\nDrop ONNX or NCNN weights here.  For v0.1 we ship IFRNet‑S fp16.\n"),
    ],
    "goesvfi": {
        "__init__.py": "__version__ = '0.1.0'\n",
        "version.py": "VERSION = '0.1.0'\n",
        "gui.py": "# TODO: PyQt6 main window implementation\n",
        "cli.py": "# TODO: CLI entry‑point implementation\n",
        "pipeline": {
            "__init__.py": "# Pipeline subpackage\n",
            "loader.py": "# TODO: discover + sort input frames\n",
            "tiler.py": "# TODO: split/merge with overlap\n",
            "interpolate.py": "# TODO: IFRNet‑S via ONNX Runtime (CoreML/DirectML)\n",
            "encoder.py": "# TODO: FFmpeg H.265 writer\n",
            "cache.py": "# TODO: simple SHA‑256 → .npy cache\n",
        },
        "utils": {
            "__init__.py": "# Utils\n",
            "config.py": "# TODO: path + TOML config\n",
            "log.py": "# TODO: colorlog wrapper\n",
        },
        "resources": {},
    },
    "tests": {
        "__init__.py": "",
        "test_placeholder.py": "def test_placeholder():\n    assert True\n",
    },
    "docs": {
        "README.md": "# GOES‑VFI Docs\n",
        "FUTURE_TODO.md": textwrap.dedent(
            """\
            ### Short‑term\n            - [ ] CUDA Execution Provider (Linux & Windows, NVIDIA)\n            - [ ] Intel Arc: onnxruntime oneAPI EP\n\n            ### Medium‑term\n            - [ ] AV1 export via libaom or SVT‑AV1\n            - [ ] 10‑bit processing pipeline\n            - [ ] Batch job queue + parallel worker pool\n\n            ### Long‑term\n            - [ ] PyInstaller/Briefcase packaging\n            - [ ] Full SatDump plugin integration\n            """
        ),
    },
    "README.md": "# GOES‑VFI – v0.1\n\nSee docs/README.md for quick‑start.\n",
    "pyproject.toml": textwrap.dedent(
        """\
        [project]\n        name = "goesvfi"\n        version = "0.1.0"\n        description = "GOES satellite frame interpolation tool"\n        dependencies = [\n            "PyQt6",\n            "onnxruntime",\n            "numpy",\n            "Pillow",\n            "opencv-python-headless",\n            "ffmpeg-python",\n            "colorlog",\n            ]\n        readme = "README.md"\n        requires-python = ">=3.11"\n\n        [project.scripts]\n        goesvfi = "goesvfi.cli:main"\n        """
    ),
    ".github": {
        "workflows": {
            "ci.yml": textwrap.dedent(
                """\
                name: CI\n                on: [push, pull_request]\n                jobs:\n                  test:\n                    runs-on: macos-14\n                    steps:\n                      - uses: actions/checkout@v4\n                      - name: Setup Python\n                        uses: actions/setup-python@v5\n                        with:\n                          python-version: '3.11'\n                      - name: Install deps\n                        run: |\n                          python -m pip install -e .[gui] pytest\n                      - name: Tests\n                        run: pytest -q\n                """
            )
        }
    }
}


def safe_write(path: pathlib.Path, content: str):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf‑8")
    print("created", path)


def create_tree(base: pathlib.Path, spec):
    if isinstance(spec, str):
        safe_write(base, spec)
    elif isinstance(spec, list):
        # tuple list for files
        for name, content in spec:
            safe_write(base / name, content)
    elif isinstance(spec, dict):
        for name, subtree in spec.items():
            create_tree(base / name, subtree)
    else:
        raise TypeError("unknown spec type")


def main():
    root = pathlib.Path.cwd()
    print("Scaffolding GOES‑VFI project in", root)
    create_tree(root, TREE)
    print("\nDone!  Next: create a venv, pip install -e .[gui], and run gui:\n    python -m goesvfi.gui\n")


if __name__ == "__main__":
    main()
