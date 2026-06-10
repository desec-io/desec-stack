import base64
import re

import dns.dnssec
from cryptography.hazmat.primitives.asymmetric import ec


def parse_csk_private_key(private_key: str) -> dict:
    if not private_key or not private_key.strip():
        raise ValueError("Missing private key material")

    algorithm = None
    private_b64 = None
    for line in private_key.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("algorithm:"):
            match = re.search(r"\b(\d+)\b", line)
            if match:
                algorithm = int(match.group(1))
        elif line.lower().startswith("privatekey:"):
            private_b64 = line.split(":", 1)[1].strip()

    if algorithm is None:
        raise ValueError("Missing algorithm in private key")
    if private_b64 is None:
        raise ValueError("Missing PrivateKey in private key")

    if algorithm != 13:
        raise ValueError("Unsupported algorithm")

    try:
        private_bytes = base64.b64decode(private_b64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 private key") from exc

    if len(private_bytes) > 32:
        raise ValueError("Invalid private key length")
    if len(private_bytes) < 32:
        private_bytes = private_bytes.rjust(32, b"\x00")

    private_value = int.from_bytes(private_bytes, "big")
    if private_value == 0:
        raise ValueError("Invalid private key value")

    private_key_obj = ec.derive_private_key(private_value, ec.SECP256R1())
    dnskey = dns.dnssec.make_dnskey(
        private_key_obj.public_key(), algorithm=13, flags=257, protocol=3
    ).to_text()

    return {
        "algorithm": algorithm,
        "dnskey": dnskey,
    }
