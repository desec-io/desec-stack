import { describe, expect, it } from 'vitest';

import { ip4Address, ip6Address, ipAddressOrSubnet } from './ipAddressValidators';

function validate(validator, value) {
  return validator.$validator(value);
}

describe('ipAddressValidators', () => {
  it('validates IPv4 addresses', () => {
    expect(validate(ip4Address, '203.0.113.11')).toBe(true);
    expect(validate(ip4Address, '0.0.0.0')).toBe(true);
    expect(validate(ip4Address, '255.255.255.255')).toBe(true);

    expect(validate(ip4Address, '2001:db8::1')).toBe(false);
    expect(validate(ip4Address, '256.0.0.1')).toBe(false);
    expect(validate(ip4Address, '192.0.2')).toBe(false);
    expect(validate(ip4Address, '192.0.2.01')).toBe(false);
  });

  it('validates IPv6 addresses', () => {
    expect(validate(ip6Address, '2001:db8::1')).toBe(true);
    expect(validate(ip6Address, '::1')).toBe(true);
    expect(validate(ip6Address, '::')).toBe(true);
    expect(validate(ip6Address, '2001:db8:0:0:0:0:2:1')).toBe(true);
    expect(validate(ip6Address, '::ffff:192.0.2.128')).toBe(true);
    expect(validate(ip6Address, '2001:db8::192.0.2.128')).toBe(true);

    expect(validate(ip6Address, '203.0.113.11')).toBe(false);
    expect(validate(ip6Address, '2001:db8:::1')).toBe(false);
    expect(validate(ip6Address, '2001:db8::1::2')).toBe(false);
    expect(validate(ip6Address, '2001:db8::g')).toBe(false);
    expect(validate(ip6Address, 'fe80::1%eth0')).toBe(false);
  });

  it('validates IP addresses with optional subnet prefixes', () => {
    expect(validate(ipAddressOrSubnet, '192.0.2.0')).toBe(true);
    expect(validate(ipAddressOrSubnet, '192.0.2.0/24')).toBe(true);
    expect(validate(ipAddressOrSubnet, '2001:db8::')).toBe(true);
    expect(validate(ipAddressOrSubnet, '2001:db8::/32')).toBe(true);
    expect(validate(ipAddressOrSubnet, '::ffff:192.0.2.128/128')).toBe(true);

    expect(validate(ipAddressOrSubnet, '192.0.2.0/33')).toBe(false);
    expect(validate(ipAddressOrSubnet, '2001:db8::/129')).toBe(false);
    expect(validate(ipAddressOrSubnet, '2001:db8::/-1')).toBe(false);
    expect(validate(ipAddressOrSubnet, '2001:db8::/32/32')).toBe(false);
  });
});
