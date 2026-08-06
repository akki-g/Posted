"""Telnyx inbound webhook signature verification.

Telnyx signs every webhook with an Ed25519 public-key signature: the
`telnyx-signature-ed25519` header holds a base64-encoded signature over
`{telnyx-timestamp}|{raw request body}`, verified against the account's
public key (Mission Control Portal > Public Key) - never a shared secret,
unlike the HMAC schemes used by Twilio-compatible providers. A timestamp
tolerance window guards against replaying an old, validly-signed request.
See https://developers.telnyx.com/docs/messaging/webhooks/signing.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SIGNATURE_HEADER = "telnyx-signature-ed25519"
TIMESTAMP_HEADER = "telnyx-timestamp"

# Telnyx's own SDKs default to a 5-minute tolerance window to block replays.
DEFAULT_TOLERANCE_SECONDS = 300


class InvalidTelnyxSignatureError(ValueError):
    """Raised when an inbound Telnyx webhook fails signature or freshness checks."""


def verify_telnyx_request(
    *,
    public_key: str,
    headers: Mapping[str, str],
    raw_body: bytes,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: float | None = None,
) -> None:
    """Verify an inbound Telnyx webhook's Ed25519 signature and timestamp freshness.

    Raises `InvalidTelnyxSignatureError` on any failure. Never returns a bare
    boolean - callers must handle the exception.
    """
    lowered = {name.lower(): value for name, value in headers.items()}
    signature_b64 = lowered.get(SIGNATURE_HEADER)
    timestamp = lowered.get(TIMESTAMP_HEADER)
    if not signature_b64 or not timestamp:
        raise InvalidTelnyxSignatureError("Missing Telnyx signature headers.")

    if not public_key:
        raise InvalidTelnyxSignatureError("Telnyx public key is not configured.")

    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise InvalidTelnyxSignatureError("Malformed Telnyx timestamp header.") from exc

    current_time = time.time() if now is None else now
    if abs(current_time - timestamp_value) > tolerance_seconds:
        raise InvalidTelnyxSignatureError(
            "Telnyx webhook timestamp is outside the tolerance window."
        )

    try:
        signature = base64.b64decode(signature_b64, validate=True)
        public_key_bytes = base64.b64decode(public_key, validate=True)
    except (ValueError, TypeError) as exc:
        raise InvalidTelnyxSignatureError(
            "Malformed Telnyx signature or public key encoding."
        ) from exc

    message = f"{timestamp}|".encode() + raw_body
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, message)
    except (InvalidSignature, ValueError) as exc:
        raise InvalidTelnyxSignatureError("Invalid Telnyx signature.") from exc
