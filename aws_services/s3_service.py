import logging
import os
import shutil

from fastapi import BackgroundTasks, UploadFile, File, Form, Response, HTTPException, Depends

from .auth import verify_s3_signature, validate_policy_json
from .config import S3_INBOX
from .lambda_processor import s3_trigger_handler

logger = logging.getLogger(__name__)

# --- AWS S3 ENDPOINT ---

class S3AuthParams:
    def __init__(
        self,
        key: str = Form(...),
        plant_id: str = Form(..., alias="x-amz-meta-plant-id"),
        upload_id: str = Form(..., alias="x-amz-meta-upload-id"),
        image_category: str = Form("plant", alias="x-amz-meta-image-category"),
        policy: str = Form(None, alias="Policy"),
        signature: str = Form(None, alias="X-Amz-Signature"),
        credential: str = Form(None, alias="X-Amz-Credential"),
        algorithm: str = Form(None, alias="X-Amz-Algorithm"),
        date: str = Form(None, alias="X-Amz-Date"),
        security_token: str = Form(None, alias="X-Amz-Security-Token"),
        aws_access_key_id: str = Form(None, alias="AWSAccessKeyId"),
        legacy_signature: str = Form(None, alias="signature")
    ):
        self.key = key
        self.plant_id = plant_id
        self.upload_id = upload_id
        self.image_category = image_category
        self.policy = policy
        self.signature = signature
        self.credential = credential
        self.algorithm = algorithm
        self.date = date
        self.security_token = security_token
        self.aws_access_key_id = aws_access_key_id
        self.legacy_signature = legacy_signature

async def mock_s3_presigned_post_handler(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    bucket_name: str,
    s3_params: S3AuthParams = Depends()
):
    """
    Full Parity S3 Presigned POST Endpoint.
    Landing zone for all uploads with SigV4/SigV2 verification.
    """
    # 1. AUTHENTICATION (Phase 9 Requirement)
    active_signature = s3_params.signature or s3_params.legacy_signature
    if s3_params.policy and active_signature:
        logger.info(f"[Auth] Verifying signature for bucket: {bucket_name}")
        
        if not verify_s3_signature(s3_params.policy, active_signature):
            logger.error("[Auth] SignatureDoesNotMatch")
            raise HTTPException(status_code=403, detail="SignatureDoesNotMatch")
            
        if not validate_policy_json(s3_params.policy, bucket_name, s3_params.key):
            logger.error("[Auth] AccessDenied (Policy Invalid/Expired)")
            raise HTTPException(status_code=403, detail="AccessDenied")
            
        logger.info("[Auth] Signature verified successfully.")
    else:
        # In mock mode, we allow unsigned for easier testing if configured, 
        # but warn that it deviates from production.
        logger.warning("[Auth] No policy/signature provided. Skipping verification (Mock Mode).")

    # 2. STORAGE (Landing Zone)
    storage_filename = f"{s3_params.upload_id}_{os.path.basename(s3_params.key)}"
    inbox_path = os.path.join(S3_INBOX, storage_filename)
    
    try:
        with open(inbox_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"[S3 Service] IO Error writing to inbox: {str(e)}")
        raise HTTPException(status_code=500, detail="InternalStorageError")
    
    # 3. EVENT TRIGGER (Lambda Simulation)
    logger.info(f"[S3 Service] Object created: {s3_params.key}. Triggering lambda...")
    try:
        background_tasks.add_task(
            s3_trigger_handler,
            inbox_path,
            s3_params.upload_id,
            s3_params.plant_id,
            s3_params.image_category,
        )
    except Exception as e:
        logger.error(f"[S3 Service] Task handoff FAILED: {str(e)}")
        # Note: In real S3, the upload succeeds even if the trigger has issues (async)
    
    # 4. RESPONSE PARITY (XML)
    location = f"http://app.localhost/cdn/{storage_filename}"
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<PostResponse>
    <Location>{location}</Location>
    <Bucket>{bucket_name}</Bucket>
    <Key>{s3_params.key}</Key>
</PostResponse>"""

    return Response(
        content=xml_content,
        media_type="application/xml",
        status_code=201
    )
