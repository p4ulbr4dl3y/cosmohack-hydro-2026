.PHONY: help install run eval eval-quick predict test docker docker-down fetch

# Default target
help:
	@echo "HydroWatch Amur — Команды проекта:"
	@echo "  make install      - Синхронизировать окружение через uv"
	@echo "  make run          - Запустить геосервис и дашборд (порт 8000)"
	@echo "  make eval         - Официальная соревновательная метрика + 4 абляции"
	@echo "  make eval-quick   - Быстрый расчет метрики"
	@echo "  make predict      - Полный инференс всех пар (submission.csv + растры)"
	@echo "  make test         - Запуск набора тестов"
	@echo "  make docker       - Сборка и запуск в Docker Compose"
	@echo "  make docker-down  - Остановка Docker Compose"
	@echo "  make fetch        - Загрузка исходных радарных сцен с облака"

install:
	uv sync

run:
	uv run uvicorn src.service.app:app --host 0.0.0.0 --port 8000

eval:
	uv run python -m src.cli evaluate --run-ablations

eval-quick:
	uv run python -m src.cli evaluate

predict:
	uv run python -m src.cli predict

test:
	uv run pytest

docker:
	docker compose up --build

docker-down:
	docker compose down

fetch:
	uv run python -m src.cli fetch
