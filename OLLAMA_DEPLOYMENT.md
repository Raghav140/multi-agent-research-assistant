# Ollama Production Deployment Guide

## Overview

Ollama is deployed as an internal Docker service within the application network. The browser never communicates directly with Ollama - all requests go through the FastAPI backend.

## Architecture

```
User
 ↓
nginx (port 80/443)
 ↓
FastAPI (port 8000)
 ↓
Ollama (port 11434, internal network only)
 ↓
qwen3:4b model
```

## Security

- **Browser**: Cannot access Ollama directly (no exposed endpoint)
- **FastAPI**: Accesses Ollama via internal Docker network (`http://ollama:11434`)
- **Ollama**: Only accessible within Docker network (`app-network`)
- **Port 11434**: Not exposed to host machine - internal network only

## Docker Compose Configuration

### Ollama Service

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: multi-agent-ollama
  volumes:
    - ollama_models:/root/.ollama
    - ./docker/ollama-entrypoint.sh:/entrypoint.sh:ro
  networks:
    - app-network
  restart: unless-stopped
  entrypoint: ["/bin/bash", "/entrypoint.sh"]
  healthcheck:
    test: ["CMD", "ollama", "list"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 300s
```

### Backend Service

```yaml
backend:
  environment:
    - OLLAMA_HOST=http://ollama:11434
  depends_on:
    ollama:
      condition: service_healthy
  networks:
    - app-network
```

## Model Setup

### Automatic Initialization

The Ollama service uses an entrypoint script that automatically:
1. Starts the Ollama server
2. Waits for it to become ready (up to 5 minutes)
3. Checks if the `qwen3:4b` model exists
4. Pulls the model automatically if it is missing

No manual model pull is required for normal deployment. The model download occurs on first startup if the persistent volume is empty.

### Verify Model

To check if the model is available:

```bash
docker exec multi-agent-ollama ollama list
```

Expected output:
```
NAME          ID              SIZE      MODIFIED
qwen3:4b      abc123...        2.3 GB    2024-08-23
```

## Environment Variables

### Backend Configuration

```bash
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT=120
OLLAMA_DISABLE_REASONING=true
OLLAMA_STREAM=false
```

## Deployment Options

### Option 1: Docker Compose (Recommended)

**Use Case**: Private/team deployment with Docker

**Steps**:
1. Update `docker-compose.yml` with Ollama service
2. Set `OLLAMA_HOST=http://ollama:11434` in backend environment
3. Run `docker-compose up -d`

The entrypoint script will automatically pull `qwen3:4b` on first startup if the model is missing.

**Advantages**:
- Self-contained deployment
- Persistent model storage
- Automatic model initialization
- Healthcheck integration
- Network isolation

### Option 2: External Ollama Server

**Use Case**: Shared Ollama server across multiple applications

**Steps**:
1. Deploy Ollama on separate server
2. Configure firewall to allow only backend server access
3. Set `OLLAMA_HOST=http://your-ollama-server:11434`
4. Pull model on external server

**Advantages**:
- Shared resource across applications
- Centralized model management
- Separate scaling

### Option 3: Docker Desktop with Host Ollama

**Use Case**: Local development with Docker Desktop

**Steps**:
1. Install Ollama on host machine
2. Set `OLLAMA_HOST=http://host.docker.internal:11434`
3. Pull model on host: `ollama pull qwen3:4b`

**Advantages**:
- No additional container
- Uses host GPU
- Simpler for local development

## GPU Support

To enable GPU acceleration, uncomment the GPU configuration in `docker-compose.yml`:

```yaml
ollama:
  # ... other config
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

**Requirements**:
- NVIDIA GPU
- NVIDIA Container Toolkit
- nvidia-docker2

## Verification

### Check Ollama Health

Since port 11434 is not exposed to the host, verify Ollama status from within the container:

```bash
docker exec multi-agent-ollama ollama list
```

### Check Backend Connectivity

```bash
curl http://localhost:8000/api/v1/system/providers/health
```

Expected response includes Ollama provider status.

### Test Research Workflow

```bash
curl -X POST http://localhost:8000/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What is artificial intelligence?"}'
```

## Troubleshooting

### Ollama Not Responding

**Symptoms**: Backend reports Ollama connection errors

**Solutions**:
1. Check Ollama container status: `docker ps | grep ollama`
2. Check Ollama logs: `docker logs multi-agent-ollama`
3. Verify network: `docker network inspect app-network`
4. Test connectivity: `docker exec multi-agent-backend curl http://ollama:11434/api/tags`

### Model Not Found

**Symptoms**: Backend reports model not found

**Solutions**:
1. List models: `docker exec multi-agent-ollama ollama list`
2. If model is missing, restart the Ollama container to trigger automatic pull:
   ```bash
   docker-compose restart ollama
   ```
3. For manual diagnostics, you can pull directly: `docker exec multi-agent-ollama ollama pull qwen3:4b`
4. Check model name in `.env` matches the expected model name

### GPU Not Working

**Symptoms**: Slow inference, CPU usage high

**Solutions**:
1. Verify NVIDIA driver: `nvidia-smi`
2. Check NVIDIA Container Toolkit: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`
3. Ensure GPU configuration uncommented in `docker-compose.yml`

## Production Considerations

### Resource Requirements

**CPU**: 4+ cores recommended
**RAM**: 8GB+ recommended (16GB+ for multiple concurrent requests)
**Storage**: 10GB+ for model storage
**GPU**: Optional but recommended for production

### Scaling

**Horizontal Scaling**: Not recommended for Ollama (single instance per deployment)
**Vertical Scaling**: Increase CPU/RAM/GPU resources as needed

### Monitoring

Monitor Ollama metrics:
- Request latency
- Token generation speed
- Memory usage
- GPU utilization (if available)

## Security Notes

- Ollama port 11434 is NOT exposed to public internet in recommended architecture
- Backend is the only service that can access Ollama
- Browser cannot communicate directly with Ollama
- Use firewall rules to restrict Ollama access if using external server
