"""Development stand-in for the GitHub webhook endpoint (SCRUM-9).

Listens on http://127.0.0.1:8000/api/v1/github/webhooks, the same path the real
endpoint will use (SCRUM-45), so the smee tunnel can be tested before the backend
exists. Stop it (Ctrl+C) before starting the backend on port 8000.

For each POST it logs only metadata: event, delivery id, action, body size and the
HMAC result. It never logs the body, headers or the secret.

    GITHUB_WEBHOOK_SECRET=<value> python infra/scripts/webhook_echo.py

Without GITHUB_WEBHOOK_SECRET the signature is reported as "not checked" and every
delivery gets 202. With it, a missing or invalid X-Hub-Signature-256 gets 401, like
the real endpoint. Standard library only; not used in production.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = int(os.environ.get("WEBHOOK_ECHO_PORT", "8000"))
PATH = "/api/v1/github/webhooks"
MAX_BODY = 25 * 1024 * 1024  # GitHub caps payloads at 25 MB


def signature_ok(secret: bytes, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


class Handler(BaseHTTPRequestHandler):
    server_version = "webhook-echo"

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != PATH:
            self._reply(404, "not found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self._reply(413, "body too large")
            return
        body = self.rfile.read(length)

        # Verify the raw bytes before parsing anything (security.md).
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").encode()
        if secret:
            valid = signature_ok(secret, body, self.headers.get("X-Hub-Signature-256"))
            sig = "valid" if valid else "INVALID"
        else:
            valid, sig = True, "not checked (GITHUB_WEBHOOK_SECRET unset)"

        action = "-"
        if valid:
            try:
                action = str(json.loads(body).get("action", "-"))
            except (ValueError, AttributeError):
                action = "(unparsable body)"

        stamp = datetime.now(UTC).strftime("%H:%M:%S")
        print(
            f"{stamp} event={self.headers.get('X-GitHub-Event', '-')} "
            f"delivery={self.headers.get('X-GitHub-Delivery', '-')} action={action} "
            f"bytes={len(body)} signature={sig}",
            flush=True,
        )
        if valid:
            self._reply(202, "accepted")
        else:
            self._reply(401, "invalid signature")

    def _reply(self, status: int, text: str) -> None:
        payload = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass  # silence the default access log; do_POST prints its own line


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"webhook-echo listening on http://{HOST}:{PORT}{PATH} (Ctrl+C to stop)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    sys.exit(0)


if __name__ == "__main__":
    main()
