# Image Upload System (Zero Local Contact)

This document describes the "Zero Local Contact" image upload architecture used in the Plant DB project. This design ensures that raw image binary data never touches the Django backend, improving scalability, security, and reducing server load.

## Architecture Overview

The system consists of three primary components orchestrating a secure upload:

1.  **Frontend (Client)**: The React/Vite application that orchestrates the user experience and handles the direct-to-S3 upload.
2.  **Backend (Django)**: The API that manages metadata, generates secure "upload intents," and validates callbacks.
3.  **CDN / Object Storage (AWS S3 / Mock CDN)**: The storage layer where files are actually persisted.

---

## The 3-Step Upload Flow

### 1. Request Upload Intent
**Frontend → Backend**

When a user selects an image, the Frontend sends a `POST` request to the Backend (e.g., `/api/plants/{id}/upload-intent/`).
- **Backend Role**: 
    - Validates that the user has permission to upload for this specific plant.
    - Communicates with AWS S3 (or the Mock CDN) to generate a **Presigned POST** object.
    - This object contains a temporary URL and a set of cryptographically signed fields (Policy, Signature, etc.) that authorize a single upload.
- **Result**: The Frontend receives the temporary URL and required form fields.

### 2. Direct Binary Upload & Multi-Stage Validation
**Frontend → S3 / CDN (Quarantine Layer)**

The Frontend performs a `multipart/form-data` POST directly to the S3 URL provided in Step 1.
- **S3 / CDN (Temporary/Quarantine Layer) Role**:
    - Validates the signature and policy.
    - If valid, accepts and persists binary data into **Temporary/Quarantine Storage**.
    - **Security & Integrity Analysis**: An automated trigger (e.g., S3 Event + Lambda) initiates a multi-point scan:
        - **Vulnerability Scan**: Checks for embedded malware or malicious payloads.
        - **Content Moderation**: Filters for inappropriate or prohibited imagery.
        - **Compliance Check**: Verifiers file size, dimensions, and mime-type integrity.
- **Result & Signal**:
    - **If Analysis Fails (`false`)**: The file remains in quarantine or is purged. A failure status/code is returned to the Frontend.
    - **If Analysis Passes (`true`)**: The orchestrator moves the file from quarantine into **Long-Term Storage (Production Bucket)**.
    - The Frontend receives a success response only after validation logic concludes or high-level persistence is confirmed.

### 3. Metadata Callback
**Frontend → Backend**

Once the upload is successful, the Frontend sends a final `POST` to the Backend (e.g., `/api/plants/photo-callback/`).
- **Backend Role**:
    - Receives only the **reference** (file key/UUID) and plant ID.
    - Verifies the authenticity of the upload (e.g., using a Bearer token and by checking storage existence).
    - Creates a record in the database linking the photo metadata to the plant.
- **Result**: The photo is now "officially" part of the plant's database record.
