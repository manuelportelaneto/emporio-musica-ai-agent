@echo off
REM ==============================================================================
REM Empório da Música - Unified Evaluator Launcher (Windows)
REM Automatically detects virtual environment (.venv) and launches main.py
REM ==============================================================================

setlocal enabledelayedexpansion

REM Set UTF-8 encoding for Windows console
chcp 65001 >nul
set PYTHONUTF8=1

cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    SET "PYTHON_BIN=.venv\Scripts\python.exe"
) ELSE IF EXIST "venv\Scripts\python.exe" (
    SET "PYTHON_BIN=venv\Scripts\python.exe"
) ELSE (
    SET "PYTHON_BIN=python"
)

"%PYTHON_BIN%" main.py %*

