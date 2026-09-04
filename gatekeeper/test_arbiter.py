import json
import os
import socket
import tempfile
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from threading import Thread
from unittest import mock

import arbiter
import blocklist


class ArbiterTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.blocklist_path = os.path.join(self.tmp_dir.name, "email-blocklist.txt")
        self.block()
        patcher = mock.patch.object(blocklist, "PATH", self.blocklist_path)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), arbiter.Arbiter)
        Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = "http://%s:%d/" % self.server.server_address

    def post(self, body, **kwargs):
        request = urllib.request.Request(self.url, data=body, method="POST", **kwargs)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def ask(self, **request):
        return self.post(json.dumps(request).encode())

    def raw(self, data):
        """Send raw bytes on a single connection, and return everything the server says."""
        with socket.create_connection(self.server.server_address, timeout=5) as sock:
            sock.sendall(data)
            sock.settimeout(1)
            chunks = []
            try:
                while chunk := sock.recv(4096):
                    chunks.append(chunk)
            except TimeoutError:
                pass
            return b"".join(chunks)

    @staticmethod
    def raw_request(body, length=None):
        length = len(body) if length is None else length
        return (
            b"POST / HTTP/1.1\r\nHost: gatekeeper\r\nContent-Length: %s\r\n\r\n"
            % str(length).encode()
            + body
        )

    def block(self, *lines):
        with open(self.blocklist_path, "w") as f:
            f.writelines(f"{line}\n" for line in lines)

    def test_allow(self):
        status, answer = self.ask(
            event="account_create",
            email="foo@example.com",
            ip="203.0.113.7",
            user_agent="curl/8.5.0",
            domain=None,
            captcha_solved=True,
        )
        self.assertEqual(status, 200)
        self.assertEqual(answer, {"verdict": "allow"})

    def test_unknown_event(self):
        status, answer = self.ask(event="not-an-event")
        self.assertEqual(status, 200)
        self.assertEqual(answer, {"verdict": "allow"})

    def test_empty_request(self):
        status, answer = self.ask()
        self.assertEqual(status, 200)
        self.assertEqual(answer, {"verdict": "allow"})

    def test_blocked_email(self):
        self.block("!good@blocked.example", "*@blocked.example")
        status, answer = self.ask(event="account_create", email="Foo@Blocked.example")
        self.assertEqual(status, 200)
        self.assertEqual(
            answer,
            {"verdict": "drop", "reason": "email address matches *@blocked.example"},
        )

    def test_blocked_email_excepted(self):
        self.block("!good@blocked.example", "*@blocked.example")
        status, answer = self.ask(event="account_create", email="good@blocked.example")
        self.assertEqual(status, 200)
        self.assertEqual(answer, {"verdict": "allow"})

    def test_blocked_email_other_event(self):
        self.block("*@blocked.example")
        status, answer = self.ask(event="not-an-event", email="foo@blocked.example")
        self.assertEqual(status, 200)
        self.assertEqual(answer, {"verdict": "allow"})

    def test_without_email(self):
        self.block("*@blocked.example")
        status, answer = self.ask(event="account_create", email=None)
        self.assertEqual(status, 200)
        self.assertEqual(answer, {"verdict": "allow"})

    def test_email_not_a_string(self):
        self.block("*@blocked.example")
        for email in [42, ["foo@blocked.example"], {"foo@blocked.example": 1}]:
            with self.subTest(email=email):
                status, answer = self.ask(event="account_create", email=email)
                self.assertEqual(status, 200)
                self.assertEqual(answer, {"verdict": "allow"})

    def test_malformed_json(self):
        status, _ = self.post(b"{")
        self.assertEqual(status, 400)

    def test_not_an_object(self):
        status, _ = self.post(b"[]")
        self.assertEqual(status, 400)

    def test_oversized_request(self):
        status, _ = self.post(b" " * (arbiter.MAX_CONTENT_LENGTH + 1))
        self.assertEqual(status, 400)

    def test_invalid_content_length(self):
        # Not all strings that isdigit() are ones int() accepts
        for header in [b"", b"Content-Length: \r\n", b"Content-Length: \xb2\r\n"]:
            with self.subTest(header=header):
                response = self.raw(
                    b"POST / HTTP/1.1\r\nHost: gatekeeper\r\n" + header + b"\r\n"
                )
                self.assertTrue(response.startswith(b"HTTP/1.1 400 "), response)

    def test_error_closes_connection(self):
        # The body was not consumed, so the connection cannot be reused: what follows must not be
        # answered, nor mistaken for a request of its own.
        response = self.raw(
            self.raw_request(b"X" * 20, length=arbiter.MAX_CONTENT_LENGTH + 1)
            + self.raw_request(json.dumps({"event": "account_create"}).encode())
        )
        self.assertIn(b"Connection: close", response)
        self.assertEqual(response.count(b"HTTP/1.1 "), 1, response)

    def test_connection_reuse(self):
        request = self.raw_request(json.dumps({"event": "account_create"}).encode())
        response = self.raw(request * 2)
        self.assertEqual(response.count(b'{"verdict": "allow"}'), 2, response)

    def test_get_not_allowed(self):
        try:
            with urllib.request.urlopen(self.url) as response:
                self.fail(f"Expected an error, but got {response.status}.")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 501)


if __name__ == "__main__":
    unittest.main()
