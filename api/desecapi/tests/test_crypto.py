from math import log
import time

from django.test import TestCase

from desecapi import crypto


class CryptoTestCase(TestCase):
    context = "desecapi.tests.test_crypto"

    def test_retrieved_key_is_reproducible(self):
        keys = (
            crypto.retrieve_key(label="test", context=self.context) for _ in range(2)
        )
        self.assertEqual(*keys)

    def test_retrieved_key_depends_on_secret(self):
        keys = []
        for secret in ["abcdefgh", "hgfedcba"]:
            with self.settings(SECRET_KEY=secret):
                keys.append(crypto.retrieve_key(label="test", context=self.context))
        self.assertNotEqual(*keys)

    def test_retrieved_key_depends_on_label(self):
        keys = (
            crypto.retrieve_key(label=f"test_{i}", context=self.context)
            for i in range(2)
        )
        self.assertNotEqual(*keys)

    def test_retrieved_key_depends_on_context(self):
        keys = (
            crypto.retrieve_key(label="test", context=f"{self.context}_{i}")
            for i in range(2)
        )
        self.assertNotEqual(*keys)

    def test_encrypt_has_high_entropy(self):
        def entropy(value: str):
            result = 0
            counts = [value.count(char) for char in set(value)]
            for count in counts:
                count /= len(value)
                result -= count * log(count, 2)
            return result * len(value)

        ciphertext = crypto.encrypt(b"test", context=self.context)
        self.assertGreater(entropy(ciphertext), 100)  # arbitrary

    def test_encrypt_decrypt(self):
        plain = b"test"
        ciphertext = crypto.encrypt(plain, context=self.context)
        timestamp, decrypted = crypto.decrypt(ciphertext, context=self.context)
        self.assertEqual(plain, decrypted)
        self.assertTrue(0 <= time.time() - timestamp <= 1)

    def test_encrypt_decrypt_raises_on_tampering(self):
        ciphertext = crypto.encrypt(b"test", context=self.context)

        with self.assertRaises(ValueError):
            ciphertext_decoded = ciphertext.decode()
            ciphertext_tampered = (
                ciphertext_decoded[:30] + "TAMPERBEEF" + ciphertext_decoded[40:]
            ).encode()
            crypto.decrypt(ciphertext_tampered, context=self.context)

        with self.assertRaises(ValueError):
            crypto.decrypt(ciphertext, context=f"{self.context}2")
