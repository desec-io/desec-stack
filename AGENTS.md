## desec-stack agent notes

### Structure
- `api/`: Django REST API and celery worker code.
- `www/webapp/`: Vue/Vite frontend.
- `www/`: nginx configs and static site.
- `docker-compose.yml`: main stack definition.

### Common tasks
- API tests (fast local):
  - `docker compose -f docker-compose.yml -f docker-compose.test-api.yml up -d dbapi`
  - `cd api`
  - `export DJANGO_SETTINGS_MODULE=api.settings_quick_test`
  - `python3 manage.py test`
- API formatting:
  - `ruff format api/desecapi/`
- Webapp dev/build:
  - `cd www/webapp`
  - `npm install`
  - `npm run dev` (hot reload)
  - `npm run build`
  - `npm run lint`

### Notes
- Prefer running API tests outside docker with the test DB container.
- Keep changes in `api/` formatted with Ruff before committing.
- e2e2 tests can intermittently hit a 504 on `POST /api/v1/domains/` during startup; a clean `docker compose ... down -v` and rerun resolved it.
