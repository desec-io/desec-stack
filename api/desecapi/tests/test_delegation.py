import socket
import threading
from contextlib import contextmanager

from django.test import SimpleTestCase, override_settings

from desecapi import unbound


class UnboundControlTestCase(SimpleTestCase):
    """
    Exercises the unbound-control client against a socket speaking the UBCT1
    handshake.
    """

    @contextmanager
    def server(self, response=b"ok\n"):
        received = []
        listener = socket.create_server(("127.0.0.1", 0))

        def serve():
            try:
                connection, _ = listener.accept()
            except OSError:  # listener closed without a connection
                return
            with connection:
                received.append(connection.recv(4096))
                connection.sendall(response)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            with override_settings(
                UNBOUND_HOST="127.0.0.1",
                UNBOUND_CONTROL_PORT=listener.getsockname()[1],
            ):
                yield received
        finally:
            listener.close()
            thread.join(timeout=5)

    def test_command(self):
        with self.server() as received:
            unbound.flush_delegation("example.com.")
        self.assertEqual(received, [b"UBCT1 flush_delegation example.com.\n"])

    def test_error_response(self):
        with self.server(response=b"error unknown command\n"):
            with self.assertRaisesMessage(
                unbound.UnboundControlException, "error unknown command"
            ):
                unbound.flush_delegation("example.com.")

    def test_empty_response(self):
        with self.server(response=b""):
            with self.assertRaises(unbound.UnboundControlException):
                unbound.flush_delegation("example.com.")

    def test_unreachable(self):
        # Claim a port, then release it so that nothing listens on it.
        with socket.create_server(("127.0.0.1", 0)) as listener:
            port = listener.getsockname()[1]
        with override_settings(UNBOUND_HOST="127.0.0.1", UNBOUND_CONTROL_PORT=port):
            with self.assertRaises(unbound.UnboundControlException):
                unbound.flush_delegation("example.com.")
