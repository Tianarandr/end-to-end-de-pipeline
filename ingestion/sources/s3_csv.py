"""CSV-on-S3 source, the ingestion pattern this project runs today.

Files are expected under `s3://<bucket>/raw/<source_name>/*.csv`, matching
the Snowflake external stage configured in snowflake/00_setup.sql.
"""
from __future__ import annotations

import boto3

from ingestion.models import FileRef
from ingestion.sources.base import Source


class S3CsvSource(Source):
    def __init__(self, name: str, bucket: str, region: str) -> None:
        self.name = name
        self.bucket = bucket
        self.prefix = f"raw/{name}/"
        self._s3 = boto3.client("s3", region_name=region)

    def list_new_files(self) -> list[FileRef]:
        paginator = self._s3.get_paginator("list_objects_v2")
        files: list[FileRef] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue  # directory marker object, not a real file
                relative_path = key[len(self.prefix):]
                files.append(FileRef(key=key, relative_path=relative_path, size_bytes=obj.get("Size")))
        return files

    def stage_ref(self, database: str) -> str:
        return f"@{database}.RAW.LANDING_STAGE/{self.name}/"
