import json
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from threading import Thread

import arbiter


class ArbiterTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
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

    def test_malformed_json(self):
        status, _ = self.post(b"{")
        self.assertEqual(status, 400)

    def test_not_an_object(self):
        status, _ = self.post(b"[]")
        self.assertEqual(status, 400)

    def test_oversized_request(self):
        status, _ = self.post(b" " * (arbiter.MAX_CONTENT_LENGTH + 1))
        self.assertEqual(status, 400)

    def test_get_not_allowed(self):
        try:
            with urllib.request.urlopen(self.url) as response:
                self.fail(f"Expected an error, but got {response.status}.")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 501)


if __name__ == "__main__":
    unittest.main()
