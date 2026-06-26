# Mock S3

Mock S3 is a local S3-compatible object storage service for development. It supports bucket-style uploads, downloads, worker write-backs, and a small public-object shortcut for files in a configured public bucket.

## Features

- **S3 Presigned POST parity**: handles `POST /{bucket}` with `multipart/form-data` from boto3 `generate_presigned_post`.
- **S3 PutObject/GetObject parity**: supports `PUT /{bucket}/{key}` and `GET /{bucket}/{key}`.
- **Generic buckets**: stores objects under `S3_STORAGE_ROOT/{bucket}/{key}`.
- **Dumb storage**: no image processing, scanning, webhooks, or compute behavior.
- **Public shortcut**: serves objects from `S3_DEFAULT_PUBLIC_BUCKET` through `/cdn/{key}` for local browser testing.

## API

### Presigned POST

`POST /{bucket_name}`

- Accepts boto3 SigV4 presigned POST fields, including lowercase `policy` and `x-amz-*` fields.
- Stores object at `S3_STORAGE_ROOT/{bucket_name}/{key}`.
- Returns `201 Created` with S3-style XML.

### PutObject

`PUT /{bucket_name}/{key:path}`

- Used by workers or local services to store objects.
- Requires valid AWS SigV4 `Authorization` header when credentials are configured.
- Optionally verifies `x-amz-expected-bucket-owner` when `AWS_ACCOUNT_ID` is configured.

### GetObject

`GET /{bucket_name}/{key:path}`

- Returns stored object bytes.
- Returns `404` when object does not exist.

### Public Shortcut

`GET /cdn/{path:path}`

- Reads from `S3_DEFAULT_PUBLIC_BUCKET`.
- Exists for local browser testing, not as production CDN behavior.

## Setup

Copy `.env-template` to `.env` and set:

```env
AWS_ACCOUNT_ID=123456789012
AWS_S3_ACCESS_KEY_ID=mock-access-key
AWS_S3_SECRET_ACCESS_KEY=mock-secret-key
SRV_MOCK_S3_PORT=8001
SRV_MOCK_S3_URL=http://localhost:8001
S3_STORAGE_ROOT=s3_buckets
S3_DEFAULT_PUBLIC_BUCKET=s3_dev_media
```

Start:

```bash
./starter.sh start --build
```

URLs:

- S3 endpoint: `http://localhost:8001`
- Public shortcut: `http://localhost:8001/cdn/{key}`
- Swagger UI: `http://localhost:8001/docs`

## Using With Media Upload Architecture

For a Django app using an S3 inbox plus scanner flow:

```env
AWS_S3_ACCESS_KEY_ID=mock-access-key
AWS_S3_SECRET_ACCESS_KEY=mock-secret-key
AWS_S3_REGION_NAME=us-east-1
AWS_S3_BUCKET_NAME=s3_inbox
AWS_S3_ENDPOINT_URL=http://localhost:8001
AWS_S3_CUSTOM_DOMAIN=http://localhost:8001/cdn
```

Use `AWS_S3_ENDPOINT_URL=http://localhost:8001` when Django runs on the host. If Django runs in Docker on the same compose network, use `http://mock-s3:8001` for service-to-service access and make sure the browser receives a reachable upload URL.

## Development

- Clear storage: `docker compose exec mock-s3 find /app/s3_buckets -mindepth 1 -delete`
- Security scan: `./scripts/security-scan.sh`
- Plant-DB reference docs: legacy Plant-DB upload notes and archived processors live in `docs/plant-db-reference/` and are not used by runtime code.
