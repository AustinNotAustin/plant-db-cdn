# Mock AWS S3/CDN

This service simulates AWS S3 object storage for local services that need bucket-style uploads, downloads, and worker write-backs. It also exposes a small CDN shortcut for the configured public bucket.

## Features
- **S3 Presigned POST Parity**: Handles `POST /{bucket}` with `multipart/form-data` and `x-amz-meta-*` headers.
- **S3 PutObject/GetObject Parity**: Supports `PUT /{bucket}/{key}` and `GET /{bucket}/{key}`.
- **Generic Buckets**: Stores objects under `S3_STORAGE_ROOT/{bucket}/{key}`.
- **Dumb Storage**: No image processing, webhooks, or compute dependencies.
- **Optional Plant-DB Compatibility**: Can enforce `company_X/plant_Y/` PUT paths with `S3_ENFORCE_PLANT_HIERARCHY=true`.
- **CDN Shortcut**: Serves objects from `S3_DEFAULT_CDN_BUCKET` via `/cdn/{key}`.

## API Specification

### 1. Mock S3 Presigned POST
`POST /{bucket_name}`
- Supports standard S3 form fields plus optional metadata fields.
- Stores the object at `S3_STORAGE_ROOT/{bucket_name}/{key}`.
- Response: `201 Created` with S3-standard XML payload.

### 2. Mock S3 PutObject
`PUT /{bucket_name}/{key:path}`
- Used by workers or local services to store objects.
- **Authentication**: Requires valid AWS SigV4 signatures (verified against `AWS_S3_SECRET_ACCESS_KEY`).
- **Owner Verification**: Optionally verifies `x-amz-expected-bucket-owner` header if `AWS_ACCOUNT_ID` is configured.
- **Optional Legacy Policy**: Set `S3_ENFORCE_PLANT_HIERARCHY=true` to require `company_X/plant_Y/` keys.

### 3. Mock S3 GetObject
`GET /{bucket_name}/{key:path}`
- Returns the stored object bytes.
- Returns `404` if the object does not exist.

### 4. CDN Endpoint
- `GET /cdn/{path:path}`: Access objects in `S3_DEFAULT_CDN_BUCKET`.

## Infrastructure & Architecture (Pure Storage)
The service is a "Dumb Store," meaning it only provides storage and retrieval. All compute (resizing, processing, validation, indexing) belongs in external services.

### 1. AWS S3 Service (`aws_services/s3_service.py`)
- Emulates the **S3 API Layer**.
- Responsible for Presigned POST writes into arbitrary buckets.

### 2. Global Architecture Config (`aws_services/config.py`)
- Defines the local storage root, default CDN bucket, and compatibility policy.

### 3. CDN / CloudFront (`main.py`)
- Provides static delivery from the configured default bucket.
- Implements `PUT` and `GET` handlers for S3 parity.

## Setup & Running
1. **Configure Environment**: Ensure `SRV_CDN_PORT` and `SRV_CDN_URL` are set in `.env`.
2. **Start Service (Docker - Recommended)**:
   ```bash
   ./starter.sh start --build
   ```
3. **Storage Access**:
   - Bucket root: `s3_buckets/`
   - Example inbox bucket: `s3_buckets/s3_inbox/`
   - Example CDN bucket: `s3_buckets/s3_longterm/`
   - Public CDN URL: `http://localhost:8001/cdn/`

## Development & Cleanup
- **Clear Storage**: `docker compose exec mock-s3 find /app/s3_buckets -mindepth 1 -delete`
- **Security Scan**: `./scripts/security-scan.sh`
- **Archived Logic**: Legacy image processing code is preserved in `archived_processors/` for reference but is not used in the runtime.
