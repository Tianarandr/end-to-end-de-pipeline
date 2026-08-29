# Airflow 3.x + Snowflake/FAB providers + the ingestion/ai layer's runtime deps
# (installed directly, for PythonOperator tasks) + dbt in its own isolated venv
# (for BashOperator tasks — see ADR-002 and airflow/dags/delivery_pipeline_dag.py).
FROM apache/airflow:3.0.3

COPY docker/airflow/requirements-airflow-app.txt /tmp/requirements-airflow-app.txt
RUN pip install --no-cache-dir \
      apache-airflow-providers-snowflake \
      apache-airflow-providers-fab \
      -r /tmp/requirements-airflow-app.txt

COPY requirements-dbt.txt /tmp/requirements-dbt.txt
RUN python -m venv /opt/airflow/.dbt_venv && \
    /opt/airflow/.dbt_venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt
