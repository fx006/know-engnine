.PHONY: dev api test worker smoke docker-build docker-up docker-down

dev:
	uv run fastapi dev know_engine_py/app/main.py

api:
	uv run uvicorn know_engine_py.app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest know_engine_py/tests -q

worker:
	uv run celery -A know_engine_py.app.tasks.celery_app.celery_app worker -l info

smoke:
	uv run python -c "from know_engine_py.app.main import app; from know_engine_py.app.core.settings import get_settings; from know_engine_py.app.tasks.celery_app import celery_app; s=get_settings(); print({'app': s.app_name, 'env': s.environment, 'routes': len(app.routes), 'celery_broker': celery_app.conf.broker_url})"

docker-build:
	docker compose build

docker-up:
	docker compose up --build api worker

docker-down:
	docker compose down
