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
    expect(row(wrapper, 'mine.dedyn.io').find('.v-chip').text()).toBe('Secure');
  });

  it('makes room for the status on phones', async () => {
    // Everything below 2000px counts as xs here.
    const {wrapper} = await mount({vuetify: {display: {thresholds: {sm: 2000}}}});
    expect(wrapper.findAll('thead th').map(th => th.text())).not.toContain('Published');
    expect(row(wrapper, 'insecure.example').find('.button-info').exists()).toBe(true);
  });

  it('does not match every row when searching for "object"', async () => {
    const {wrapper} = await mount();
    wrapper.vm.search = 'object';
    await flushPromises();
    expect(wrapper.findAll('tr.crud-item')).toHaveLength(0);
  });

  it('sorts by the clicked column, keeping the previous order among ties', async () => {
    const {wrapper} = await mount();
    const MISCONFIGURED = {...INSECURE, security_status: 'misconfigured'};
    const published = (d, month) => ({...d, published: `2026-0${month}-01T00:00:00Z`});
    wrapper.vm.rows = [
      published(domain('a.example', INSECURE), 3),
      published(domain('b.example', SECURE), 1),
      published(domain('c.example', INSECURE), 2),
      published(domain('d.example', SECURE), 4),
      published(domain('e.example', MISCONFIGURED), 5),
    ];
    await flushPromises();
    const names = () => wrapper.findAll('tr.crud-item').map(tr => tr.find('td').text().trim());
    const header = title => wrapper.findAll('thead th').find(th => th.text().includes(title));
    const sortBy = async title => {
      await header(title).find('.v-data-table-header__content').trigger('click');
      await flushPromises();
    };

    await sortBy('Published');
    expect(names()).toEqual(['b.example', 'c.example', 'a.example', 'd.example', 'e.example']);
    // Within each state, still by publication
    await sortBy('Delegation');
    expect(names()).toEqual(['e.example', 'c.example', 'a.example', 'b.example', 'd.example']);

    // Within each state, by name instead
    await sortBy('Name');
    await sortBy('Delegation');
    expect(names()).toEqual(['e.example', 'a.example', 'c.example', 'b.example', 'd.example']);
    const rank = title => header(title).find('.v-data-table-header__sort-badge').text();
    expect(['Delegation', 'Name', 'Published'].map(rank)).toEqual(['1', '2', '3']);

    // The primary column reverses; ties stay by name
    await sortBy('Delegation');
    expect(names()).toEqual(['b.example', 'd.example', 'a.example', 'c.example', 'e.example']);
    await sortBy('Delegation');
    expect(names()).toEqual(['e.example', 'a.example', 'c.example', 'b.example', 'd.example']);
  });
});
