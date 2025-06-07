# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a minimal Python project called "ezra" that currently contains a simple "Hello World" style application. The project uses modern Python packaging with pyproject.toml and requires Python 3.12+.

## Development Commands

- **Run the application**: `uv run python main.py`
- **Install dependencies**: `uv sync` (when dependencies are added to pyproject.toml)
- **Add dependencies**: `uv add <package-name>`
- **Create virtual environment**: `uv venv` (if not already created)

## Project Structure

- `main.py` - Entry point with a simple main() function
- `pyproject.toml` - Project configuration and dependencies
- `README.md` - Currently empty project documentation

## Notes

- Use `uv` for all Python package management operations
- Dependencies should be managed through pyproject.toml, not requirements.txt
- The project is in early development stage with minimal functionality