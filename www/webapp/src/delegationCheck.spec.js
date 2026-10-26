import { describe, expect, it, vi } from 'vitest';

import { POLL_TIMEOUT, recheckDelegation } from './delegationCheck';

const REQUESTED = '2026-10-24T12:00:00.500000Z';

function current(overrides = {}) {
  return {
    secure_since: null,
    checked: '2026-10-24T11:00:00.000000Z',
    nameserver_status: 'correctly_delegated',
    security_status: 'insecure',
    nameservers: ['ns1.desec.io.'],
    ...overrides,
  };
}

function client({post, gets = []}) {
  const get = vi.fn();
  for (const data of gets) {
    get.mockResolvedValueOnce({status: 200, data});
  }
  get.mockResolvedValue({status: 200, data: current()});
  return {post: vi.fn().mockResolvedValue(post), get};
}

const accepted = {status: 202, data: {...current(), requested: REQUESTED}};

describe('recheckDelegation', () => {
  it('is done at once when the API answers from what it knows', async () => {
    const http = client({post: {status: 200, data: current({secure_since: '2026-09-01T00:00:00Z'})}});
    const sleep = vi.fn();
    const result = await recheckDelegation(http, 'example.com', {sleep});
    expect(http.post).toHaveBeenCalledWith('domains/example.com/status/');
    expect(result).toEqual({status: current({secure_since: '2026-09-01T00:00:00Z'}), done: true});
    expect(sleep).not.toHaveBeenCalled();
    expect(http.get).not.toHaveBeenCalled();
  });

  it('polls until a check newer than the request is in', async () => {
    const result_ = current({checked: '2026-10-24T12:00:03.000000Z', security_status: 'secure', secure_since: '2026-10-24T12:00:03.000000Z'});
    const http = client({post: accepted, gets: [current(), current(), result_]});
    const sleep = vi.fn().mockResolvedValue();
    const onRequested = vi.fn();
    const result = await recheckDelegation(http, 'example.com', {sleep, onRequested});

    expect(onRequested).toHaveBeenCalledWith(current());
    expect(http.get).toHaveBeenCalledTimes(3);
    expect(http.get).toHaveBeenCalledWith('domains/example.com/status/');
    expect(sleep.mock.calls.map(([ms]) => ms)).toEqual([2000, 3000, 5000]);
    expect(result).toEqual({status: result_, done: true});
  });

  it('gives up after the timeout, keeping the status it had', async () => {
    const http = client({post: accepted});
    const sleep = vi.fn().mockResolvedValue();
    const result = await recheckDelegation(http, 'example.com', {sleep});

    const waited = sleep.mock.calls.reduce((sum, [ms]) => sum + ms, 0);
    expect(waited).toBeLessThanOrEqual(POLL_TIMEOUT * 1000);
    expect(waited).toBeGreaterThan((POLL_TIMEOUT - 15) * 1000);
    expect(http.get).toHaveBeenCalledTimes(sleep.mock.calls.length);
    expect(result).toEqual({status: current(), done: false});
  });

  it('stops waiting when asked to', async () => {
    const http = client({post: accepted});
    const sleep = vi.fn().mockResolvedValue();
    const result = await recheckDelegation(http, 'example.com', {sleep, shouldStop: () => true});
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(http.get).not.toHaveBeenCalled();
    expect(result.done).toBe(false);
  });

  it('passes request errors on', async () => {
    const error = Object.assign(new Error('throttled'), {response: {status: 429, headers: {'retry-after': '42'}}});
    const http = {post: vi.fn().mockRejectedValue(error), get: vi.fn()};
    await expect(recheckDelegation(http, 'example.com', {sleep: vi.fn()})).rejects.toBe(error);
  });
});
