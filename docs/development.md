# Development Guide

## Setup

1. Create virtual environment:
```bash
uv venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Unix
```

2. Install dependencies:
```bash
uv pip install -e ".[dev]"
```

3. Set up environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Running the Application

Development:
```bash
uvicorn backend.core.main:app --reload
```

Production:
```bash
uvicorn backend.core.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Testing

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=backend --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_api.py
```

## Code Quality

Format code:
```bash
black .
```

Lint code:
```bash
ruff check .
```

Fix linting issues:
```bash
ruff check --fix .
```

Type checking:
```bash
mypy backend/
```

## Pre-commit Hooks

Install pre-commit hooks:
```bash
pre-commit install
```

Run manually:
```bash
pre-commit run --all-files
```

## Adding New Features

1. Create feature branch
2. Implement feature following SOLID principles
3. Add type hints
4. Write tests
5. Run pre-commit hooks
6. Submit PR

## Code Style

- Follow PEP 8
- Use type hints everywhere
- Keep functions focused and small
- Write docstrings for all public functions
- Use async/await for I/O operations
