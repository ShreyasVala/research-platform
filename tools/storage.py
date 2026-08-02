from __future__ import annotations

from pathlib import Path
from config import get_settings

settings = get_settings()


def safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None

    name = Path(filename).name
    if name != filename or name in {"", ".", ".."}:
        return None
    return name


def storage_backend() -> str:
    return settings.storage_backend.lower()


def _s3_client():
    import boto3
    return boto3.client("s3", region_name=settings.aws_region)


def _s3_key(folder: str, filename: str) -> str:
    prefix = settings.s3_prefix.strip("/")
    key = f"{folder.strip('/')}/{filename}"
    return f"{prefix}/{key}" if prefix else key


def save_upload_bytes(filename: str, content: bytes) -> dict:
    name = safe_filename(filename)
    if name is None:
        raise ValueError("Invalid filename.")

    if storage_backend() == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3.")

        key = _s3_key("uploads", name)
        _s3_client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
        )
        return {
            "filename": name,
            "size_kb": round(len(content) / 1024, 1),
            "storage": "s3",
            "location": f"s3://{settings.s3_bucket}/{key}",
        }

    uploads_root = Path(settings.uploads_dir).resolve()
    uploads_root.mkdir(parents=True, exist_ok=True)
    dest = (uploads_root / name).resolve()
    if dest.parent != uploads_root:
        raise ValueError("Invalid filename.")

    dest.write_bytes(content)
    return {
        "filename": name,
        "size_kb": round(dest.stat().st_size / 1024, 1),
        "storage": "local",
        "location": str(dest),
    }


def read_upload_bytes(filename: str) -> tuple[bytes | None, str | None]:
    name = safe_filename(filename)
    if name is None:
        return None, f"Invalid filename: {filename}"

    if storage_backend() == "s3":
        if not settings.s3_bucket:
            return None, "S3_BUCKET is required when STORAGE_BACKEND=s3."

        key = _s3_key("uploads", name)
        try:
            response = _s3_client().get_object(
                Bucket=settings.s3_bucket,
                Key=key,
            )
            return response["Body"].read(), None
        except Exception as e:
            return None, f"File not found in S3: {name} ({e})"

    uploads_root = Path(settings.uploads_dir).resolve()
    path = (uploads_root / name).resolve()
    if path.parent != uploads_root:
        return None, f"Invalid filename: {filename}"
    if not path.exists():
        return None, f"File not found: {name}"

    return path.read_bytes(), None


def list_uploads() -> list[dict]:
    if storage_backend() == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3.")

        prefix = _s3_key("uploads", "")
        response = _s3_client().list_objects_v2(
            Bucket=settings.s3_bucket,
            Prefix=prefix,
            MaxKeys=100,
        )
        return [
            {
                "name": item["Key"].removeprefix(prefix),
                "size_kb": round(item["Size"] / 1024, 1),
                "type": Path(item["Key"]).suffix,
            }
            for item in response.get("Contents", [])
            if item["Key"] != prefix
        ]

    uploads_root = Path(settings.uploads_dir).resolve()
    if not uploads_root.exists():
        return []
    return [
        {
            "name": path.name,
            "size_kb": round(path.stat().st_size / 1024, 1),
            "type": path.suffix,
        }
        for path in uploads_root.iterdir()
        if path.is_file()
    ]


def save_report_text(job_id: str, query: str, report: str) -> str:
    safe_job_id = safe_filename(job_id)
    if safe_job_id is None:
        raise ValueError("Invalid job ID.")
    filename = f"report_{safe_job_id}.txt"
    content = f"Query: {query}\n\n{report}".encode("utf-8")

    if storage_backend() == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3.")

        key = _s3_key("reports", filename)
        _s3_client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
            ContentType="text/plain; charset=utf-8",
        )
        return f"s3://{settings.s3_bucket}/{key}"

    reports_root = Path(settings.reports_dir).resolve()
    reports_root.mkdir(parents=True, exist_ok=True)
    path = (reports_root / filename).resolve()
    path.write_bytes(content)
    return str(path)
