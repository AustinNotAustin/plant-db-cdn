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
PORT = int(get_env_or_raise("PORT"))
S3_INBOX = "s3_inbox"               # Equivalent to the Landing S3 Bucket
S3_QUARANTINE = "s3_quarantine"     # Temporary processing zone (Simulates Lambda ephemeral disk)
S3_LONGTERM = "s3_longterm"         # Equivalent to the Production Storage/CDN S3 Bucket

CALLBACK_URL = get_env_or_raise("CALLBACK_URL")
CALLBACK_SECRET = get_env_or_raise("CALLBACK_SECRET")
BASE_URL = get_env_or_raise("BASE_URL")

# --- CDN Image Subdirectories (within S3_LONGTERM) ---
CDN_FULL_IMGS = os.path.join(S3_LONGTERM, "full-imgs")       # Full-resolution images
CDN_THUMB_IMGS = os.path.join(S3_LONGTERM, "thumb-imgs")     # Thumbnail images
CDN_SALES_IMGS = os.path.join(S3_LONGTERM, "sales-imgs")     # Sales/promotional images
CDN_PROFILE_PICS = os.path.join(S3_LONGTERM, "profile-pics") # User profile pictures
CDN_COMPANY_LOGOS = os.path.join(S3_LONGTERM, "company-logos") # Company logos

# Ensure physical directory structure for the tiering system
for d in [S3_INBOX, S3_QUARANTINE, CDN_FULL_IMGS, CDN_THUMB_IMGS, CDN_SALES_IMGS, CDN_PROFILE_PICS, CDN_COMPANY_LOGOS]:
    os.makedirs(d, exist_ok=True)
