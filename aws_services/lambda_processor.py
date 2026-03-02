import asyncio
import httpx
import logging
import os
import shutil
from PIL import Image

from .config import S3_QUARANTINE, S3_LONGTERM, CALLBACK_URL, CALLBACK_SECRET

logger = logging.getLogger(__name__)

async def scan_malware(file_path: str) -> bool:
    logger.info(f"[Security] Scanning {os.path.basename(file_path)}...")
    await asyncio.sleep(0.1)
    return True

async def scan_content_policy(file_path: str) -> bool:
    logger.info(f"[Policy] Verifying content policy...")
    await asyncio.sleep(0.1)
    return True

async def s3_trigger_handler(inbox_path: str, upload_id: str, plant_id: str):
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

        # 4. PROMOTION: Quarantine -> Long-Term
        logger.info(f"[S3] Promoting variants to {S3_LONGTERM}")
        shutil.move(os.path.join(S3_QUARANTINE, thumb_filename), os.path.join(S3_LONGTERM, thumb_filename))
        shutil.move(os.path.join(S3_QUARANTINE, large_filename), os.path.join(S3_LONGTERM, large_filename))

        # Cleanup original
        if os.path.exists(quarantine_path):
            os.remove(quarantine_path)

        # 5. ASYNC CALLBACK (Notify Backend)
        payload = {
            "upload_id": upload_id,
            "plant_id": plant_id,
            "status": "success",
            "full_url": large_filename,
            "thumbnail_url": thumb_filename
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
