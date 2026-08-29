"""Connection factory scoped to LOADER_ROLE. See docs/architecture/05-security.md.
The ingestion process never authenticates with a broader role, even though one
would technically work; the credentials it's given (SNOWFLAKE_LOADER_*) are
provisioned with LOADER_ROLE as their only grant."""
from __future__ import annotations

import snowflake.connector
from ingestion.config import IngestionSettings
from snowflake.connector import SnowflakeConnection


def get_loader_connection(settings: IngestionSettings) -> SnowflakeConnection:
    return snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_loader_user,
        password=settings.snowflake_loader_password,
        role=settings.snowflake_loader_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema="RAW",
    )
