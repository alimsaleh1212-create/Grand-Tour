#!/bin/sh
# Seed all application secrets into Vault KV v2 at secret/travel-planner.
# Called by the vault-init one-shot container. Idempotent — kv put overwrites.
# All values come from env vars injected by docker-compose via env_file: .env
set -e

export VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-dev-root-token}"

echo "Enabling KV v2 at 'secret/'..."
# exits 2 if already enabled — treat as success
vault secrets enable -version=2 -path=secret kv 2>/dev/null || true

echo "Writing secrets to secret/travel-planner..."
vault kv put secret/travel-planner \
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  JWT_SECRET="${JWT_SECRET}" \
  GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
  LANGSMITH_API_KEY="${LANGSMITH_API_KEY:-}" \
  LANGCHAIN_API_KEY="${LANGCHAIN_API_KEY:-}" \
  DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}" \
  SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}" \
  AMADEUS_API_KEY="${AMADEUS_API_KEY:-}" \
  AMADEUS_API_SECRET="${AMADEUS_API_SECRET:-}" \
  PGADMIN_PASSWORD="${PGADMIN_PASSWORD:-adminpassword}"

echo "Seeding complete. Stored keys:"
vault kv get -format=json secret/travel-planner | grep -E '"[A-Z_]+":'
