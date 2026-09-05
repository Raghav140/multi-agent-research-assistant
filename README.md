# Multi-Agent Research Assistant

A production-ready AI-powered research assistant built with FastAPI and React, featuring multi-agent architecture for comprehensive research tasks.

## Features

- **Multi-Agent Architecture**: Specialized agents for planning, research, and report generation
- **LangGraph Workflow**: Orchestration of research pipeline with state management
- **Multi-Source Retrieval**: DuckDuckGo, Wikipedia, arXiv, and Documentation providers
- **Circuit Breaker Pattern**: Fault tolerance for external provider failures
- **Provider Health Monitoring**: Real-time tracking of provider performance
- **Adaptive Provider Selection**: Intelligent provider selection based on query type
- **Caching Layer**: LRU cache for embeddings, retrieval results, and memory lookups
- **Research Memory**: Storage and retrieval of previous research for context reuse
- **Evaluation Metrics**: Tracking of retrieval quality, answer quality, and system performance
- **Modern React Frontend**: TypeScript, Vite, Tailwind CSS, and shadcn/ui components
- **Real-time Progress**: Live research experience with status updates
- **System Health Dashboard**: Provider status and analytics visualization

## Tech Stack

### Backend
- **Python**: 3.10.11
- **Web Framework**: FastAPI
- **Workflow**: LangGraph
- **LLM Provider**: Ollama
- **Search Providers**: DuckDuckGo, Wikipedia, arXiv, Documentation
- **Package Manager**: uv
- **Linting**: Ruff
- **Formatting**: Black
- **Testing**: Pytest
- **Containerization**: Docker & Docker Compose

### Frontend
- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS v4
- **Components**: Custom components with Lucide icons
- **State Management**: React hooks
- **HTTP Client**: Fetch API with typed responses
- **Routing**: Client-side navigation
- **Markdown**: react-markdown with remark-gfm

## Project Structure

```
multi-agent-research-assistant/
├── backend/
│   ├── agents/          # AI agent implementations
│   ├── api/             # API endpoints and routes
│   ├── config/          # Application configuration and dependency injection
│   ├── core/            # Interfaces, exceptions, middleware
│   ├── database/        # Database models and connections
│   ├── graph/           # LangGraph workflow and nodes
│   ├── memory/          # Research memory management
│   ├── models/          # Pydantic models and schemas
│   ├── providers/       # External providers (LLM, search, papers)
│   ├── rag/             # Retrieval-Augmented Generation
│   ├── services/        # Retrieval engine and external services
│   └── utils/           # Cache, evaluation, logging, embeddings
├── frontend/           # React + TypeScript frontend
│   ├── src/
│   │   ├── components/  # Reusable UI components
│   │   ├── lib/         # API client and utilities
│   │   ├── pages/       # Page components
│   │   └── types/       # TypeScript type definitions
├── tests/               # Test suite
└── docker/              # Docker configurations
```

## Getting Started

### Prerequisites

- Python 3.10.11 or higher
- Node.js 18+ (for frontend)
- uv package manager
- Docker (optional, for containerized deployment)
- Ollama (for LLM provider)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd multi-agent-research-assistant
```

2. Backend setup:
```bash
# Create virtual environment with uv
uv venv
.venv\Scripts\activate  # On Windows
source .venv/bin/activate  # On Unix

# Install dependencies
uv pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

3. Frontend setup:
```bash
cd frontend
npm install
cd ..
```

4. Configure frontend environment (optional):
```bash
cd frontend
echo "VITE_API_BASE_URL=http://127.0.0.1:8000" > .env.local
cd ..
```

5. Start Ollama (if not running):
```bash
ollama serve
```

### Running the Application

#### Development Mode

**Backend (development with reload):**
```bash
python -m uvicorn backend.config.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend (development):**
```bash
cd frontend
npm run dev
```

**Both (recommended - separate terminals):**
```bash
# Terminal 1: Backend
python -m uvicorn backend.config.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Access the application at http://localhost:5173

**Development characteristics:**
- `APP_ENV=development`
- `APP_DEBUG=true` (API docs available at `/docs`)
- Hot reload enabled
- Local SQLite databases
- Local Ollama connection

#### Production Mode

**Backend (production without reload):**
```bash
python -m uvicorn backend.config.main:app --host 0.0.0.0 --port 8000
```

