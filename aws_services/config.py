import os

from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

def get_env_or_raise(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"CRITICAL: Environment variable '{key}' is missing. Application cannot start.")
    return value


# --- AWS PHYSICAL STORAGE TIERS (Simulated Buckets) ---
SRV_CDN_PORT = int(get_env_or_raise("SRV_CDN_PORT"))
SRV_CDN_URL = get_env_or_raise("SRV_CDN_URL")

S3_STORAGE_ROOT = os.getenv("S3_STORAGE_ROOT", "s3_buckets")
S3_DEFAULT_CDN_BUCKET = os.getenv("S3_DEFAULT_CDN_BUCKET", "s3_longterm")
S3_ENFORCE_PLANT_HIERARCHY = os.getenv("S3_ENFORCE_PLANT_HIERARCHY", "").lower() in {
    "1",
    "true",
    "yes",
}

# Legacy bucket names kept for Plant-DB compatibility.
S3_INBOX_BUCKET = os.getenv("S3_INBOX_BUCKET", "s3_inbox")
S3_QUARANTINE_BUCKET = os.getenv("S3_QUARANTINE_BUCKET", "s3_quarantine")
S3_LONGTERM_BUCKET = os.getenv("S3_LONGTERM_BUCKET", S3_DEFAULT_CDN_BUCKET)


def get_bucket_path(bucket_name: str) -> str:
    if not bucket_name or bucket_name in {".", ".."} or "/" in bucket_name or "\\" in bucket_name:
        raise ValueError("Invalid bucket name")

    root_path = os.path.abspath(S3_STORAGE_ROOT)
    bucket_path = os.path.abspath(os.path.join(root_path, bucket_name))
    if os.path.commonpath([root_path, bucket_path]) != root_path:
        raise ValueError("Invalid bucket path")
    return bucket_path


def get_object_path(bucket_name: str, key: str) -> str:
    bucket_path = get_bucket_path(bucket_name)
    object_path = os.path.abspath(os.path.join(bucket_path, key))
    if os.path.commonpath([bucket_path, object_path]) != bucket_path:
        raise ValueError("Invalid object key")
    return object_path


os.makedirs(S3_STORAGE_ROOT, exist_ok=True)
for bucket in [S3_INBOX_BUCKET, S3_QUARANTINE_BUCKET, S3_LONGTERM_BUCKET]:
    os.makedirs(get_bucket_path(bucket), exist_ok=True)
