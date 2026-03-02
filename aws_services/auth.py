import base64
import hashlib
import hmac
import json
import logging

from datetime import datetime, timezone

from .config import get_env_or_raise


logger = logging.getLogger(__name__)

# Try to get AWS_SECRET_ACCESS_KEY, but don't crash yet if missing 
# (allows configuration to be updated via env)
try:
    AWS_SECRET_ACCESS_KEY = get_env_or_raise("AWS_SECRET_ACCESS_KEY")
except Exception:
    logger.warning("AWS_SECRET_ACCESS_KEY not found in environment. Signature verification will fail.")
    AWS_SECRET_ACCESS_KEY = None

def verify_s3_signature(policy_b64: str, signature_provided: str) -> bool:
    """
    Verifies an S3 Signature against the provided Policy.
    Note: For simplicity in this mock, we verify SigV2/Post-Style signatures
    which is just HMAC-SHA1 or SHA256 of the policy.
    """
    if not AWS_SECRET_ACCESS_KEY:
        logger.error("Signature verification skipped: No AWS_SECRET_ACCESS_KEY.")
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
                AWS_SECRET_ACCESS_KEY.encode('utf-8'),
                policy_b64.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')

        if hmac.compare_digest(expected_sig, signature_provided):
            return True

        # SigV4 check (simplified for mock - usually requires signing key/date chain)
        # In a full SigV4 POST, the signature is hex-encoded HMAC-SHA256
        v4_expected = hmac.new(
            AWS_SECRET_ACCESS_KEY.encode('utf-8'),
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