**Production characteristics:**
- `APP_ENV=production`
- `APP_DEBUG=false` (API docs disabled)
- No hot reload
- Docker volume SQLite databases (`/app/data`)
- Internal Ollama connection

**Recommended worker count:** 1 worker

**Reasoning:** The current architecture uses:
- In-memory LRU cache (per-worker)
- SQLite databases (write-heavy)
- Circuit breaker state (per-worker)
- Provider health state (per-worker)
- Research memory (SQLite-based)

Multiple workers would create isolated cache and state instances, reducing cache effectiveness and potentially causing inconsistent circuit breaker behavior. A single worker is recommended for correctness and reliability in this architecture.

#### Docker Deployment

**Using Docker Compose:**
```bash
docker-compose up -d
```

**Healthcheck endpoint:** `http://localhost:8000/api/v1/system/health`

**Process management:** Docker Compose restart policy (`restart: unless-stopped`)

**Shutdown/restart:** Docker Compose handles process lifecycle automatically

#### Production Frontend Deployment

**Production frontend build:**
```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=/api" > .env.local  # For same-domain deployment
npm run build
```

**Serving with nginx:**
```bash
# Copy nginx.conf.example to your nginx configuration directory
# Update the root path to point to frontend/dist
# Update server_name to your domain
# Restart nginx
```

**Same-domain architecture:**
```
https://your-domain.example/
    → React frontend (served by nginx)

https://your-domain.example/api/
    → nginx proxy
    → FastAPI localhost:8000
```

**Production API URL:**
- For same-domain deployment: `VITE_API_BASE_URL=/api`
- For cross-domain deployment: `VITE_API_BASE_URL=https://api.your-domain.example`

**What users do NOT need:**
- Python (backend runs on server)
- Node.js (frontend is pre-built)
- Ollama (runs on server)
- Model files (managed by server)
- Provider API keys (managed by server)

**Important**: `VITE_*` variables are exposed to the browser - never put secrets in them.

### Development

#### Running Backend Tests
```bash
pytest
```

#### Running Frontend Build
```bash
cd frontend
npm run build
```

#### Running Frontend Lint
```bash
cd frontend
npm run lint
```

#### Code Formatting
```bash
black backend/
```

#### Linting
```bash
ruff check backend/
```

### Docker Deployment

The application uses Docker Compose for containerized deployment with the following architecture:

- **Backend**: FastAPI application with uvicorn
- **Frontend**: React static files (served by nginx)
- **Storage**: SQLite databases for research memory and metrics (persistent volumes)
- **Cache**: In-memory LRU cache (per worker)
- **Ollama**: Internal Docker service (included in Docker Compose)

Build and run with Docker Compose:
```bash
docker-compose up --build
```

The Docker Compose configuration includes:
- Backend service with FastAPI
- Ollama service for LLM inference
- Persistent volumes for databases and models
- Healthchecks for both services
- Internal network for service communication

**Ollama Deployment**:
- Ollama runs as an internal Docker service
- Backend accesses Ollama via internal network (`http://ollama:11434`)
- Browser cannot access Ollama directly (security)
- Model storage is persistent via Docker volume
- See `OLLAMA_DEPLOYMENT.md` for detailed setup instructions

**Model Setup**:
After starting containers, pull the required model:
```bash
docker exec -it multi-agent-ollama ollama pull qwen3:4b
```

### Backup & Recovery

**What Must Be Backed Up**:
- **Research Memory Database**: `/app/data/research_memory.db` (Docker volume: `app_data`)
- **Evaluation Metrics Database**: `/app/data/evaluation_metrics.db` (Docker volume: `app_data`)
- **Ollama Models**: `/root/.ollama` (Docker volume: `ollama_models`)

**What Does Not Need Backup**:
- **In-Memory Cache**: LRU cache (recreated automatically on restart)
- **Circuit Breaker State**: Circuit breaker state (recreated automatically on restart)
- **Provider Health State**: Provider health metrics (recreated automatically on restart)
- **Logs**: Application logs (optional backup for debugging)

**Backup Strategy**:

**SQLite Databases**:
- Use SQLite online backup (`.backup` command) for consistency
- Backup script provided: `scripts/backup_sqlite.sh`
- Manual backup command (inside container):
  ```bash
  sqlite3 /app/data/research_memory.db ".backup /backups/research_memory_$(date +%Y%m%d_%H%M%S).db"
  sqlite3 /app/data/evaluation_metrics.db ".backup /backups/evaluation_metrics_$(date +%Y%m%d_%H%M%S).db"
  ```
