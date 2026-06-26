import aiofiles
import logging
import os

from fastapi import UploadFile, Form, Response, HTTPException, Depends
from typing import Annotated

from .auth import verify_s3_signature, validate_policy_json
from .config import SRV_MOCK_S3_URL, get_object_path

logger = logging.getLogger(__name__)


# --- AWS S3 ENDPOINT ---
class S3AuthParams:
    def __init__(
        self,
        key: str = Form(...),
        policy: str = Form(None, alias="policy"),
        policy_legacy: str = Form(None, alias="Policy"),
        signature: str = Form(None, alias="x-amz-signature"),
        signature_legacy: str = Form(None, alias="X-Amz-Signature"),
        credential: str = Form(None, alias="x-amz-credential"),
        credential_legacy: str = Form(None, alias="X-Amz-Credential"),
        algorithm: str = Form(None, alias="x-amz-algorithm"),
        algorithm_legacy: str = Form(None, alias="X-Amz-Algorithm"),
        date: str = Form(None, alias="x-amz-date"),
        date_legacy: str = Form(None, alias="X-Amz-Date"),
        security_token: str = Form(None, alias="x-amz-security-token"),
        security_token_legacy: str = Form(None, alias="X-Amz-Security-Token"),
        aws_access_key_id: str = Form(None, alias="AWSAccessKeyId"),
        legacy_signature: str = Form(None, alias="signature"),
    ):
        self.key = key
        self.policy = policy or policy_legacy
        self.signature = signature or signature_legacy
        self.credential = credential or credential_legacy
        self.algorithm = algorithm or algorithm_legacy
        self.date = date or date_legacy
        self.security_token = security_token or security_token_legacy
        self.aws_access_key_id = aws_access_key_id
        self.legacy_signature = legacy_signature


async def mock_s3_presigned_post_handler(
    file: UploadFile,
    bucket_name: str,
    s3_params: Annotated[S3AuthParams, Depends()]
):
    """
    Full Parity S3 Presigned POST Endpoint.
    Landing zone for all uploads with SigV4/SigV2 verification.
    """
    # 1. AUTHENTICATION (Phase 9 Requirement)
    active_signature = s3_params.signature or s3_params.legacy_signature
    if s3_params.policy and active_signature:
        logger.info(f"[Auth] Verifying signature for bucket: {bucket_name}")
        
        if not verify_s3_signature(s3_params.policy, active_signature, s3_params.credential):
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

    # 2. STORAGE
    # Strictly preserve the requested S3 key hierarchy for S3 parity.
    relative_key = s3_params.key

    try:
        object_path = get_object_path(bucket_name, relative_key)
        os.makedirs(os.path.dirname(object_path), exist_ok=True)
        
        async with aiofiles.open(object_path, mode="wb") as buffer:
            content = await file.read()
            await buffer.write(content)
    except ValueError:
        logger.error(f"[S3 Service] Invalid key for bucket {bucket_name}: {relative_key}")
        raise HTTPException(status_code=400, detail="InvalidObjectKey")
    except Exception as e:
        logger.error(f"[S3 Service] IO Error writing object: {str(e)}")
        raise HTTPException(status_code=500, detail="InternalStorageError")

    
    # 4. RESPONSE PARITY (XML)
    # Location reflects the true hierarchical path for internal consumption.
    location = f"{SRV_MOCK_S3_URL}/{bucket_name}/{relative_key}"
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
