import base64
import hashlib
import hmac
import json

import pytest

from app.services.signalwire_signature import (
    InvalidSignalWireSignatureError,
    build_legacy_payload,
    calculate_legacy_signature,
    verify_signalwire_request,
)

TOKEN = "test-token-not-a-real-secret"  # noqa: S105 - fixture value, not a real secret
URL = "https://example.com/api/v1/webhooks/signalwire"

FORM_FIELDS = (
    ("AccountSid", "project-test"),
    ("Body", "balance"),
    ("From", "+15555550100"),
    ("MessageSid", "message-test"),
    ("NumMedia", "0"),
    ("NumSegments", "1"),
    ("SmsSid", "message-test"),
    ("To", "+15555550101"),
)


def _sign(url: str, form_fields, token: str = TOKEN) -> str:
    return calculate_legacy_signature(token=token, url=url, form_fields=form_fields)


def _verify(**overrides):
    kwargs = {
        "token": TOKEN,
        "configured_url": URL,
        "request_url": URL,
        "form_fields": FORM_FIELDS,
        "headers": {"x-twilio-signature": _sign(URL, FORM_FIELDS)},
        "configured_project_id": "project-test",
        "enable_diagnostics": False,
    }
    kwargs.update(overrides)
    verify_signalwire_request(**kwargs)


def test_correct_legacy_signature_passes() -> None:
    _verify()  # no exception


def test_incorrect_signature_fails() -> None:
    correct = _sign(URL, FORM_FIELDS)
    bad_signature = correct[:-1] + ("A" if correct[-1] != "A" else "B")
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(headers={"x-twilio-signature": bad_signature})


def test_modified_body_fails() -> None:
    signature = _sign(URL, FORM_FIELDS)
    tampered = tuple(
        (k, "transactions") if k == "Body" else (k, v) for k, v in FORM_FIELDS
    )
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(form_fields=tampered, headers={"x-twilio-signature": signature})


def test_modified_url_fails() -> None:
    signature = _sign(URL, FORM_FIELDS)
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(
            configured_url=URL.replace("https://", "http://"),
            headers={"x-twilio-signature": signature},
        )


def test_trailing_slash_changes_the_signature() -> None:
    signature = _sign(URL, FORM_FIELDS)
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(configured_url=URL + "/", headers={"x-twilio-signature": signature})


def test_missing_signature_fails() -> None:
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(headers={})


def test_missing_token_fails() -> None:
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(token="")


def test_duplicate_form_keys_are_preserved_in_signing() -> None:
    fields = (
        ("MediaUrl", "https://example.com/1"),
        ("MediaUrl", "https://example.com/2"),
    )
    signature = calculate_legacy_signature(token=TOKEN, url=URL, form_fields=fields)
    _verify(form_fields=fields, headers={"x-twilio-signature": signature})

    # Dropping either duplicate value changes the signed payload.
    single = (("MediaUrl", "https://example.com/1"),)
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(form_fields=single, headers={"x-twilio-signature": signature})


def test_blank_values_are_preserved() -> None:
    fields = (("Body", ""), ("From", "+15555550100"))
    signature = calculate_legacy_signature(token=TOKEN, url=URL, form_fields=fields)
    _verify(form_fields=fields, headers={"x-twilio-signature": signature})


def test_unicode_content_is_preserved() -> None:
    fields = (("Body", "What’s my balance? \U0001f680"), ("From", "+15555550100"))
    signature = calculate_legacy_signature(token=TOKEN, url=URL, form_fields=fields)
    _verify(form_fields=fields, headers={"x-twilio-signature": signature})


def test_plus_and_percent_encoded_values_differ() -> None:
    plus_body = (("Body", "A+B"),)
    escaped_body = (("Body", "A B"),)
    sig_for_plus = calculate_legacy_signature(token=TOKEN, url=URL, form_fields=plus_body)
    with pytest.raises(InvalidSignalWireSignatureError):
        _verify(form_fields=escaped_body, headers={"x-twilio-signature": sig_for_plus})


def test_account_sid_match_produces_true_diagnostic_metadata() -> None:
    bad_signature = "not-a-real-signature"
    try:
        _verify(headers={"x-twilio-signature": bad_signature})
        pytest.fail("expected InvalidSignalWireSignatureError")
    except InvalidSignalWireSignatureError as exc:
        assert exc.details.account_sid_matches_project is True


def test_account_sid_mismatch_produces_false_metadata() -> None:
    bad_signature = "not-a-real-signature"
    try:
        _verify(
            configured_project_id="a-different-project",
            headers={"x-twilio-signature": bad_signature},
        )
        pytest.fail("expected InvalidSignalWireSignatureError")
    except InvalidSignalWireSignatureError as exc:
        assert exc.details.account_sid_matches_project is False


def test_diagnostic_output_contains_no_secret_data() -> None:
    bad_signature = "not-a-real-signature"
    try:
        _verify(
            headers={"x-twilio-signature": bad_signature},
            enable_diagnostics=True,
        )
        pytest.fail("expected InvalidSignalWireSignatureError")
    except InvalidSignalWireSignatureError as exc:
        serialized = json.dumps(
            {
                "header_names": exc.details.header_names,
                "header_lengths": exc.details.header_lengths,
                "matched_variants": [
                    (m.header_name, m.candidate_name, m.algorithm, m.encoding)
                    for m in exc.details.matched_variants
                ],
                "duplicate_parameter_keys": exc.details.duplicate_parameter_keys,
                "parameter_keys": exc.details.parameter_keys,
            }
        )
        assert TOKEN not in serialized
        assert bad_signature not in serialized
        assert "balance" not in serialized
        assert "+15555550100" not in serialized
        assert "project-test" not in serialized


def test_header_names_are_case_insensitive() -> None:
    signature = _sign(URL, FORM_FIELDS)
    _verify(headers={"X-Twilio-Signature": signature})


def test_malformed_preferred_header_falls_back_to_valid_secondary_header() -> None:
    valid_signalwire_signature = _sign(URL, FORM_FIELDS)
    _verify(
        headers={
            "x-twilio-signature": "garbage",
            "x-signalwire-signature": valid_signalwire_signature,
        }
    )


def test_build_legacy_payload_sorts_by_key_and_concatenates() -> None:
    fields = (("b", "2"), ("a", "1"))
    assert build_legacy_payload(url="u", form_fields=fields) == b"ua1b2"


def test_valid_sha1_reference_vector() -> None:
    # Independent computation of Twilio's documented construction, to catch
    # accidental drift in build_legacy_payload/calculate_legacy_signature.
    data = URL + "".join(k + v for k, v in sorted(FORM_FIELDS, key=lambda kv: kv[0]))
    expected = base64.b64encode(
        hmac.new(TOKEN.encode(), data.encode("utf-8"), hashlib.sha1).digest()
    ).decode()
    assert calculate_legacy_signature(token=TOKEN, url=URL, form_fields=FORM_FIELDS) == expected