- Recommended frequency: Daily
- Recommended retention: 7 days

**Ollama Models**:
- Volume persistence is sufficient (Docker volume: `ollama_models`)
- Re-pull is acceptable if volume is lost: `docker exec -it multi-agent-ollama ollama pull qwen3:4b`
- Model backup not necessary (models can be re-downloaded from Ollama registry)

**Recovery Procedures**:

**Scenario A: Backend Container Restart**
- **Survives Automatically**: SQLite databases, Ollama models (Docker volumes)
- **Recreated Automatically**: In-memory cache, circuit breaker state, provider health state
- **Action**: None required

**Scenario B: Backend Container Deleted/Recreated**
- **Survives Automatically**: SQLite databases, Ollama models (Docker volumes)
- **Recreated Automatically**: In-memory cache, circuit breaker state, provider health state
- **Action**: `docker-compose up -d backend`

**Scenario C: Server Restart**
- **Survives Automatically**: SQLite databases, Ollama models (Docker volumes)
- **Recreated Automatically**: In-memory cache, circuit breaker state, provider health state
- **Action**: `docker-compose up -d`

**Scenario D: SQLite Database Corrupted/Lost**
- **Survives Automatically**: Ollama models
- **Must Be Restored**: SQLite databases from backup
- **Action**:
  ```bash
  docker cp /path/to/backup/research_memory_YYYYMMDD_HHMMSS.db multi-agent-backend:/app/data/research_memory.db
  docker cp /path/to/backup/evaluation_metrics_YYYYMMDD_HHMMSS.db multi-agent-backend:/app/data/evaluation_metrics.db
  docker-compose restart backend
  ```

**Scenario E: Ollama Container Deleted**
- **Survives Automatically**: SQLite databases
- **Must Be Restored**: Ollama models (re-pull)
- **Action**:
  ```bash
  docker-compose up -d ollama
  docker exec -it multi-agent-ollama ollama pull qwen3:4b
  ```

**Scenario F: Entire Docker Host Lost**
- **Survives Automatically**: Nothing
- **Must Be Restored**: SQLite databases from off-site backup, Ollama models (re-pull)
- **Action**:
  1. Restore from off-site backup
  2. Deploy application
  3. Pull Ollama model: `docker exec -it multi-agent-ollama ollama pull qwen3:4b`

**Disaster Recovery Limitations**:
- No automated off-site backup (requires manual configuration)
- No database replication (single point of failure)
- No high availability (single server deployment)
- Recommended for private/team deployment only

## Configuration

Configuration is managed through environment variables. See `.env.example` for all available options.

### Development vs Production

**Development Environment:**
- `APP_ENV=development`
- `APP_DEBUG=true` (enables API docs, detailed error messages)
- `CORS_ORIGINS` includes localhost/127.0.0.1 frontend ports
- `OLLAMA_HOST=http://127.0.0.1:11434` (local Ollama)
- SQLite databases in current directory (`./research_memory.db`, `./evaluation_metrics.db`)

**Production Environment:**
- `APP_ENV=production`
- `APP_DEBUG=false` (disables API docs, reduces error detail)
- `CORS_ORIGINS` set to production domain only
- `OLLAMA_HOST` configured for deployment (host.docker.internal or internal service)
- SQLite databases in `/app/data/` (Docker volume)

### Backend Variables

**Application:**
- `APP_NAME`: Application name (default: multi-agent-research-assistant)
- `APP_VERSION`: Application version (default: 0.1.0)
- `APP_ENV`: Application environment (development/production)
- `APP_DEBUG`: Enable debug mode (default: true for development, false for production)

**Server:**
- `SERVER_HOST`: Server host address (default: 0.0.0.0)
- `SERVER_PORT`: Server port (default: 8000)
- `SERVER_WORKERS`: Number of worker processes (default: 4)

