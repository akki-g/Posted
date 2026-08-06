import base64
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.telnyx_signature import InvalidTelnyxSignatureError, verify_telnyx_request

PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_KEY = base64.b64encode(PRIVATE_KEY.public_key().public_bytes_raw()).decode()
OTHER_PRIVATE_KEY = Ed25519PrivateKey.generate()

BODY = b'{"data":{"event_type":"message.received","payload":{"text":"balance"}}}'


def _sign(body: bytes, timestamp: str, *, key: Ed25519PrivateKey = PRIVATE_KEY) -> str:
    message = f"{timestamp}|".encode() + body
    return base64.b64encode(key.sign(message)).decode()


def _headers(
    body: bytes,
    timestamp: str,
    *,
    key: Ed25519PrivateKey = PRIVATE_KEY,
    header_name: str = "telnyx-signature-ed25519",
) -> dict[str, str]:
    return {header_name: _sign(body, timestamp, key=key), "telnyx-timestamp": timestamp}


def _now() -> str:
    return str(int(time.time()))


def test_correct_signature_passes() -> None:
    timestamp = _now()
    verify_telnyx_request(public_key=PUBLIC_KEY, headers=_headers(BODY, timestamp), raw_body=BODY)


def test_wrong_key_signature_fails() -> None:
    timestamp = _now()
    headers = _headers(BODY, timestamp, key=OTHER_PRIVATE_KEY)
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=BODY)


def test_tampered_body_fails() -> None:
    timestamp = _now()
    headers = _headers(BODY, timestamp)
    tampered = b'{"data":{"event_type":"message.received","payload":{"text":"transactions"}}}'
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=tampered)


def test_missing_signature_header_fails() -> None:
    timestamp = _now()
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(
            public_key=PUBLIC_KEY, headers={"telnyx-timestamp": timestamp}, raw_body=BODY
        )


def test_missing_timestamp_header_fails() -> None:
    headers = {"telnyx-signature-ed25519": _sign(BODY, _now())}
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=BODY)


def test_stale_timestamp_fails() -> None:
    old_timestamp = str(int(time.time()) - 3600)
    headers = _headers(BODY, old_timestamp)
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=BODY)


def test_timestamp_within_tolerance_passes() -> None:
    timestamp = str(int(time.time()) - 100)
    headers = _headers(BODY, timestamp)
    verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=BODY)


def test_malformed_timestamp_fails() -> None:
    headers = {"telnyx-signature-ed25519": "irrelevant", "telnyx-timestamp": "not-a-number"}
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=BODY)


def test_malformed_signature_encoding_fails() -> None:
    headers = {"telnyx-signature-ed25519": "not valid base64!!", "telnyx-timestamp": _now()}
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=BODY)


def test_missing_public_key_fails() -> None:
    headers = _headers(BODY, _now())
    with pytest.raises(InvalidTelnyxSignatureError):
        verify_telnyx_request(public_key="", headers=headers, raw_body=BODY)


def test_header_names_are_case_insensitive() -> None:
    timestamp = _now()
    headers = {
        "Telnyx-Signature-Ed25519": _sign(BODY, timestamp),
        "Telnyx-Timestamp": timestamp,
    }
    verify_telnyx_request(public_key=PUBLIC_KEY, headers=headers, raw_body=BODY)
