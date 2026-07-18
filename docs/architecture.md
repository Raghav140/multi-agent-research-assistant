# Architecture Documentation

## Overview

The multi-agent research assistant follows Clean Architecture principles with clear separation of concerns.

## Layer Structure

### Presentation Layer (backend/api/)
- FastAPI routes and endpoints
- Request/response handling
- API versioning

### Application Layer (backend/core/)
- Business logic orchestration
- Configuration management
- Dependency injection

### Domain Layer (backend/agents/, backend/models/)
- Domain entities and models
- Agent base classes
- Business rules

### Infrastructure Layer (backend/database/, backend/services/, backend/tools/)
- External service integrations
- Database connections
- Utility tools

## Key Components

### Agents
- Base agent class for all AI agents
- Specialized agents for different research tasks

### RAG (Retrieval-Augmented Generation)
- Vector database integration
- Semantic search capabilities
- Document chunking and indexing

### Services
- OpenAI API integration
- External API clients
- Caching layer

### Tools
- Web search functionality
- Data processing utilities
- File handling

## Data Flow

1. API receives request
2. Request validated against Pydantic models
3. Appropriate agent selected based on task
4. Agent uses tools and services to execute task
5. Results returned through API

## Async Architecture

All I/O operations use async/await pattern:
- Database queries
- External API calls
- File operations
- Agent execution