**Logging:**
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FORMAT`: Log output format (json or text)

**SQLite Database Paths:**
- `RESEARCH_MEMORY_DB_PATH`: Path to research memory database
  - Development: `./research_memory.db`
  - Production: `/app/data/research_memory.db`
- `EVALUATION_METRICS_DB_PATH`: Path to evaluation metrics database
  - Development: `./evaluation_metrics.db`
  - Production: `/app/data/evaluation_metrics.db`

**Ollama (Local LLM):**
- `OLLAMA_HOST`: Ollama server host URL
  - Development: `http://127.0.0.1:11434`
  - Docker Desktop: `http://host.docker.internal:11434`
  - Docker Compose: `http://ollama:11434`
- `OLLAMA_MODEL`: Ollama model name (default: qwen3:4b)
- `OLLAMA_TIMEOUT`: Request timeout in seconds (default: 120)
- `OLLAMA_DISABLE_REASONING`: Disable reasoning mode for Qwen3 (default: true)
- `OLLAMA_STREAM`: Enable streaming responses (default: false)
- `OLLAMA_REPORT_TEMPERATURE`: Temperature for report generation (default: 0.3)
- `OLLAMA_REPORT_MAX_TOKENS`: Max tokens for report generation (default: 384)
- `OLLAMA_REPORT_TIMEOUT`: Timeout for report generation (default: 60)

**Security:**
- `SECRET_KEY`: Secret key for JWT token signing (if authentication is added)
- `CORS_ORIGINS`: Allowed CORS origins (JSON array of URLs)
  - Development: `["http://localhost:5173","http://localhost:5174","http://127.0.0.1:5173","http://127.0.0.1:5174"]`
  - Production: `["https://your-domain.example"]`

### Frontend Variables

- `VITE_API_BASE_URL`: Backend API endpoint
  - Development: `http://127.0.0.1:8000`
  - Production: `https://api.your-domain.example`
  - Set in `frontend/.env.local`
  - Can also be configured via Settings page in the UI

**Important**:
- Production frontend builds must receive the production API URL at build time via `VITE_API_BASE_URL`
- `VITE_*` variables are exposed to the browser - never put secrets in them
- The browser never directly accesses Ollama or provider services - only the backend does

### Deployment Architecture

**Development Flow:**
```
Browser → Vite Dev Server → FastAPI → Local Ollama (127.0.0.1:11434)
```

**Private Production Flow:**
```
Browser → nginx/HTTPS → FastAPI → Internal Ollama (host.docker.internal:11434 or internal service)
```

**Security Notes:**
- Browser does not need Ollama credentials
- Browser does not need provider API keys
- Only server-side services access Ollama and external providers
- CORS restricts which domains can access the API

## Architecture

### Backend Architecture

The backend follows Clean Architecture principles:

- **Domain Layer**: Core business logic and entities
- **Application Layer**: Use cases and application services
- **Infrastructure Layer**: External services, database, and API
- **Presentation Layer**: API endpoints and request/response handling

**Workflow Pipeline:**
1. **Planner Node**: Analyzes query and creates research plan
2. **Research Node**: Multi-provider retrieval with circuit breaker protection
3. **Report Node**: Synthesizes findings into comprehensive report

**Key Components:**
- **RetrievalEngine**: Centralized orchestration of all providers
- **CircuitBreaker**: Fault tolerance for external provider failures
- **ProviderHealthMonitor**: Real-time provider performance tracking
- **ProviderSelector**: Adaptive provider selection based on query type
- **LRUCache**: Caching for embeddings, retrieval results, and memory
- **MemoryManager**: Research memory storage and retrieval
- **RetrievalEvaluator**: Metrics tracking for quality assessment

### Frontend Architecture

The frontend uses a modern React architecture:

- **Component-Based**: Reusable UI components with TypeScript
- **API Client**: Typed HTTP client for backend communication
- **Page Components**: Route-based page components
- **Utility Functions**: Helper functions for formatting and styling

**Pages:**
- **Dashboard**: Overview with statistics and recent research
- **Research**: Main research query interface with live progress
- **History**: Research history and memory
- **Health**: System and provider health monitoring
- **Settings**: Application configuration

## API Endpoints

- `POST /api/v1/research` - Execute research workflow
- `GET /api/v1/system/health` - System health status
- `GET /api/v1/system/providers/health` - Provider health status
- `GET /api/v1/system/metrics/summary` - Research metrics summary
- `GET /api/v1/system/cache/stats` - Cache statistics
- `GET /api/v1/system/memory/history` - Research memory history

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

[Your License Here]
