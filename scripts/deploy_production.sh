#!/usr/bin/env bash
#
# Production CPU control-plane deploy, executed on the VPS by the deploy
# workflow. The order is fixed: backup -> migrate -> release -> health check,
# and a failed health check rolls the application back to the previous image.
#
# Required environment:
#   DEPLOY_DIR       compose project directory on the server
#   API_IMAGE        fully qualified api image to release (immutable sha tag)
#   GPU_IMAGE        fully qualified gpu worker image published for this release
# Optional:
#   BACKUP_DIR       defaults to $DEPLOY_DIR/backups
#   HEALTH_RETRIES   defaults to 30 (1s apart)

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:?DEPLOY_DIR is required}"
API_IMAGE="${API_IMAGE:?API_IMAGE is required}"
GPU_IMAGE="${GPU_IMAGE:?GPU_IMAGE is required}"
BACKUP_DIR="${BACKUP_DIR:-$DEPLOY_DIR/backups}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"

COMPOSE=(docker compose -f compose.production.yml --env-file .env)

cd "$DEPLOY_DIR"

# shellcheck disable=SC1091
set -a
source .env
set +a

PREVIOUS_API_IMAGE="$("${COMPOSE[@]}" images --quiet api 2>/dev/null || true)"
echo "[deploy] previous api image: ${PREVIOUS_API_IMAGE:-<none>}"

# 1. Backup before any schema change so a bad migration stays recoverable.
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/pre-deploy-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
echo "[deploy] backing up database to $BACKUP_FILE"
"${COMPOSE[@]}" exec -T postgres \
    pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    | gzip > "$BACKUP_FILE"

# 2. Pull the immutable images for this release.
echo "[deploy] pulling $API_IMAGE"
docker pull "$API_IMAGE"
echo "[deploy] pulling $GPU_IMAGE"
docker pull "$GPU_IMAGE"

# 3. Forward-only migration. Destructive upgrades are rejected in CI, so the
#    previous image keeps working against the new schema during a rollback.
echo "[deploy] running alembic upgrade head"
API_IMAGE="$API_IMAGE" "${COMPOSE[@]}" run --rm --no-deps --no-build api alembic upgrade head

# 4. Release the new image.
echo "[deploy] releasing api"
API_IMAGE="$API_IMAGE" "${COMPOSE[@]}" up --detach --no-build api

rollback() {
    echo "[deploy] health check failed; rolling back application" >&2
    if [[ -n "$PREVIOUS_API_IMAGE" ]]; then
        API_IMAGE="$PREVIOUS_API_IMAGE" "${COMPOSE[@]}" up --detach --no-build api
        echo "[deploy] rolled back to $PREVIOUS_API_IMAGE" >&2
    else
        echo "[deploy] no previous image recorded; manual intervention required" >&2
    fi
    echo "[deploy] database backup kept at $BACKUP_FILE" >&2
    exit 1
}

# 5. Health check the released control plane.
echo "[deploy] waiting for /health/ready"
for _ in $(seq 1 "$HEALTH_RETRIES"); do
    if curl --fail --silent --show-error \
        "http://127.0.0.1:${API_PORT:-8000}/health/ready" >/dev/null 2>&1; then
        echo "[deploy] release healthy: $API_IMAGE"
        exit 0
    fi
    sleep 1
done

rollback
