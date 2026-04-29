#!/usr/bin/env bash
# One-shot init script: waits for the Ollama service to be ready, then pulls
# the embedding model required by the RAG pipeline.
#
# Usage (docker-compose):
#   Run as an `init` container (restart: "no") that depends_on: ollama.
#   The OLLAMA_HOST env var is injected by docker-compose (default: ollama:11434).
#
# Models pulled:
#   nomic-embed-text  — 768-dimensional text embeddings
#                       Must match EMBED_DIM=768 in backend Settings and the
#                       pgvector column dimension.  Changing the model requires
#                       a new Alembic migration to ALTER the vector column size.
#
# Why a separate init container rather than entrypoint of the ollama service:
#   The official ollama image's entrypoint starts the server and exits. An
#   extra init container (restart: "no") separates the server-start concern
#   from the model-pull concern, making the compose graph cleaner.

set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-ollama:11434}"
BASE_URL="http://${OLLAMA_HOST}"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo "Waiting for Ollama at ${BASE_URL} …"
for i in $(seq 1 "${MAX_RETRIES}"); do
  if curl --silent --fail "${BASE_URL}/api/tags" > /dev/null 2>&1; then
    echo "Ollama is ready."
    break
  fi
  if [ "${i}" -eq "${MAX_RETRIES}" ]; then
    echo "ERROR: Ollama did not become ready after ${MAX_RETRIES} attempts." >&2
    exit 1
  fi
  echo "  attempt ${i}/${MAX_RETRIES} — retrying in ${RETRY_INTERVAL}s"
  sleep "${RETRY_INTERVAL}"
done

echo "Pulling nomic-embed-text …"
curl --silent --fail --request POST \
  "${BASE_URL}/api/pull" \
  --header "Content-Type: application/json" \
  --data '{"name": "nomic-embed-text", "stream": false}'

echo "Model pull complete."
