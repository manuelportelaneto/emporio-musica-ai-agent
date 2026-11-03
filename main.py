#!/usr/bin/env python3
"""Empório da Música - Single Root Entrypoint.

Starts the 3-Stage Evaluator CLI, which allows branching directly into
either the Terminal Interactive Console or the Streamlit Web Application.
"""

import sys
from src.cli import run_cli

if __name__ == "__main__":
    run_cli()
