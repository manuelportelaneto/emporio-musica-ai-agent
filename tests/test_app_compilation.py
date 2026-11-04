"""Integrity and Syntax Test: Ensures app.py and all entry points compile cleanly."""

import ast
import glob
import os
import py_compile
import pytest


def test_app_py_syntax_and_compilation():
    """Verify that app.py has zero SyntaxError or IndentationError."""
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
    assert os.path.exists(app_path), "app.py must exist in repository root"

    with open(app_path, "r", encoding="utf-8") as f:
        source = f.read()

    # 1. AST Parse validation
    tree = ast.parse(source, filename="app.py")
    assert tree is not None

    # 2. Bytecode compilation validation
    compiled = py_compile.compile(app_path, doraise=True)
    assert compiled is not None


def test_all_project_python_files_compile():
    """CI/CD Gold Standard: Ensure every python file across src, scripts and tests compiles cleanly."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py_files = (
        glob.glob(os.path.join(root_dir, "src", "**", "*.py"), recursive=True)
        + glob.glob(os.path.join(root_dir, "scripts", "**", "*.py"), recursive=True)
        + glob.glob(os.path.join(root_dir, "tests", "**", "*.py"), recursive=True)
        + [os.path.join(root_dir, "app.py")]
    )

    for py_file in py_files:
        assert os.path.exists(py_file)
        with open(py_file, "r", encoding="utf-8") as f:
            code = f.read()
        parsed = ast.parse(code, filename=py_file)
        assert parsed is not None, f"Failed to parse AST for {py_file}"
        py_compile.compile(py_file, doraise=True)

