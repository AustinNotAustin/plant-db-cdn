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
S3_INBOX = "s3_inbox"               # Equivalent to the Landing S3 Bucket
S3_QUARANTINE = "s3_quarantine"     # Temporary processing zone (Simulates Lambda ephemeral disk)
S3_LONGTERM = "s3_longterm"         # Equivalent to the Production Storage/CDN S3 Bucket

SRV_CDN_URL = get_env_or_raise("SRV_CDN_URL")

# Ensure physical directory structure for the tiering system
for d in [S3_INBOX, S3_QUARANTINE, S3_LONGTERM]:
    os.makedirs(d, exist_ok=True)
