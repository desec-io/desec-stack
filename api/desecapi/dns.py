import struct

import dns
import dns.rdtypes.txtbase, dns.rdtypes.svcbbase
import dns.rdtypes.ANY.CDS, dns.rdtypes.ANY.DLV, dns.rdtypes.ANY.DS


def _strip_quotes_decorator(func):
    return lambda *args, **kwargs: func(*args, **kwargs)[1:-1]


# Ensure that dnspython agrees with pdns' expectations for SVCB / HTTPS parameters.
# WARNING: This is a global side-effect. It can't be done by extending a class, because dnspython hardcodes the use of
# their dns.rdtypes.svcbbase.*Param classes in the global dns.rdtypes.svcbbase._class_for_key dictionary. We either have
# to globally mess with that dict and insert our custom class, or we just mess with their classes directly.
dns.rdtypes.svcbbase.ALPNParam.to_text = _strip_quotes_decorator(dns.rdtypes.svcbbase.ALPNParam.to_text)
dns.rdtypes.svcbbase.IPv4HintParam.to_text = _strip_quotes_decorator(dns.rdtypes.svcbbase.IPv4HintParam.to_text)
dns.rdtypes.svcbbase.IPv6HintParam.to_text = _strip_quotes_decorator(dns.rdtypes.svcbbase.IPv6HintParam.to_text)
dns.rdtypes.svcbbase.MandatoryParam.to_text = _strip_quotes_decorator(dns.rdtypes.svcbbase.MandatoryParam.to_text)
dns.rdtypes.svcbbase.PortParam.to_text = _strip_quotes_decorator(dns.rdtypes.svcbbase.PortParam.to_text)


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


# TODO remove when https://github.com/rthalley/dnspython/pull/625 is in the main codebase
class _DigestLengthMixin():
    _digest_length_by_type = {
        1: 20,  # SHA-1, RFC 3658 Sec. 2.4
        2: 32,  # SHA-256, RFC 4509 Sec. 2.2
        3: 32,  # GOST R 34.11-94, RFC 5933 Sec. 4 in conjunction with RFC 4490 Sec. 2.1
        4: 48,  # SHA-384, RFC 6605 Sec. 2
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            if self.digest_type == 0:  # reserved, RFC 3658 Sec. 2.4
                raise ValueError('digest type 0 is reserved')
            expected_length = _DigestLengthMixin._digest_length_by_type[self.digest_type]
        except KeyError:
            raise ValueError('unknown digest type')
        if len(self.digest) != expected_length:
            raise ValueError('digest length inconsistent with digest type')


@dns.immutable.immutable
class CDS(_DigestLengthMixin, dns.rdtypes.ANY.CDS.CDS):
    pass


@dns.immutable.immutable
class DLV(_DigestLengthMixin, dns.rdtypes.ANY.DLV.DLV):
    pass


@dns.immutable.immutable
class DS(_DigestLengthMixin, dns.rdtypes.ANY.DS.DS):
    pass
