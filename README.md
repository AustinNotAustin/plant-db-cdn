# Plant-DB Mock CDN Image Receiver (AWS S3 Parity)

This service simulates AWS S3 (Presigned POST), AWS Lambda (Triggered Processing), and AWS CloudFront (CDN) for the Plant-DB system. It provides high-fidelity AWS parity to ensure the Django backend can transition to production without code changes.

## Features
- **S3 Presigned POST Parity**: Handles `POST /{bucket}` with `multipar/form-data` and `x-amz-meta-*` headers.
- **Two-Stage Storage (Scanning)**: Mimics enterprise security flows (Temp Storage -> Validation/Scan -> Long-Term Storage).
- **Lambda Simulation**: Async background processing using Pillow for EXIF stripping and generating variant (Thumbnail/Large) images.
- **CloudFront Parity**: Serves processed images via a simulated CDN structure.
- **Async Callback**: Notifies the Django backend with `Bearer` token authentication and specific status payloads.

## API Specification

### 1. Mock S3 Presigned POST
`POST /{bucket_name}`
- Supports standard S3 metadata headers:
  - `x-amz-meta-plant-id`: Internal Plant ID.
  - `x-amz-meta-upload-id`: Unique Photo Upload ID.
- Content-Type: `multipart/form-data`.
- Response: `201 Created` with S3-standard XML payload.

### 2. AWS Lambda Simulation (Callback)
Triggered automatically after upload:
1. **Malware/Content Scan**: Simulated 1s delay and basic validation.
2. **Image Processing**: EXIF stripping + Resizing (200px Thumb, 1200px Large).
3. **Storage Tiering**: Moves valid files from `temp_uploads/` to `storage/`.
4. **Callback (Django/Backend)**: Sends a JSON POST to `CALLBACK_URL` with `Bearer {CALLBACK_SECRET}`.

**Callback Payload (Success):**
```json
{
  "upload_id": "uuid",
  "plant_id": "123",
  "status": "success",
  "large_url": "http://localhost:8001/cdn/large_uuid.jpg",
  "thumb_url": "http://localhost:8001/cdn/thumb_uuid.jpg"
}
```

**Callback Payload (Failure):**
```json
{
  "upload_id": "uuid",
  "plant_id": "123",
  "status": "failed",
  "error": "Image validation failed..."
}
```

### 3. CDN Endpoints
- `GET /cdn/{filename}`: Access images in the `storage/` directory.

## Infrastructure & Architecture (AWS Parity)
The service is decomposed into modular files that map directly to AWS managed services:

### 1. AWS S3 Service (`aws_services/s3_service.py`)
- Emulates the **S3 API Layer**.
- Responsible for the initial `POST` landing (Simulated S3 Bucket Inbox).
- Decoupled from processing; it only commits the object and signals the event trigger.

### 2. AWS Lambda Processor (`aws_services/lambda_processor.py`)
- Emulates the **Serverless Compute Layer**.
- Contains all image processing code, security scans, and status callbacks.
- Maintains zero-state; operates locally on "Quarantine" storage (Simulated Lambda Temp Disk).

### 3. Global Architecture Config (`aws_services/config.py`)
- Defines the **AWS Physical Boundaries** (S3 Buckets/Storage Tiers).
- Ensures strict configuration for local network and auth secrets.

### 4. CDN / CloudFront (`main.py`)
- Provides the entry mapping for static asset delivery via `s3_longterm`.

## Setup & Running
1. **Configure Environment**: Copy `.env.example` to `.env` and set `CALLBACK_URL` and `CALLBACK_SECRET`.
2. **Start Service (Docker - Recommended)**:
   ```bash
   ./starter.sh start --build
   ```
3. **Run Security Audit**:
   ```bash
   ./starter.sh scan
   ```
