import os
import tempfile
import unittest

import blocklist


class EmailBlocklistTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.path = os.path.join(self.tmp_dir.name, "email-blocklist.txt")

    def write(self, content):
        with open(self.path, "w") as f:
            f.write(content)

    def assertBlocked(self, content, *emails):
        self.write(content)
        for email in emails:
            self.assertIsNotNone(blocklist.match(email, self.path), email)

    def assertNotBlocked(self, content, *emails):
        self.write(content)
        for email in emails:
            self.assertIsNone(blocklist.match(email, self.path), email)

    def test_matching_line(self):
        self.write("# comment\n\n*@outlook.com\nsmith+*@gmail.com\n")
        self.assertEqual(
            blocklist.match("smith+news@gmail.com", self.path), "smith+*@gmail.com"
        )

    def test_domain_pattern(self):
        self.assertBlocked(
            "*@outlook.com\n",
            "foo@outlook.com",
            "foo+bar@outlook.com",
            "foo@bar@outlook.com",
        )
        self.assertNotBlocked(
            "*@outlook.com\n",
            "foo@notoutlook.com",
            "foo@outlook.com.example",
            "outlook.com",
        )

    def test_subdomain_pattern(self):
        self.assertBlocked(
            "*@*.foobar.example\n",
            "foo@bar.foobar.example",
            "foo@bar.baz.foobar.example",
        )
        self.assertNotBlocked(
            "*@*.foobar.example\n",
            "foo@foobar.example",
            "foo@bar.foobar.example.org",
        )

    def test_local_part_pattern(self):
        self.assertBlocked("smith+*@gmail.com\n", "smith+news@gmail.com")
        self.assertNotBlocked(
            "smith+*@gmail.com\n",
            "smith@gmail.com",
            "jsmith+news@gmail.com",
            "smith+news@googlemail.com",
        )

    def test_case_insensitive(self):
        self.assertBlocked("*@OutLook.COM\n", "Foo@OUTLOOK.com", "FOO@outlook.com")
        self.assertBlocked("SMITH+*@gmail.com\n", "smith+News@Gmail.com")

    def test_question_mark(self):
        self.assertBlocked("user?@example.com\n", "user1@example.com")
        self.assertNotBlocked(
            "user?@example.com\n", "user@example.com", "user12@example.com"
        )

    def test_character_class(self):
        self.assertBlocked("[ab]*@example.com\n", "alice@example.com", "b@example.com")
        self.assertNotBlocked("[ab]*@example.com\n", "carol@example.com")
        self.assertBlocked("[!ab]*@example.com\n", "carol@example.com")
        self.assertNotBlocked("[!ab]*@example.com\n", "alice@example.com")

    def test_exception_pattern(self):
        content = "!smith+ok@gmail.com\nsmith+*@gmail.com\n"
        self.assertNotBlocked(content, "smith+ok@gmail.com", "SMITH+OK@gmail.com")
        self.assertBlocked(content, "smith+news@gmail.com")

    def test_exception_pattern_wildcards(self):
        content = "!*@good.foobar.example\n*@*.foobar.example\n"
        self.assertNotBlocked(content, "foo@good.foobar.example")
        self.assertBlocked(content, "foo@bad.foobar.example")

    def test_exception_pattern_order(self):
        # The first matching line decides, so an exception listed last has no effect
        self.assertBlocked(
            "smith+*@gmail.com\n!smith+ok@gmail.com\n", "smith+ok@gmail.com"
        )

    def test_exception_pattern_without_match(self):
        self.assertNotBlocked("!smith+ok@gmail.com\n", "foo@example.com")

    def test_multiple_patterns(self):
        content = "*@outlook.com\nsmith+*@gmail.com\n"
        self.assertBlocked(content, "foo@outlook.com", "smith+news@gmail.com")
        self.assertNotBlocked(content, "foo@example.com")

    def test_comments_and_blank_lines(self):
        content = "# *@example.com\n\n   \n  *@outlook.com  \n"
        self.assertBlocked(content, "foo@outlook.com")
        self.assertNotBlocked(content, "foo@example.com")

    def test_empty_file(self):
        self.assertNotBlocked("", "foo@example.com")

    def test_not_cached(self):
        self.assertNotBlocked("", "foo@blocked.example")
        self.assertBlocked("*@blocked.example\n", "foo@blocked.example")

    def test_file_not_found(self):
        # An absent blocklist is a normal state, not worth a warning on every request
        with self.assertLogs(blocklist.logger, "INFO") as logs:
            self.assertIsNone(blocklist.match("foo@example.com", self.path))
        self.assertEqual([record.levelname for record in logs.records], ["INFO"])

    def test_file_unreadable(self):
        with self.assertLogs(blocklist.logger, "WARNING"):
            self.assertIsNone(blocklist.match("foo@example.com", self.tmp_dir.name))

    def test_default_path(self):
        self.assertEqual(blocklist.PATH, "/etc/gatekeeper/email-blocklist.txt")


if __name__ == "__main__":
    unittest.main()
