import logging
import sys
import uvicorn
import os
import aiofiles

from aws_services.auth import verify_s3_v4_signature
from aws_services.config import (
    SRV_CDN_PORT,
    S3_DEFAULT_CDN_BUCKET,
    S3_ENFORCE_PLANT_HIERARCHY,
    get_object_path,
)
from aws_services.s3_service import mock_s3_presigned_post_handler, S3AuthParams
from fastapi import FastAPI, UploadFile, File, Response, Depends, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated


# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
    stream=sys.stdout
)


logger = logging.getLogger(__name__)


app = FastAPI(title="Mock AWS S3/CDN")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://app.localhost",
        "http://app.localhost:3000",
        "http://localhost:3000",
        "http://localhost",
        "http://localhost:5173",
        "http://app.localhost:5173",
        "http://localhost:80",
        "http://app.localhost:80"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


def _file_response(bucket_name: str, key: str) -> FileResponse:
    try:
        file_path = get_object_path(bucket_name, key)
    except ValueError:
        raise HTTPException(status_code=400, detail="InvalidObjectKey")

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/octet-stream")


@app.get("/cdn/{path:path}", responses={404: {"description": "File not found"}})
async def get_cdn_file(path: str):
    """
    Legacy CDN shortcut. Serves objects from the configured default CDN bucket.
    """
    return _file_response(S3_DEFAULT_CDN_BUCKET, path)


@app.api_route("/health", methods=["GET", "OPTIONS"])
async def cdn_health_check():
    return Response(content='{"status": "cdn_reachable"}', media_type="application/json")


@app.put("/{bucket_name}/{key:path}")
async def s3_put_object(bucket_name: str, key: str, request: Request):
    """
    Mock S3 PUT Object endpoint for Image Worker write-backs.
    Verifies SigV4 signature for authentication and owner consistency.
    Optional legacy enforcement allows only 'company_X/plant_Y' hierarchical paths.
    """
    # 0. SigV4 Authentication Check
    if not await verify_s3_v4_signature(request):
        logger.error(f"[S3 Mock] PUT AccessDenied: Invalid SigV4 signature for {bucket_name}/{key}")
        return Response(content="SignatureDoesNotMatch (Invalid AWS Signature)", status_code=403)

    if S3_ENFORCE_PLANT_HIERARCHY:
        if not key.startswith("company_"):
            logger.error(f"[S3 Mock] PUT AccessDenied: Key '{key}' violates company hierarchy policy.")
            return Response(content="AccessDenied (Strict Company Hierarchy Required)", status_code=403)

        parts = key.split("/")
        if len(parts) < 3 or not parts[1].startswith("plant_"):
            logger.error(f"[S3 Mock] PUT AccessDenied: Key '{key}' missing required plant_ folder.")
            return Response(content="AccessDenied (Invalid Object Path Depth)", status_code=403)

    try:
        target_path = get_object_path(bucket_name, key)
    except ValueError:
        logger.error(f"[S3 Mock] PUT InvalidObjectKey: {bucket_name}/{key}")
        return Response(content="InvalidObjectKey", status_code=400)

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


@app.get("/{bucket_name}/{key:path}", responses={404: {"description": "File not found"}})
async def s3_get_object(bucket_name: str, key: str):
    """
    Mock S3 GET Object endpoint.
    """
    return _file_response(bucket_name, key)


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
    uvicorn.run(app, host="0.0.0.0", port=SRV_CDN_PORT)

