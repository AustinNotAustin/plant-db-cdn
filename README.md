# Plant-DB Mock CDN (Dumb S3 Mimic)

This service simulates AWS S3 (Presigned POST and PutObject) and AWS CloudFront (CDN) for the Plant-DB system. It provides high-fidelity AWS parity to ensure the Django backend can transition to production without code changes while strictly decoupling storage from compute.

## Features
- **S3 Presigned POST Parity**: Handles `POST /{bucket}` with `multipart/form-data` and `x-amz-meta-*` headers.
- **S3 PutObject Parity**: Supports `PUT /{bucket}/{key}` for direct worker write-backs.
- **Dumb Storage**: No image processing, no internal webhooks, no compute dependencies.
- **Multi-tenant Hierarchy**: Strictly enforces `company_X/plant_Y/` directory structures.
- **CloudFront Parity**: Serves processed images via a simulated CDN structure.

## API Specification

### 1. Mock S3 Presigned POST
`POST /{bucket_name}`
- Supports standard S3 metadata headers.
- Response: `201 Created` with S3-standard XML payload.

### 2. Mock S3 PutObject
`PUT /{bucket_name}/{key:path}`
- Used by the **Image Worker** to store processed variants.
- **Authentication**: Requires valid AWS SigV4 signatures (verified against `AWS_S3_SECRET_ACCESS_KEY`).
- **Owner Verification**: Optionally verifies `x-amz-expected-bucket-owner` header if `AWS_ACCOUNT_ID` is configured.
- Enforces strict multi-tenant pathing.

### 3. CDN Endpoints
- `GET /cdn/{path:path}`: Access images in the `s3_longterm/` directory.

## Infrastructure & Architecture (Pure Storage)
The service is a "Dumb Store," meaning it only provides storage and retrieval. All compute (resizing, processing) is handled by the external **Image Worker**.

### 1. AWS S3 Service (`aws_services/s3_service.py`)
- Emulates the **S3 API Layer**.
- Responsible for the initial `POST` landing into `s3_inbox/`.

### 2. Global Architecture Config (`aws_services/config.py`)
- Defines the **AWS Physical Boundaries** (S3 Buckets/Storage Tiers).

### 3. CDN / CloudFront (`main.py`)
- Provides the entry mapping for static asset delivery via `s3_longterm`.
- Implements `PUT` and `GET` handlers for worker parity.

## Setup & Running
1. **Configure Environment**: Ensure `PORT` and `BASE_URL` are set in `.env`.
2. **Start Service (Docker - Recommended)**:
   ```bash
   ./starter.sh start --build
   ```
3. **Storage Access**:
   - Raw Uploads (Inbox): `s3_inbox/`
   - Processed Photos (CDN): `s3_longterm/`
   - Public CDN URL: `http://localhost:8001/cdn/`

## Development & Cleanup
- **Clear Storage**: `docker compose exec mock-cdn find /app/s3_inbox /app/s3_longterm -mindepth 1 -delete`
- **Security Scan**: `./starter.sh scan`
- **Archived Logic**: Legacy image processing code is preserved in `archived_processors/` for reference but is not used in the runtime.
