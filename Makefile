# ==============================================================================
# ZERMP ENTERPRISE AUTOMATION MAKEFILE (VRIDHI FINANCIAL SERVICES)
# ==============================================================================

.PHONY: help up down restart logs ps clean test lint scan quality-gate ci

help:
	@echo "Available commands:"
	@echo "  make up           - Build and start all infrastructure containers"
	@echo "  make down         - Stop and tear down all platform containers"
	@echo "  make restart      - Restart the API application container"
	@echo "  make ps           - View status and healthchecks of all services"
	@echo "  make logs         - Stream real-time logs from API container"
	@echo "  make test         - Execute pytest suite inside container"
	@echo "  make quality-gate - Run all unit and integration test suites"
	@echo "  make ci           - Execute complete local CI verification pipeline"

up:
	docker compose --project-directory . -f infra/docker-compose.yml --env-file .env up -d --build

down:
	docker compose --project-directory . -f infra/docker-compose.yml --env-file .env down

restart:
	docker restart zermp-api

ps:
	docker compose --project-directory . -f infra/docker-compose.yml --env-file .env ps

logs:
	docker logs -f zermp-api

test:
	docker exec -it zermp-api pytest tests/

quality-gate:
	docker exec -it zermp-api pytest tests/ -v
	docker exec -it zermp-api python scripts/verify_module1.py
	docker exec -it zermp-api python scripts/verify_module2.py
	docker exec -it zermp-api python scripts/verify_module3.py

ci: quality-gate
	@echo "\n[✓] All enterprise quality gates passed successfully."
