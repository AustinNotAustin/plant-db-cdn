import logging
import sys
import uvicorn
import os
import aiofiles

from aws_services.config import PORT, S3_LONGTERM, S3_INBOX
from aws_services.s3_service import mock_s3_presigned_post_handler, S3AuthParams
from fastapi import FastAPI, UploadFile, File, Form, Response, Depends, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Annotated


# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


app = FastAPI(title="Mock AWS Service Architecture (Modular)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://app.localhost",
        "http://app.localhost:3000",
        "http://localhost:3000",
        "http://localhost"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/cdn", StaticFiles(directory=S3_LONGTERM), name="cdn")

@app.get(
    "/s3_inbox/{path:path}",
    responses={404: {"description": "File not found"}}
)
async def get_inbox_file(path: str):
    """
    Custom GET handler for s3_inbox to support extensionless blobs.
    """
    file_path = os.path.join(S3_INBOX, path)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/octet-stream")

@app.api_route("/health", methods=["GET", "OPTIONS"])
async def cdn_health_check():
    return Response(content='{"status": "cdn_reachable"}', media_type="application/json")


@app.put("/{bucket_name}/{key:path}")
async def s3_put_object(bucket_name: str, key: str, request: Request):
    """
    Mock S3 PUT Object endpoint for Image Worker write-backs.
    STRICT ENFORCEMENT: Only allows 'company_X/plant_Y' hierarchical paths.
    """
    # 1. Strict Hierarchy Validation: Every key MUST start with company_
    if not key.startswith("company_"):
        logger.error(f"[S3 Mock] PUT AccessDenied: Key '{key}' violates company hierarchy policy.")
        return Response(content="AccessDenied (Strict Company Hierarchy Required)", status_code=403)

    target_path = os.path.join(S3_LONGTERM, key)
    
    # 2. Prevent directory traversal/root-sprawl hacks
    # Check that it follows standard pattern: company_ID/plant_ID/filename
    parts = key.split("/")
    if len(parts) < 3 or not parts[1].startswith("plant_"):
         logger.error(f"[S3 Mock] PUT AccessDenied: Key '{key}' missing required plant_ folder.")
         return Response(content="AccessDenied (Invalid Object Path Depth)", status_code=403)

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    body = await request.body()
    try:
        async with aiofiles.open(target_path, mode="wb") as f:
            await f.write(body)
        logger.info(f"[S3 Mock] PUT Object successful: {bucket_name}/{key}")
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"[S3 Mock] PUT Object FAILED: {str(e)}")
        return Response(content=str(e), status_code=500)


@app.post("/{bucket_name}", status_code=201)
async def s3_presigned_post(
    bucket_name: str,
    file: Annotated[UploadFile, File()],
    s3_params: Annotated[S3AuthParams, Depends()]
):
    """
    Standard S3 Path-style Endpoint.
    Aligns with Boto3-generated SigV4 presigned posts.
    """
    return await mock_s3_presigned_post_handler(
        file=file,
        bucket_name=bucket_name,
        s3_params=s3_params
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

