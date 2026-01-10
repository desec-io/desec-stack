import { helpers } from '@vuelidate/validators';

function isIPv4Address(value) {
  if (!helpers.req(value)) {
    return true;
  }
  if (typeof value !== 'string') {
    return false;
  }

  const parts = value.split('.');
  return parts.length === 4 && parts.every((part) => {
    if (!/^\d+$/.test(part) || (part.length > 1 && part.startsWith('0'))) {
      return false;
    }
    const number = Number(part);
    return number >= 0 && number <= 255;
  });
}

function isIPv6HexGroup(value) {
  return /^[0-9a-fA-F]{1,4}$/.test(value);
}

function isIPv6Address(value) {
  if (!helpers.req(value)) {
    return true;
  }
  if (typeof value !== 'string' || value.includes('%')) {
    return false;
  }

  let address = value;
  if (address.includes('.')) {
    const lastColon = address.lastIndexOf(':');
    if (lastColon === -1 || !isIPv4Address(address.slice(lastColon + 1))) {
      return false;
    }
    address = `${address.slice(0, lastColon)}:0:0`;
  }

  const compressionMatches = address.match(/::/g) || [];
  if (compressionMatches.length > 1) {
    return false;
  }

  if (compressionMatches.length === 1) {
    const [left, right] = address.split('::');
    const groups = [
      ...(left ? left.split(':') : []),
      ...(right ? right.split(':') : []),
    ];
    return groups.length < 8 && groups.every(isIPv6HexGroup);
  }

  const groups = address.split(':');
  return groups.length === 8 && groups.every(isIPv6HexGroup);
}

function isPrefixLength(value, max) {
  return /^\d+$/.test(value) && Number(value) >= 0 && Number(value) <= max;
}

function isIPAddressOrSubnet(value) {
  if (!helpers.req(value)) {
    return true;
  }
  if (typeof value !== 'string') {
    return false;
  }

  const parts = value.split('/');
  if (parts.length > 2) {
    return false;
  }

  const [address, prefix] = parts;
  const isIPv4 = isIPv4Address(address);
  const isIPv6 = isIPv6Address(address);
  if (prefix === undefined) {
    return isIPv4 || isIPv6;
  }
  return (isIPv4 && isPrefixLength(prefix, 32)) || (isIPv6 && isPrefixLength(prefix, 128));
}

export const ip4Address = helpers.withParams({ type: 'ip4Address' }, isIPv4Address);
export const ip6Address = helpers.withParams({ type: 'ip6Address' }, isIPv6Address);
export const ipAddressOrSubnet = helpers.withParams({ type: 'ipAddressOrSubnet' }, isIPAddressOrSubnet);
