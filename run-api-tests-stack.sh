#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose -f ${ROOT_DIR}/docker-compose.yml -f ${ROOT_DIR}/docker-compose.test-api.yml"
BUILD_IMAGES_STACK=(api dbapi nslord nsmaster dblord dbmaster)
BUILD_IMAGES_DB=(dbapi)
KEEP=0
BUILD=1
MODE="host"

usage() {
  cat <<'EOF'
Usage: ./run-api-tests-stack.sh [--no-build] [--keep] [--docker]
  --no-build  Skip docker image build step
  --keep      Do not tear down containers/volumes after tests
  --docker    Run API tests inside the api container (CI-style)
EOF
}

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    --keep) KEEP=1 ;;
    --docker) MODE="docker" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage; exit 1 ;;
  esac
done

cleanup() {
  $COMPOSE ps || true
  $COMPOSE down -v || true
}

if [[ "$KEEP" -eq 0 ]]; then
  trap cleanup EXIT
fi

if [[ "$MODE" == "docker" ]]; then
  if [[ "$BUILD" -eq 1 ]]; then
    $COMPOSE build "${BUILD_IMAGES_STACK[@]}"
  fi
  $COMPOSE run --rm api bash -c "./entrypoint-tests.sh"
else
  if [[ "$BUILD" -eq 1 ]]; then
    $COMPOSE build "${BUILD_IMAGES_DB[@]}"
  fi
  $COMPOSE up -d dbapi
  (
    set -a
    source "${ROOT_DIR}/.env"
    set +a
    export DJANGO_SETTINGS_MODULE=api.settings_quick_test
    export DESECSTACK_DJANGO_TEST=1
    cd "${ROOT_DIR}/api"
    if [[ -x "./venv/bin/python" ]]; then
      # Use project venv when present.
      source "./venv/bin/activate"
    else
      echo "Missing venv at ${ROOT_DIR}/api/venv. Create it with: cd api && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt" >&2
      exit 1
    fi
    # Avoid local psql dependency by checking readiness inside the DB container.
    wait_seconds=10
    start_ts=$(date +%s)
    while true; do
      if $COMPOSE exec -T dbapi sh -c "command -v pg_isready >/dev/null 2>&1" >/dev/null 2>&1; then
        if $COMPOSE exec -T dbapi pg_isready -U "${DESECSTACK_DBAPI_USER:-desec}" -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
          break
        fi
      else
        if $COMPOSE exec -T dbapi sh -c "PGPASSWORD='${DESECSTACK_DBAPI_PASSWORD_desec:-}' psql -U '${DESECSTACK_DBAPI_USER:-desec}' -h 127.0.0.1 -p 5432 -d postgres -c 'select 1' >/dev/null 2>&1"; then
          break
        fi
      fi

      now_ts=$(date +%s)
      if (( now_ts - start_ts > wait_seconds )); then
        echo "Timed out waiting for Postgres to become ready."
        $COMPOSE ps
        $COMPOSE logs --tail 80 dbapi || true
        exit 1
      fi
      echo "Postgres is unavailable - sleeping"
      sleep 2
    done
    python3 manage.py test
  )
fi
