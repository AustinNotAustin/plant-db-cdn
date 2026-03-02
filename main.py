import logging
import sys
import uvicorn

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, Response, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

from aws_services.config import PORT, S3_LONGTERM
from aws_services.s3_service import mock_s3_presigned_post_handler

app = FastAPI(title="Mock AWS Service Architecture (Modular)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://app.localhost",
        "http://app.localhost:3000",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/cdn", StaticFiles(directory=S3_LONGTERM), name="cdn")

@app.api_route("/health", methods=["GET", "OPTIONS"])
async def cdn_health_check():
    return Response(content='{"status": "cdn_reachable"}', media_type="application/json")

@app.post("/{bucket_name}", status_code=201)
async def s3_presigned_post(
    bucket_name: str,
    background_tasks: BackgroundTasks,
    key: str = Form(...),
    plant_id: str = Form(..., alias="x-amz-meta-plant-id"),
    upload_id: str = Form(..., alias="x-amz-meta-upload-id"),
    # AWS SigV4 / SigV2 specific fields from Boto3
    policy: str = Form(None, alias="Policy"),
    file: UploadFile = File(...),
    signature: str = Form(None, alias="X-Amz-Signature"),
    credential: str = Form(None, alias="X-Amz-Credential"),
    algorithm: str = Form(None, alias="X-Amz-Algorithm"),
    date: str = Form(None, alias="X-Amz-Date"),
    security_token: str = Form(None, alias="X-Amz-Security-Token"),
    # Legacy fields
    aws_access_key_id: str = Form(None, alias="AWSAccessKeyId"),
    legacy_signature: str = Form(None, alias="signature")
):
    """
    Standard S3 Path-style Endpoint.
    Aligns with Boto3-generated SigV4 presigned posts.
    """
    return await mock_s3_presigned_post_handler(
        background_tasks=background_tasks,
        key=key,
        plant_id=plant_id,
        upload_id=upload_id,
        file=file,
        bucket_name=bucket_name,
        policy=policy,
        signature=signature,
        legacy_signature=legacy_signature
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
