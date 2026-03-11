import logging
import sys
import uvicorn
import os
import aiofiles

from aws_services.config import PORT, S3_LONGTERM, S3_INBOX
from aws_services.s3_service import mock_s3_presigned_post_handler, S3AuthParams
from fastapi import FastAPI, UploadFile, File, Form, Response, Depends, Request
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
app.mount("/s3_inbox", StaticFiles(directory=S3_INBOX), name="internal-inbox")


@app.api_route("/health", methods=["GET", "OPTIONS"])
async def cdn_health_check():
    return Response(content='{"status": "cdn_reachable"}', media_type="application/json")


@app.put("/{bucket_name}/{key:path}")
async def s3_put_object(bucket_name: str, key: str, request: Request):
    """
    Mock S3 PUT Object endpoint for Image Worker write-backs.
    Saves binary data directly to S3_LONGTERM (mapped to bucket).
    """
    # In this mock, we assume bucket_name is relevant but we map primarily to S3_LONGTERM structure
    # which mirrors the production bucket layout.
    target_path = os.path.join(S3_LONGTERM, key)
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

