import logging
import sys
import uvicorn

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, Response, Depends
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
from aws_services.s3_service import mock_s3_presigned_post_handler, S3AuthParams
from aws_services.sales_photo_schema import SalesPhotoBatchRequest
from aws_services.sales_photo_processor import process_sales_photo_batch

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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/cdn", StaticFiles(directory=S3_LONGTERM), name="cdn")

@app.api_route("/health", methods=["GET", "OPTIONS"])
async def cdn_health_check():
    return Response(content='{"status": "cdn_reachable"}', media_type="application/json")

@app.post("/tools/sales-photos", status_code=200)
async def create_sales_photos(
    request: SalesPhotoBatchRequest,
    background_tasks: BackgroundTasks
):
    """
    Accepts sales photo batch instructions and starts background processing.
    """
    background_tasks.add_task(process_sales_photo_batch, request)
    return {"status": "accepted", "batch_id": request.batch_id}

@app.post("/{bucket_name}", status_code=201)
async def s3_presigned_post(
    bucket_name: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    s3_params: S3AuthParams = Depends()
):
    """
    Standard S3 Path-style Endpoint.
    Aligns with Boto3-generated SigV4 presigned posts.
    """
    return await mock_s3_presigned_post_handler(
        background_tasks=background_tasks,
        file=file,
        bucket_name=bucket_name,
        s3_params=s3_params
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
