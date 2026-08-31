.PHONY: help setup lint test dbt-deps dbt-parse dbt-compile dbt-build dbt-test airflow-up airflow-down rag text-to-sql

help:
	@echo "make setup          - create venv and install all Python deps"
	@echo "make lint           - ruff lint + sqlfluff lint dbt models"
	@echo "make test           - run Python unit tests"
	@echo "make dbt-deps       - install dbt packages"
	@echo "make dbt-parse      - dbt parse (fast, no warehouse work)"
	@echo "make dbt-compile    - dbt compile"
	@echo "make dbt-build      - dbt build (staging + marts + semantic, excludes AI models)"
	@echo "make dbt-test       - dbt test only"
	@echo "make airflow-up     - start local Airflow via docker compose"
	@echo "make airflow-down   - stop local Airflow"
	@echo "make rag            - run the RAG chat Streamlit app"
	@echo "make text-to-sql    - run the text-to-SQL Streamlit app"

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt

lint:
	ruff check ingestion ai tests airflow
	sqlfluff lint dbt/delivery_pipeline/models

test:
	pytest tests/python -v

dbt-deps:
	dbt deps --project-dir dbt/delivery_pipeline --profiles-dir dbt/delivery_pipeline/profiles

dbt-parse:
	dbt parse --project-dir dbt/delivery_pipeline --profiles-dir dbt/delivery_pipeline/profiles

dbt-compile:
	dbt compile --project-dir dbt/delivery_pipeline --profiles-dir dbt/delivery_pipeline/profiles

dbt-build:
	dbt build --exclude tag:ai --project-dir dbt/delivery_pipeline --profiles-dir dbt/delivery_pipeline/profiles

dbt-test:
	dbt test --project-dir dbt/delivery_pipeline --profiles-dir dbt/delivery_pipeline/profiles

airflow-up:
	cd docker/airflow && docker compose up -d --build

airflow-down:
	cd docker/airflow && docker compose down

rag:
	streamlit run ai/apps/rag_chat_app.py

text-to-sql:
	streamlit run ai/apps/text_to_sql_app.py
