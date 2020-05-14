import struct

import dns
import dns.rdtypes.txtbase
import dns.rdtypes.ANY.OPENPGPKEY


class LongQuotedTXT(dns.rdtypes.txtbase.TXTBase):
    """
    A TXT record like RFC 1035, but
    - allows arbitrarily long tokens, and
    - all tokens must be quoted.
    """

    @classmethod
    def from_text(cls, rdclass, rdtype, tok, origin=None, relativize=True):
        strings = []
        while 1:
            token = tok.get().unescape()
            if token.is_eol_or_eof():
                break
            if not token.is_quoted_string():
                raise dns.exception.SyntaxError("Content must be quoted.")
            value = token.value
            if isinstance(value, bytes):
                strings.append(value)
            else:
                strings.append(value.encode())
        if len(strings) == 0:
            raise dns.exception.UnexpectedEnd
        return cls(rdclass, rdtype, strings)

    def to_wire(self, file, compress=None, origin=None):
        for long_s in self.strings:
            for s in [long_s[i:i+255] for i in range(0, max(len(long_s), 1), 255)]:
                l = len(s)
                assert l < 256
                file.write(struct.pack('!B', l))
                file.write(s)


class OPENPGPKEY(dns.rdtypes.ANY.OPENPGPKEY.OPENPGPKEY):
    # TODO remove when https://github.com/rthalley/dnspython/commit/d6a95982fcd454a10467260bfb874c3c9d31d06f was
    #  released

    def to_text(self, origin=None, relativize=True, **kw):
        return super().to_text(origin, relativize, **kw).replace(' ', '')
