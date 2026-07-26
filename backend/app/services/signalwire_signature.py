"""SignalWire inbound webhook signature verification.

SignalWire's Compatibility API sends inbound SMS callbacks signed the same
way Twilio signs LaML requests: HMAC-SHA1 over the exact webhook URL followed
by every POST parameter (key then value, sorted by key, no separators),
base64-encoded, in either `X-Twilio-Signature` or `X-SignalWire-Signature`.
Per Twilio's own official `RequestValidator` source, the URL is checked both
with and without an explicit default port (`:443`/`:80`), since signature
generation on the provider's back end is documented as inconsistent about
including it. This is the only scheme confirmed against production traffic;
the `-sha256` variant headers SignalWire also sends are not yet documented
against our token and are only used for diagnostic matching, never accepted.
"""

from __future__ import annotations

import base64
import hmac
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

LEGACY_SIGNATURE_HEADERS = (
    "x-twilio-signature",
    "x-signalwire-signature",
)

SHA256_SIGNATURE_HEADERS = (
    "x-twilio-sha256-signature",
    "x-signalwire-sha256-signature",
)

ALL_SIGNATURE_HEADERS = (*LEGACY_SIGNATURE_HEADERS, *SHA256_SIGNATURE_HEADERS)

FormFields = Sequence[tuple[str, str]]


@dataclass(frozen=True)
class SignatureMatch:
    header_name: str
    candidate_name: str
    algorithm: str
    encoding: str


@dataclass(frozen=True)
class SignatureFailureDetails:
    header_names: tuple[str, ...]
    header_lengths: tuple[tuple[str, int], ...]
    matched_variants: tuple[SignatureMatch, ...]
    account_sid_matches_project: bool | None
    configured_url_matches_request_url: bool
    duplicate_parameter_keys: tuple[str, ...]
    parameter_keys: tuple[str, ...]


class InvalidSignalWireSignatureError(ValueError):
    def __init__(self, message: str, *, details: SignatureFailureDetails) -> None:
        super().__init__(message)
        self.details = details


def build_legacy_payload(*, url: str, form_fields: FormFields) -> bytes:
    """URL + every (key, value) sorted by key, concatenated. Twilio's scheme."""
    pieces = [url]
    for key, value in sorted(form_fields, key=lambda item: item[0]):
        pieces.append(key)
        pieces.append(value)
    return "".join(pieces).encode("utf-8")


def calculate_hmac_base64(*, secret: str, payload: bytes, digestmod: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, digestmod=digestmod).digest()
    return base64.b64encode(digest).decode("ascii")


def calculate_legacy_signature(*, token: str, url: str, form_fields: FormFields) -> str:
    payload = build_legacy_payload(url=url, form_fields=form_fields)
    return calculate_hmac_base64(secret=token, payload=payload, digestmod="sha1")


def validate_legacy_signature(
    *, token: str, url: str, form_fields: FormFields, signature: str
) -> bool:
    expected = calculate_legacy_signature(token=token, url=url, form_fields=form_fields)
    return hmac.compare_digest(expected, signature.strip())


def _with_explicit_port(url: str) -> str:
    """Add the scheme's default port (443/80) if the URL doesn't have one."""
    parsed = urlparse(url)
    if parsed.port:
        return url
    port = 443 if parsed.scheme == "https" else 80
    return parsed._replace(netloc=f"{parsed.netloc}:{port}").geturl()


def _without_explicit_port(url: str) -> str:
    """Strip an explicit port from the URL, if present."""
    parsed = urlparse(url)
    if not parsed.port:
        return url
    return parsed._replace(netloc=parsed.netloc.split(":")[0]).geturl()


def url_port_variants(url: str) -> tuple[str, str]:
    """Twilio's official `RequestValidator` checks the signature against the
    request URL both with and without an explicit `:443`/`:80` port, since
    "sig generation on the back end is inconsistent" (per Twilio's own
    source). Returns (with_port, without_port); one may equal `url` itself."""
    return _with_explicit_port(url), _without_explicit_port(url)


def _collect_signature_headers(headers: Mapping[str, str]) -> dict[str, str]:
    collected: dict[str, str] = {}
    lowered = {name.lower(): value for name, value in headers.items()}
    for name in ALL_SIGNATURE_HEADERS:
        value = lowered.get(name)
        if value:
            collected[name] = value
    return collected


