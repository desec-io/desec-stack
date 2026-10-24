import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  compareBySecurity,
  delegationSummary,
  isLocallyRegistrable,
  isSecure,
  isUnderLocalPublicSuffix,
} from './delegation';

const SUFFIXES = ['dedyn.io'];

function status(overrides = {}) {
  return {
    secure_since: null,
    checked: '2026-10-24T08:00:00.000000Z',
    nameserver_status: 'correctly_delegated',
    security_status: 'insecure',
    nameservers: ['ns1.desec.io.', 'ns2.desec.org.'],
    ...overrides,
  };
}

const SECURE = {
  secure_since: '2026-09-01T12:00:00.000000Z',
  security_status: 'secure',
};

describe('local public suffixes', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('recognizes domains under a local public suffix at any depth', () => {
    expect(isUnderLocalPublicSuffix('mine.dedyn.io', SUFFIXES)).toBe(true);
    expect(isUnderLocalPublicSuffix('sub.mine.dedyn.io', SUFFIXES)).toBe(true);
    expect(isUnderLocalPublicSuffix('dedyn.io', SUFFIXES)).toBe(false);
    expect(isUnderLocalPublicSuffix('notdedyn.io', SUFFIXES)).toBe(false);
    expect(isUnderLocalPublicSuffix('dedyn.io.example.com', SUFFIXES)).toBe(false);
    expect(isUnderLocalPublicSuffix('example.com', SUFFIXES)).toBe(false);
  });

  it('recognizes locally registrable domains as immediate children only', () => {
    expect(isLocallyRegistrable('mine.dedyn.io', SUFFIXES)).toBe(true);
    expect(isLocallyRegistrable('sub.mine.dedyn.io', SUFFIXES)).toBe(false);
    expect(isLocallyRegistrable('dedyn.io', SUFFIXES)).toBe(false);
    expect(isLocallyRegistrable('notdedyn.io', SUFFIXES)).toBe(false);
  });

  it('reads the suffixes from the environment by default', () => {
    vi.stubEnv('VITE_APP_LOCAL_PUBLIC_SUFFIXES', 'dedyn.io dedyn.example');
    expect(isUnderLocalPublicSuffix('mine.dedyn.example')).toBe(true);
    expect(isLocallyRegistrable('mine.dedyn.io')).toBe(true);
  });

  it('copes with the suffixes missing from the environment', () => {
    vi.stubEnv('VITE_APP_LOCAL_PUBLIC_SUFFIXES', undefined);
    expect(isUnderLocalPublicSuffix('mine.dedyn.io')).toBe(false);
  });
});

describe('isSecure', () => {
  it('goes by secure_since', () => {
    expect(isSecure(null)).toBe(false);
    expect(isSecure(status())).toBe(false);
    expect(isSecure(status(SECURE))).toBe(true);
    // Error-immune: the latest check failing does not undo it.
    expect(isSecure(status({...SECURE, security_status: 'error', nameserver_status: 'error'}))).toBe(true);
  });
});

describe('delegationSummary', () => {
  it('maps each state', () => {
    const cases = [
      [status(SECURE), 'secure', 'Secure', 'success'],
      [status({checked: null, nameserver_status: null, security_status: null, nameservers: []}), 'unchecked', 'Not checked yet', 'grey'],
      [null, 'unchecked', 'Not checked yet', 'grey'],
      [status({security_status: 'misconfigured'}), 'misconfigured', 'DNSSEC broken', 'error'],
      [status({nameserver_status: 'not_delegated', security_status: null, nameservers: []}), 'not_delegated', 'Not delegated', 'grey'],
      [status({nameserver_status: 'other_provider', nameservers: ['ns.other.example.']}), 'other_provider', 'Delegated elsewhere', 'warning'],
      [status(), 'insecure', 'No DNSSEC', 'warning'],
      [status({nameserver_status: 'multi_provider'}), 'insecure', 'No DNSSEC', 'warning'],
      [status({security_status: 'error'}), 'error', 'Check failed', 'grey'],
      [status({nameserver_status: 'error', security_status: 'error', nameservers: []}), 'error', 'Check failed', 'grey'],
    ];
    for (const [input, state, label, color] of cases) {
      const summary = delegationSummary(input, 'example.com');
      expect(summary.state, JSON.stringify(input)).toBe(state);
      expect(summary.label).toBe(label);
      expect(summary.color).toBe(color);
      expect(summary.icon).toBeTruthy();
      expect(summary.hint).toBeTruthy();
      expect(summary.details.length).toBeGreaterThan(0);
    }
  });

  it('keeps a secure domain secure when the latest check failed, and says so', () => {
    const summary = delegationSummary(
        status({...SECURE, security_status: 'error', nameserver_status: 'error', nameservers: []}),
        'example.com',
    );
    expect(summary.state).toBe('secure');
    expect(summary.hint).toMatch(/could not complete the most recent check/);
    expect(summary.details.join(' ')).toMatch(/keeps counting as securely delegated/);
  });

  it('decides by the nameserver status when undelegated', () => {
    // The API reports no security status then, as the check asked about the
    // parent instead.
    expect(delegationSummary(status({nameserver_status: 'not_delegated', security_status: null})).state).toBe('not_delegated');
  });

  it('reports broken DNSSEC wherever the domain is delegated', () => {
    expect(delegationSummary(status({nameserver_status: 'other_provider', security_status: 'misconfigured'})).state).toBe('misconfigured');
  });

  it('does not claim a delegation to deSEC when the delegation is unknown', () => {
    // An unsigned parent settles "insecure" even when the delegation cannot
    // be read.
    expect(delegationSummary(status({nameserver_status: 'error', security_status: 'insecure'})).state).toBe('error');
  });

  it('lists the nameservers a domain is delegated to elsewhere', () => {
    const summary = delegationSummary(status({
      nameserver_status: 'other_provider',
      nameservers: ['ns1.other.example.', 'ns2.other.example.'],
    }), 'example.com');
    expect(summary.hint).toContain('ns1.other.example, ns2.other.example');
    expect(summary.details[0]).toContain('example.com is delegated to other nameservers: ns1.other.example, ns2.other.example.');
  });

  it('asks users without DNSSEC to take it to their registrar', () => {
    const details = delegationSummary(status(), 'example.com').details.join(' ');
    expect(details).toContain('example.com is delegated to deSEC, but the parent zone has no DS records for it.');
    expect(details).toContain('please ask them to change that');
  });
});

describe('compareBySecurity', () => {
  it('sorts domains that are not secure first, then by name', () => {
    vi.stubEnv('VITE_APP_LOCAL_PUBLIC_SUFFIXES', 'dedyn.io');
    const domains = [
      {name: 'b.example', status: status(SECURE)},
      {name: 'mine.dedyn.io', status: status({checked: null})},
      {name: 'c.example', status: status()},
      {name: 'a.example', status: status({checked: null})},
    ];
    expect(domains.sort(compareBySecurity).map(d => d.name)).toEqual(
        ['a.example', 'c.example', 'b.example', 'mine.dedyn.io'],
    );
    vi.unstubAllEnvs();
  });
});
