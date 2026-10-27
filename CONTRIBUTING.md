# Contributing to News Pebbles

Thank you for your interest in contributing to **News Pebbles**! We welcome contributions to our newspaper generation engine, craft rules, web reader, and educational tooling.

## Getting Started

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/devendr-ai/teen-newspaper-builder.git
   cd teen-newspaper-builder
   ```

2. Set up a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run the test suite:
   ```bash
   python -m pytest -q
   ```

## Development Guidelines

- **Craft Rules**: Any changes to prompts or content guidelines must adhere to [`docs/CRAFT_RULES.md`](docs/CRAFT_RULES.md).
- **Measurement-First Layout**: Always use `ygc.measure` to ensure content does not overflow ReportLab frames.
- **Backwards Compatibility**: Existing editions must continue rendering pixel-identically.
- **Code Style**: Keep code clean, typed where helpful, and tested.

## Submitting Pull Requests

1. Create a feature branch (`git checkout -b feature/my-new-feature`).
2. Run `python -m pytest -q` to make sure all tests pass.
3. Commit with clear, descriptive commit messages.
4. Push to your fork and submit a Pull Request.

## Reporting Bugs & Suggesting Features

Please use our GitHub Issues tab or email corrections to `corrections@newspebbles.com`.
