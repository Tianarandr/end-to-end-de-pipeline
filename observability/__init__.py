"""Cross-cutting observability: the PIPELINE_RUNS control table writer used
by the Airflow DAG's `publish` stage and its DAG-level failure callback. See
docs/architecture/06-observability.md.

Lives as its own small top-level package rather than under airflow/, because
a package literally named `airflow.callables` would collide with the
installed `apache-airflow` package's own `airflow` namespace the moment
anything tried `from airflow import DAG`. Keeping it at repo root sidesteps
that problem.
"""
