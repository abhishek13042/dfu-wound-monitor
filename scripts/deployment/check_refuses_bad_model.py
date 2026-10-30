"""REQ-P07-S01-005 check: a service holding a wrong checkpoint must not serve.

Run against a started container.  Standard library only, so it can run outside
the image.

    python scripts/deployment/check_refuses_bad_model.py --url http://127.0.0.1:7860
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154"
                    "789c6360000002000001e221bc330000000049454e44ae426082")


def _status(request: urllib.request.Request) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")

    ready_status, ready = _status(urllib.request.Request(f"{base}/health/ready"))
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="x.png"\r\n'
            f"Content-Type: image/png\r\n\r\n").encode() + PNG + f"\r\n--{boundary}--\r\n".encode()
    upload = urllib.request.Request(f"{base}/api/v1/analyses", data=body, method="POST",
                                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    analysis_status, analysis = _status(upload)
    print(json.dumps({"ready_status": ready_status, "ready": ready,
                      "analysis_status": analysis_status, "analysis": analysis}, indent=2))
    return 0 if ready_status == 503 and analysis_status == 503 else 1


if __name__ == "__main__":
    sys.exit(main())
