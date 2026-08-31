"""Environment-driven configuration for ingestion. No hardcoded credentials,
see .env.example and docs/architecture/05-security.md."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"

    snowflake_account: str
    snowflake_warehouse: str = "DELIVERY_WH"
    snowflake_database: str

    snowflake_loader_user: str
    snowflake_loader_password: str
    snowflake_loader_role: str = "LOADER_ROLE"

    aws_region: str = "ap-southeast-2"
    s3_landing_bucket: str

    @property
    def stage_ref(self) -> str:
        return f"{self.snowflake_database}.RAW.LANDING_STAGE"


# One place every ingestion entrypoint pulls settings from. Built lazily
# rather than at import time, so tests can construct IngestionSettings
# directly with their own values instead of needing a real .env.
def load_settings() -> IngestionSettings:
    return IngestionSettings()


# Which RAW table each source loads into, and the column order its CSV files
# carry (the four technical metadata columns aren't listed here, see
# snowflake/02_bronze_tables.sql). Adding a new source is a new entry here
# plus a Source implementation; the loader itself doesn't change.
SOURCE_COLUMNS: dict[str, list[str]] = {
    "restaurants": ["_idx", "id", "name", "city", "rating", "rating_count", "cost", "cuisine", "lic_no", "link", "address", "menu"],
    "users": ["_idx", "user_id", "name", "email", "password", "age", "gender", "marital_status", "occupation", "monthly_income", "education", "family_size"],
    "food": ["_idx", "f_id", "item", "veg_or_non_veg"],
    "menu": ["_idx", "menu_id", "r_id", "f_id", "cuisine", "price"],
    "orders": ["order_id", "order_timestamp", "order_date", "user_id", "r_id", "restaurant_city", "cuisine", "items_count", "sales_qty", "subtotal", "discount", "delivery_fee", "gst", "sales_amount", "currency", "payment_method", "order_status", "customer_rating", "delivery_time_min"],
    "order_items": ["order_item_id", "order_id", "r_id", "f_id", "price", "quantity", "line_amount"],
    "reviews": ["review_id", "order_id", "user_id", "restaurant_id", "rating", "comment", "review_date"],
}
