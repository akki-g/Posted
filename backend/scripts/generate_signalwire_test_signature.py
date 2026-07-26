"""Generate a legacy SignalWire/Twilio-compatible webhook signature for local testing.

This is a local testing utility only. It never reads SIGNALWIRE_API_TOKEN from
.env - pass a throwaway token explicitly via --token so nobody accidentally
prints (or curls with) the production secret.

Usage (from backend/):
    uv run python scripts/generate_signalwire_test_signature.py \\
        --token 'test-token' \\
        --url 'http://127.0.0.1:8000/api/v1/webhooks/signalwire' \\
        --body 'AccountSid=project-test&Body=balance&From=%2B15555550100'

Then replay it:
    curl -i -X POST '<url>' \\
        -H 'Content-Type: application/x-www-form-urlencoded' \\
        -H "X-Twilio-Signature: <printed signature>" \\
        --data-raw '<body>'
"""

import argparse
import sys
from urllib.parse import parse_qsl

sys.path.insert(0, ".")
from app.services.signalwire_signature import calculate_legacy_signature  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, help="Throwaway token, never a real secret.")
    parser.add_argument("--url", required=True, help="Exact webhook URL to sign.")
    parser.add_argument("--body", required=True, help="Raw x-www-form-urlencoded request body.")
    args = parser.parse_args()

    form_fields = tuple(parse_qsl(args.body, keep_blank_values=True))
    signature = calculate_legacy_signature(token=args.token, url=args.url, form_fields=form_fields)
    print(signature)


if __name__ == "__main__":
    main()
