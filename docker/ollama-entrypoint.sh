#!/bin/bash
set -e

MODEL_NAME="qwen3:4b"
MAX_WAIT_SECONDS=300  # 5 minutes maximum wait for Ollama startup
WAIT_INTERVAL=2     # Check every 2 seconds
OLLAMA_PORT=11434

echo "Starting Ollama server in background..."
ollama serve &
SERVE_PID=$!

# Trap signals to clean up background process
trap 'echo "Received shutdown signal, terminating Ollama server..."; kill $SERVE_PID 2>/dev/null; exit 0' TERM INT

echo "Waiting for Ollama server to become ready (max ${MAX_WAIT_SECONDS}s)..."

# Wait for Ollama to be ready with timeout
# Use TCP port check followed by CLI command for robustness
elapsed=0
while [ $elapsed -lt $MAX_WAIT_SECONDS ]; do
  # First check if the TCP port is listening using bash /dev/tcp
  if (echo > /dev/tcp/127.0.0.1/$OLLAMA_PORT) >/dev/null 2>&1; then
    # Port is open, now verify the API is actually responding via CLI
    if ollama list > /dev/null 2>&1; then
      echo "Ollama server is ready and responding."
      break
    fi
  fi
  sleep $WAIT_INTERVAL
  elapsed=$((elapsed + WAIT_INTERVAL))
done

# Check if we timed out
if [ $elapsed -ge $MAX_WAIT_SECONDS ]; then
  echo "ERROR: Ollama server did not become ready within ${MAX_WAIT_SECONDS}s"
  kill $SERVE_PID 2>/dev/null
  exit 1
fi

echo "Checking if model $MODEL_NAME exists..."

# Check if model exists
if ollama list | grep -q "$MODEL_NAME"; then
  echo "Model $MODEL_NAME already exists. Skipping download."
else
  echo "Model $MODEL_NAME not found. Pulling model..."
  if ollama pull "$MODEL_NAME"; then
    echo "Model $MODEL_NAME pulled successfully."
  else
    echo "ERROR: Failed to pull model $MODEL_NAME"
    kill $SERVE_PID 2>/dev/null
    exit 1
  fi
fi

echo "Ollama server ready with model $MODEL_NAME loaded."
echo "Waiting for Ollama server process (PID $SERVE_PID)..."

# Wait for the background server (this keeps the container running)
wait $SERVE_PID
