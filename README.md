# Multi-Agent Research Assistant

A production-ready AI-powered research assistant built with FastAPI, featuring multiple autonomous agents for comprehensive research tasks.

## Features

- **Multi-Agent Architecture**: Specialized agents for different research tasks
- **FastAPI Backend**: High-performance async Python web framework
- **Clean Architecture**: SOLID principles and clean code practices
- **Type Safety**: Full type hints with mypy support
- **Production Ready**: Docker support, logging, and configuration management

## Tech Stack

- **Python**: 3.10.11
- **Web Framework**: FastAPI
- **Package Manager**: uv
- **Linting**: Ruff
- **Formatting**: Black
- **Testing**: Pytest
- **Containerization**: Docker & Docker Compose

## Project Structure

```
multi-agent-research-assistant/
├── backend/
│   ├── agents/          # AI agent implementations
│   ├── api/             # API endpoints and routes
│   ├── config/          # Application configuration and main entry point
│   ├── database/        # Database models and connections
│   ├── models/          # Pydantic models
│   ├── rag/             # Retrieval-Augmented Generation
│   ├── services/        # External service integrations
│   ├── tools/           # Utility tools and functions
│   └── utils/           # Common utilities
├── frontend/            # Frontend application
├── tests/               # Test suite
├── docs/                # Documentation
└── docker/              # Docker configurations
```

## Getting Started

### Prerequisites

- Python 3.10.11 or higher
- uv package manager
- Docker (optional, for containerized deployment)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd multi-agent-research-assistant
```

2. Create virtual environment with uv:
```bash
uv venv
.venv\Scripts\activate  # On Windows
source .venv/bin/activate  # On Unix
```

3. Install dependencies:
```bash
uv pip install -e ".[dev]"
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the application:
```bash
uvicorn backend.config.main:app --reload
```

### Development

#### Running Tests
```bash
pytest
```

#### Code Formatting
```bash
black .
```

#### Linting
```bash
ruff check .
```

#### Type Checking
```bash
mypy backend/
```

### Docker Deployment

Build and run with Docker Compose:
```bash
docker-compose up --build
```

## Configuration

Configuration is managed through environment variables. See `.env.example` for available options.

## Architecture

This project follows Clean Architecture principles:

- **Domain Layer**: Core business logic and entities
- **Application Layer**: Use cases and application services
- **Infrastructure Layer**: External services, database, and API
- **Presentation Layer**: API endpoints and request/response handling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

[Your License Here]
