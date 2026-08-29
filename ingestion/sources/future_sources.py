"""Sketches, not implementations. They just show that `Source` supports
these without any change to loader.py. Left unimplemented for now: building
them would be speculative code for a need this project doesn't have yet
(the repo's "no code for hypothetical requirements" principle). Wire one of
these up for real the day an actual API or CDC source shows up.

class ApiPullSource(Source):
    '''Pulls a paginated API response, writes it to
    s3://<bucket>/raw/<name>/<run_id>.jsonl before list_new_files() ever
    runs. So the API-pull step still lands in S3 first (ADR-004), just with
    a different producer than a manual CSV drop.'''
    ...

class DatabaseExtractSource(Source):
    '''Runs a SELECT (full extract or CDC-log-based incremental extract)
    against a source database, writes the result to S3 as Parquet, and
    returns FileRefs the same way S3CsvSource does. A CDC-based version
    would carry a high-watermark cursor instead of listing all objects.'''
    ...
"""
