"""Generate a Telnyx-compatible webhook Ed25519 signature for local testing.

This is a local testing utility only. It never reads a real Telnyx account
key - pass a throwaway Ed25519 private key explicitly (or omit --private-key
to generate one, printing the matching public key so you can set it as
TELNYX_PUBLIC_KEY for the test).

Usage (from backend/):
    uv run python scripts/generate_telnyx_test_signature.py \\
        --body '{"data":{"event_type":"message.received",
                          "payload":{"from":{"phone_number":"+15555550100"},"text":"balance"}}}'

Then replay it:
    curl -i -X POST 'http://127.0.0.1:8000/api/v1/webhooks/telnyx' \\
        -H 'Content-Type: application/json' \\
        -H 'telnyx-timestamp: <printed timestamp>' \\
        -H 'telnyx-signature-ed25519: <printed signature>' \\
        --data-raw '<body>'
"""

import argparse
import base64
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", required=True, help="Raw JSON request body to sign.")
    parser.add_argument(
        "--private-key",
        help="Base64 Ed25519 private key (32 raw bytes). Generates a throwaway one if omitted.",
    )
    parser.add_argument(
        "--timestamp", help="Unix timestamp to sign. Defaults to the current time."
    )
    args = parser.parse_args()

    if args.private_key:
        private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(args.private_key))
    else:
        private_key = Ed25519PrivateKey.generate()
        public_key_b64 = base64.b64encode(private_key.public_key().public_bytes_raw()).decode()
        print(f"TELNYX_PUBLIC_KEY={public_key_b64}")

    timestamp = args.timestamp or str(int(time.time()))
    message = f"{timestamp}|".encode() + args.body.encode()
    signature = base64.b64encode(private_key.sign(message)).decode()

    print(f"telnyx-timestamp: {timestamp}")
    print(f"telnyx-signature-ed25519: {signature}")


if __name__ == "__main__":
    main()
