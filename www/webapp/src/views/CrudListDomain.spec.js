import { flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mountWithVuetify } from '@/test/vuetify';
import { HTTP } from '@/utils';
import CrudListDomain from './CrudListDomain.vue';

const UNCHECKED = {secure_since: null, checked: null, nameserver_status: null, security_status: null, nameservers: []};
const INSECURE = {
  ...UNCHECKED,
  checked: '2026-10-24T08:00:00.000000Z',
  nameserver_status: 'correctly_delegated',
  security_status: 'insecure',
  nameservers: ['ns1.desec.io.'],
};
const SECURE = {...INSECURE, secure_since: '2026-09-01T12:00:00.000000Z', security_status: 'secure'};

function domain(name, status) {
  return {name, status, created: '2026-01-01T00:00:00Z', published: '2026-01-01T00:00:00Z', minimum_ttl: 3600, touched: '2026-01-01T00:00:00Z'};
}

async function mount({account = {limit_domains: 5, secure_domains: 2}, vuetify} = {}) {
  const rows = [
    domain('insecure.example', INSECURE),
    domain('secure.example', SECURE),
    domain('mine.dedyn.io', UNCHECKED),
  ];
  const get = vi.spyOn(HTTP, 'get').mockImplementation(async url => {
    if (url === 'domains/') return {status: 200, data: rows};
    if (url === 'auth/account/') return {status: 200, data: account};
    throw new Error(`unexpected GET ${url}`);
  });
  const wrapper = mountWithVuetify(CrudListDomain, {
    vuetify,
    global: {
      mocks: {
        $route: {params: {}, fullPath: '/domains'},
        $router: {push: vi.fn()},
      },
    },
    attachTo: document.body,
  });
  await flushPromises();
  return {wrapper, get, rows};
}

function row(wrapper, name) {
  return wrapper.findAll('tr.crud-item').find(tr => tr.find('td').text().trim() === name);
}

describe('CrudListDomain', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.stubEnv('VITE_APP_LOCAL_PUBLIC_SUFFIXES', 'dedyn.io');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    document.body.innerHTML = '';
  });

  it('shows each domain\'s delegation status', async () => {
    const {wrapper} = await mount();
    expect(row(wrapper, 'insecure.example').text()).toContain('No DNSSEC');
    expect(row(wrapper, 'secure.example').text()).toContain('Secure');
    expect(row(wrapper, 'mine.dedyn.io').find('.v-chip').exists()).toBe(false);
  });

  it('offers a re-check only where one can tell something new', async () => {
    const {wrapper} = await mount();
    expect(row(wrapper, 'insecure.example').find('.button-recheck').exists()).toBe(true);
    expect(row(wrapper, 'secure.example').find('.button-recheck').exists()).toBe(false);
    expect(row(wrapper, 'mine.dedyn.io').find('.button-recheck').exists()).toBe(false);
    // The other actions are unaffected.
    expect(row(wrapper, 'secure.example').find('.button-info').exists()).toBe(true);
  });

  it('leaves the re-check to the setup instructions on phones', async () => {
    // Everything below 2000px counts as xs here.
    const {wrapper} = await mount({vuetify: {display: {thresholds: {sm: 2000}}}});
    expect(row(wrapper, 'insecure.example').find('.button-recheck').exists()).toBe(false);
    expect(row(wrapper, 'insecure.example').find('.button-info').exists()).toBe(true);
    expect(wrapper.findAll('thead th').map(th => th.text())).not.toContain('Published');
  });

  it('updates the row and the limit when a re-check finds the domain secure', async () => {
    const {wrapper, get} = await mount();
    const found = {...SECURE, secure_since: '2026-10-24T12:00:00.000000Z'};
    const post = vi.spyOn(HTTP, 'post').mockResolvedValue({status: 200, data: found});
    get.mockImplementation(async url => {
      if (url === 'auth/account/') return {status: 200, data: {limit_domains: 7, secure_domains: 3}};
      throw new Error(`unexpected GET ${url}`);
    });

    await row(wrapper, 'insecure.example').find('.button-recheck').trigger('click');
    await flushPromises();

    expect(post).toHaveBeenCalledWith('domains/insecure.example/status/');
    expect(row(wrapper, 'insecure.example').text()).toContain('Secure');
    expect(row(wrapper, 'insecure.example').find('.button-recheck').exists()).toBe(false);
    expect(wrapper.vm.limit_domains).toBe(7);
    expect(wrapper.vm.notification).toBe('insecure.example is now securely delegated. Your domain limit is now 7.');
  });

  it('tells when a re-check is throttled, without an error', async () => {
    const {wrapper} = await mount();
    const error = Object.assign(new Error('throttled'), {response: {status: 429, headers: {'retry-after': '42'}}});
    vi.spyOn(HTTP, 'post').mockRejectedValue(error);

    await row(wrapper, 'insecure.example').find('.button-recheck').trigger('click');
    await flushPromises();

    expect(wrapper.vm.notification).toBe('You can re-check insecure.example again in 42 seconds.');
    expect(wrapper.vm.notificationColor).toBe('info');
    expect(wrapper.vm.snackbar).toBe(false);
    expect(wrapper.vm.checking).toEqual({});
  });

  it('does not match every row when searching for "object"', async () => {
    const {wrapper} = await mount();
    wrapper.vm.search = 'object';
    await flushPromises();
    expect(wrapper.findAll('tr.crud-item')).toHaveLength(0);
  });
});
