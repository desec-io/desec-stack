import struct

import dns
import dns.rdtypes.txtbase


@dns.immutable.immutable
class LongQuotedTXT(dns.rdtypes.txtbase.TXTBase):
    """
    A TXT record like RFC 1035, but
    - allows arbitrarily long tokens, and
    - all tokens must be quoted.
    """

    def __init__(self, rdclass, rdtype, strings):
        # Same as in parent class, but with max_length=None. Note that we are calling __init__ from the grandparent.
        super(dns.rdtypes.txtbase.TXTBase, self).__init__(rdclass, rdtype)
        self.strings = self._as_tuple(strings,
                                      lambda x: self._as_bytes(x, True, max_length=None))

    @classmethod
    def from_text(cls, rdclass, rdtype, tok, origin=None, relativize=True):
        strings = []
        for token in tok.get_remaining():
            token = token.unescape_to_bytes()
            # The 'if' below is always true in the current code, but we
            # are leaving this check in in case things change some day.
            if not token.is_quoted_string():
                raise dns.exception.SyntaxError("Content must be quoted.")
            strings.append(token.value)
        if len(strings) == 0:
            raise dns.exception.UnexpectedEnd
        return cls(rdclass, rdtype, strings)

    def _to_wire(self, file, compress=None, origin=None, canonicalize=False):
        for long_s in self.strings:
            for s in [long_s[i:i+255] for i in range(0, max(len(long_s), 1), 255)]:
                l = len(s)
                assert l < 256
                file.write(struct.pack('!B', l))
                file.write(s)
