"""Code generation and hashing for SMS phone-number verification."""

import hashlib
import hmac
import secrets
from datetime import timedelta

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
REQUEST_WINDOW = timedelta(hours=1)
MAX_REQUESTS_PER_WINDOW = 5
MAX_VERIFY_ATTEMPTS = 5


def generate_code() -> str:
    """Return a cryptographically random 6-digit numeric code, zero-padded."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str, secret: str) -> str:
    """HMAC-SHA256 the code so it is never stored in plaintext."""
    return hmac.new(secret.encode(), code.encode(), hashlib.sha256).hexdigest()