def _diagnose_matches(
    *,
    token: str,
    signature_headers: Mapping[str, str],
    url_candidates: Mapping[str, str],
    form_fields: FormFields,
    raw_body: bytes,
) -> tuple[SignatureMatch, ...]:
    """Best-effort sweep to identify which (header, URL, algorithm, encoding)
    combination a received signature actually matches. Diagnostic only -
    never used to accept a request, only to log where a rejected one came
    close, so this is only invoked when diagnostics are enabled."""
    candidates: dict[str, bytes] = {
        name: build_legacy_payload(url=url, form_fields=form_fields)
        for name, url in url_candidates.items()
    }
    if raw_body:
        for name, url in url_candidates.items():
            candidates[f"{name}_plus_raw_body"] = url.encode("utf-8") + raw_body
        candidates["raw_body_only"] = raw_body

    matches: list[SignatureMatch] = []
    for header_name, received in signature_headers.items():
        normalized_received = received.strip()
        for candidate_name, payload in candidates.items():
            for algorithm in ("sha1", "sha256"):
                digest = hmac.new(token.encode("utf-8"), payload, digestmod=algorithm).digest()
                for encoding, expected in (
                    ("base64", base64.b64encode(digest).decode("ascii")),
                    ("hex", digest.hex()),
                ):
                    if hmac.compare_digest(expected, normalized_received):
                        matches.append(
                            SignatureMatch(
                                header_name=header_name,
                                candidate_name=candidate_name,
                                algorithm=algorithm,
                                encoding=encoding,
                            )
                        )
    return tuple(matches)


def verify_signalwire_request(
    *,
    token: str,
    configured_url: str,
    request_url: str,
    form_fields: FormFields,
    headers: Mapping[str, str],
    configured_project_id: str | None,
    raw_body: bytes = b"",
    enable_diagnostics: bool = False,
) -> None:
    """Verify an inbound SignalWire webhook.

    Accepts when either `X-Twilio-Signature` or `X-SignalWire-Signature`
    validates against the legacy HMAC-SHA1 construction using the configured
    public webhook URL. Raises `InvalidSignalWireSignatureError` otherwise.
    Never returns a bare boolean - callers must handle the exception.
    """
    signature_headers = _collect_signature_headers(headers)
    params = dict(form_fields)
    key_counts = Counter(key for key, _ in form_fields)
    duplicate_keys = tuple(sorted(key for key, count in key_counts.items() if count > 1))

    account_sid = params.get("AccountSid", "")
    account_sid_matches_project: bool | None = None
    if account_sid and configured_project_id:
        account_sid_matches_project = hmac.compare_digest(account_sid, configured_project_id)

    def _fail(matched_variants: tuple[SignatureMatch, ...] = ()) -> None:
        raise InvalidSignalWireSignatureError(
            "Invalid SignalWire signature.",
            details=SignatureFailureDetails(
                header_names=tuple(sorted(signature_headers)),
                header_lengths=tuple(
                    sorted((name, len(value)) for name, value in signature_headers.items())
                ),
                matched_variants=matched_variants,
                account_sid_matches_project=account_sid_matches_project,
                configured_url_matches_request_url=(configured_url == request_url),
                duplicate_parameter_keys=duplicate_keys,
                parameter_keys=tuple(sorted(key_counts)),
            ),
        )

    if not token or not signature_headers:
        _fail()
        return

    for header_name in LEGACY_SIGNATURE_HEADERS:
        received = signature_headers.get(header_name)
        if not received:
            continue
        for url_variant in url_port_variants(configured_url):
            if validate_legacy_signature(
                token=token, url=url_variant, form_fields=form_fields, signature=received
            ):
                return

    matched_variants: tuple[SignatureMatch, ...] = ()
    if enable_diagnostics:
        url_candidates = {"configured": configured_url, "request": request_url}
        if configured_url.endswith("/"):
            url_candidates["configured_without_trailing_slash"] = configured_url[:-1]
        else:
            url_candidates["configured_with_trailing_slash"] = configured_url + "/"
        with_port, without_port = url_port_variants(configured_url)
        url_candidates["configured_with_port"] = with_port
        url_candidates["configured_without_port"] = without_port
        matched_variants = _diagnose_matches(
            token=token,
            signature_headers=signature_headers,
            url_candidates=url_candidates,
            form_fields=form_fields,
            raw_body=raw_body,
        )

    _fail(matched_variants)
