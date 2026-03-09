import asyncio
import httpx
import logging
import os
import shutil
from PIL import Image

from .config import (
    S3_QUARANTINE, S3_LONGTERM,
    CDN_FULL_IMGS, CDN_THUMB_IMGS, CDN_SALES_IMGS, CDN_PROFILE_PICS, CDN_COMPANY_LOGOS,
    CALLBACK_URL, CALLBACK_SECRET,
)

# Maps image_category metadata values to their long-term storage directory
CATEGORY_DIR_MAP = {
    "sales":   CDN_SALES_IMGS,
    "profile": CDN_PROFILE_PICS,
    "logo":    CDN_COMPANY_LOGOS,
}

logger = logging.getLogger(__name__)

async def scan_malware(file_path: str) -> bool:
    logger.info(f"[Security] Scanning {os.path.basename(file_path)}...")
    await asyncio.sleep(0.1)
    return True

async def scan_content_policy(file_path: str) -> bool:
    logger.info(f"[Policy] Verifying content policy...")
    await asyncio.sleep(0.1)
    return True

async def s3_trigger_handler(inbox_path: str, upload_id: str, plant_id: str, image_category: str = "plant"):
    """
    Consumer function simulating an S3 Event -> SQS -> Lambda trigger.
    """
    file_name = os.path.basename(inbox_path)
    quarantine_path = os.path.join(S3_QUARANTINE, file_name)
    
    try:
        # 1. ATOMIC MOVE: Inbox -> Quarantine
        logger.info(f"[S3] Event received. Moving {file_name} to quarantine...")
        shutil.move(inbox_path, quarantine_path)

        # 2. RUN FULL SCAN SUITE
        await scan_malware(quarantine_path)
        await scan_content_policy(quarantine_path)
            
        # 3. IMAGE PROCESSING
        logger.info(f"[Processor] Generating variants (Thumb + Large)...")
        with Image.open(quarantine_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            thumb_filename = f"thumb_{upload_id}.jpg"
            large_filename = f"large_{upload_id}.jpg"

            # Generate variants
            thumb = img.copy()
            thumb.thumbnail((200, 200))
            thumb.save(os.path.join(S3_QUARANTINE, thumb_filename), "JPEG")

            large = img.copy()
            large.thumbnail((1200, 1200))
            large.save(os.path.join(S3_QUARANTINE, large_filename), "JPEG")

        # 4. PROMOTION: Quarantine -> Long-Term (category-specific subdirectory)
        # Category-specific uploads (sales, profile, logo) use their own directory;
        # default plant images are split into full-imgs and thumb-imgs.
        if image_category in CATEGORY_DIR_MAP:
            target_dir = CATEGORY_DIR_MAP[image_category]
            full_dest = os.path.join(target_dir, large_filename)
            thumb_dest = os.path.join(target_dir, thumb_filename)
        else:
            full_dest = os.path.join(CDN_FULL_IMGS, large_filename)
            thumb_dest = os.path.join(CDN_THUMB_IMGS, thumb_filename)

        logger.info(f"[S3] Promoting variants to {os.path.dirname(full_dest)}")
        shutil.move(os.path.join(S3_QUARANTINE, large_filename), full_dest)
        shutil.move(os.path.join(S3_QUARANTINE, thumb_filename), thumb_dest)

        # Cleanup original
        if os.path.exists(quarantine_path):
            os.remove(quarantine_path)

        # Derive relative CDN paths (relative to S3_LONGTERM root served at /cdn)
        # Use forward slashes to ensure URL compatibility across all platforms.
        full_cdn_path = os.path.relpath(full_dest, S3_LONGTERM).replace(os.sep, "/")
        thumb_cdn_path = os.path.relpath(thumb_dest, S3_LONGTERM).replace(os.sep, "/")

        # 5. ASYNC CALLBACK (Notify Backend)
        payload = {
            "upload_id": upload_id,
            "plant_id": plant_id,
            "status": "success",
            "full_url": full_cdn_path,
            "thumbnail_url": thumb_cdn_path,
        }
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {CALLBACK_SECRET}", 
                "Content-Type": "application/json",
                "Host": "app.localhost"
            }
            try:
                response = await client.post(CALLBACK_URL, json=payload, headers=headers, timeout=15.0)
                logger.info(f"[Callback] Backend response {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"[Callback] Network Error: {str(e)}")
            
            logger.info(f"[Lifecycle] Task {upload_id} completed successfully.")

    except Exception as e:
        logger.error(f"[Lifecycle] Task {upload_id} FAILED: {str(e)}")
        if os.path.exists(quarantine_path):
            os.remove(quarantine_path)
