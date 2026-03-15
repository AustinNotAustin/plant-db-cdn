import hashlib
import hmac
import json
import logging
import re

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from datetime import datetime, timezone

from .config import get_env_or_raise


logger = logging.getLogger(__name__)

# Try to get AWS keys, but don't crash yet if missing 
# (allows configuration to be updated via env)
try:
    AWS_S3_SECRET_ACCESS_KEY = get_env_or_raise("AWS_S3_SECRET_ACCESS_KEY")
    AWS_S3_ACCESS_KEY_ID = get_env_or_raise("AWS_S3_ACCESS_KEY_ID")
except Exception:
    logger.warning("AWS credentials not found in environment. Signature verification will fail.")
    AWS_S3_SECRET_ACCESS_KEY = None
    AWS_S3_ACCESS_KEY_ID = None

try:
    AWS_ACCOUNT_ID = get_env_or_raise("AWS_ACCOUNT_ID")
except Exception:
    logger.warning("AWS_ACCOUNT_ID not found in environment. ExpectedBucketOwner check may skip.")
    AWS_ACCOUNT_ID = None


async def verify_s3_v4_signature(request):
    """
    Verifies an S3 SigV4 signature for a given FastAPI request.
    Specifically targets PUT requests from the image-worker.
    """
    if not AWS_S3_SECRET_ACCESS_KEY or not AWS_S3_ACCESS_KEY_ID:
        logger.error("Signature verification failed: Missing AWS credentials.")
        return False

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("AWS4-HMAC-SHA256"):
        logger.error("Signature verification failed: Missing or invalid Authorization header.")
        return False

    # 1. Check Expected Bucket Owner if configured
    expected_owner = request.headers.get("x-amz-expected-bucket-owner")
    if AWS_ACCOUNT_ID and expected_owner and expected_owner != AWS_ACCOUNT_ID:
        logger.error(f"Bucket owner mismatch: Expected {AWS_ACCOUNT_ID}, got {expected_owner}")
        return False

    try:
        # Reconstruct the AWSRequest for botocore to sign
        # We need the body for the payload hash if it's not UNSIGNED-PAYLOAD
        body = await request.body()
        
        # FastAPI request.url.path includes the leading slash
        # botocore expects the path to be used in canonical request
        
        # We need to filter headers to only include what was signed
        # The Authorization header looks like: 
        # AWS4-HMAC-SHA256 Credential=.../20260315/us-east-1/s3/aws4_request, SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature=...
        
        signed_headers_match = re.search(r"SignedHeaders=([^,]+)", auth_header)
        if not signed_headers_match:
            logger.error("Could not find SignedHeaders in Authorization header.")
            return False
            
        signed_header_names = signed_headers_match.group(1).split(";")
        
        # Map FastAPI headers to a dict for botocore
        # Botocore expects headers to be case-insensitive or specifically formatted
        headers_to_sign = {}
        for h in signed_header_names:
            val = request.headers.get(h)
            if val:
                headers_to_sign[h] = val

        # Create a botocore AWSRequest
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=body,
            headers=headers_to_sign
        )

        # Use botocore's SigV4Auth to generate the canonical request and signature
        credentials = Credentials(AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY)
        auth = SigV4Auth(credentials, "s3", "us-east-1")
        
        # signature_provided is at the end of the Auth header
        signature_match = re.search(r"Signature=([a-f0-9]+)", auth_header)
        if not signature_match:
            logger.error("Could not find Signature in Authorization header.")
            return False
        provided_signature = signature_match.group(1)

        # To verify, we'll let botocore sign our reconstructed request and compare
        # Note: botocore's add_auth modifies the request in place
        auth.add_auth(aws_request)
        
        new_auth_header = aws_request.headers.get("Authorization")
        new_signature_match = re.search(r"Signature=([a-f0-9]+)", new_auth_header)
        expected_signature = new_signature_match.group(1)

        if hmac.compare_digest(provided_signature, expected_signature):
            return True
            
        logger.error(f"Signature mismatch. Provided: {provided_signature}, Expected: {expected_signature}")
        return False

    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def verify_s3_signature(policy_b64: str, signature_provided: str) -> bool:
    """
    Verifies an S3 Signature against the provided Policy.
    Note: For simplicity in this mock, we verify SigV2/Post-Style signatures
    which is just HMAC-SHA1 or SHA256 of the policy.
    """
    if not AWS_S3_SECRET_ACCESS_KEY:
        logger.error("Signature verification skipped: No AWS_S3_SECRET_ACCESS_KEY.")
        return False
        
    if not policy_b64 or not signature_provided:
        logger.error("Signature verification failed: Missing policy or signature.")
        return False

    try:
        # standard S3 Post Policy signature is HMAC-SHA1 of the base64 policy
        # but SigV4 uses SHA256. We'll check both for robustness in mocking.
        
        # SigV2/Standard Post Policy format
        expected_sig = base64.b64encode(
            hmac.new(
                AWS_S3_SECRET_ACCESS_KEY.encode('utf-8'),
                policy_b64.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')

        if hmac.compare_digest(expected_sig, signature_provided):
            return True

        # SigV4 check (simplified for mock - usually requires signing key/date chain)
        # In a full SigV4 POST, the signature is hex-encoded HMAC-SHA256
        v4_expected = hmac.new(
            AWS_S3_SECRET_ACCESS_KEY.encode('utf-8'),
            policy_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(v4_expected, signature_provided):
            return True

        logger.error(f"Signature mismatch. Provided: {signature_provided}")
        return False

    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False

def validate_policy_json(policy_b64: str, bucket_name: str, key: str) -> bool:
    """
    Decodes the policy and checks for expiration and bucket/key constraints.
    """
    try:
        policy_json = base64.b64decode(policy_b64).decode('utf-8')
        policy = json.loads(policy_json)
        
        # Check Expiration
        expiration_str = policy.get('expiration')
        if expiration_str:
            expiration = datetime.fromisoformat(expiration_str.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expiration:
                logger.error(f"Policy expired at {expiration_str}")
                return False

        # Basic condition checks (simplified)
        conditions = policy.get('conditions', [])
        # We could iterate and check ['eq', '$bucket', 'bucket_name'] etc.
        # For the mock, we'll assume valid if structure is correct or not provided.
        
        return True
    except Exception as e:
        logger.error(f"Policy validation error: {str(e)}")
        return False
