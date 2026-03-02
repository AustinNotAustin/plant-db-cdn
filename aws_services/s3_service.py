import logging
import os
import shutil

from fastapi import BackgroundTasks, UploadFile, File, Form, Response, HTTPException

from .auth import verify_s3_signature, validate_policy_json
from .config import S3_INBOX
from .lambda_processor import s3_trigger_handler

logger = logging.getLogger(__name__)

# --- AWS S3 ENDPOINT ---

async def mock_s3_presigned_post_handler(
    background_tasks: BackgroundTasks,
    key: str,
    plant_id: str,
    upload_id: str,
    file: UploadFile,
    bucket_name: str = "plant-photos",
    policy: str = None,
    signature: str = None,
    legacy_signature: str = None
):
    """
    Full Parity S3 Presigned POST Endpoint.
    Landing zone for all uploads with SigV4/SigV2 verification.
    """
    # 1. AUTHENTICATION (Phase 9 Requirement)
    active_signature = signature or legacy_signature
    if policy and active_signature:
        logger.info(f"[Auth] Verifying signature for bucket: {bucket_name}")
        
        if not verify_s3_signature(policy, active_signature):
            logger.error("[Auth] SignatureDoesNotMatch")
            raise HTTPException(status_code=403, detail="SignatureDoesNotMatch")
            
        if not validate_policy_json(policy, bucket_name, key):
            logger.error("[Auth] AccessDenied (Policy Invalid/Expired)")
            raise HTTPException(status_code=403, detail="AccessDenied")
            
        logger.info("[Auth] Signature verified successfully.")
    else:
        # In mock mode, we allow unsigned for easier testing if configured, 
        # but warn that it deviates from production.
        logger.warning("[Auth] No policy/signature provided. Skipping verification (Mock Mode).")

    # 2. STORAGE (Landing Zone)
    storage_filename = f"{upload_id}_{os.path.basename(key)}"
    inbox_path = os.path.join(S3_INBOX, storage_filename)
    
    try:
        with open(inbox_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"[S3 Service] IO Error writing to inbox: {str(e)}")
        raise HTTPException(status_code=500, detail="InternalStorageError")
    
    # 3. EVENT TRIGGER (Lambda Simulation)
    logger.info(f"[S3 Service] Object created: {key}. Triggering lambda...")
    try:
        background_tasks.add_task(s3_trigger_handler, inbox_path, upload_id, plant_id)
    except Exception as e:
        logger.error(f"[S3 Service] Task handoff FAILED: {str(e)}")
        # Note: In real S3, the upload succeeds even if the trigger has issues (async)
    
    # 4. RESPONSE PARITY (XML)
    location = f"http://app.localhost/cdn/{storage_filename}"
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<PostResponse>
    <Location>{location}</Location>
    <Bucket>{bucket_name}</Bucket>
    <Key>{key}</Key>
</PostResponse>"""

    return Response(
        content=xml_content,
        media_type="application/xml",
        status_code=201
    )
