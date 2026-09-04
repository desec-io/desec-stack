#!/usr/bin/env python3
"""
Reference arbiter for the deSEC gatekeeping interface (see README.md).

The API POSTs a JSON object describing a request it does not want to decide on its own, and this
service answers with a JSON object carrying the verdict. All decision making lives in decide().

This arbiter allows everything.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ADDRESS = ("", 8000)
MAX_CONTENT_LENGTH = 64 * 1024


def decide(request):
    return {"verdict": "allow"}


class Arbiter(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "desec-gatekeeper"
    timeout = 10  # do not let a peer occupy a thread indefinitely

    def version_string(self):
        return self.server_version

    def do_POST(self):
        length = self.headers.get("Content-Length", "")
        if (
            not (length.isascii() and length.isdigit())
            or int(length) > MAX_CONTENT_LENGTH
        ):
            return self.respond(400, {"detail": "Invalid or missing Content-Length."})
        try:
            request = json.loads(self.rfile.read(int(length)))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.respond(400, {"detail": "Malformed JSON."})
        if not isinstance(request, dict):
            return self.respond(400, {"detail": "Expected a JSON object."})
        self.respond(200, decide(request))

    def respond(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        if status != 200:
            # The request body may not have been consumed, so the connection cannot be reused.
            self.send_header("Connection", "close")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(address=ADDRESS):
    ThreadingHTTPServer(address, Arbiter).serve_forever()


if __name__ == "__main__":
    serve()
