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
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
  });

  it('shows each domain\'s delegation status', async () => {
    const {wrapper} = await mount();
    expect(row(wrapper, 'insecure.example').text()).toContain('No DNSSEC');
    expect(row(wrapper, 'secure.example').text()).toContain('Secure');
    expect(row(wrapper, 'mine.dedyn.io').find('.v-chip').text()).toBe('Secure');
  });

  it('offers a re-check only where one can tell something new', async () => {
    const {wrapper} = await mount();
    expect(row(wrapper, 'insecure.example').find('.button-recheck').exists()).toBe(true);
    expect(row(wrapper, 'secure.example').find('.button-recheck').exists()).toBe(true);
    expect(row(wrapper, 'mine.dedyn.io').find('.button-recheck').exists()).toBe(false);
    // The other actions are unaffected.
    expect(row(wrapper, 'mine.dedyn.io').find('.button-info').exists()).toBe(true);
  });

  it('leaves the re-check to the setup instructions on phones', async () => {
    vi.stubGlobal('innerWidth', 400);
    const {wrapper} = await mount();
    expect(row(wrapper, 'insecure.example').find('.button-recheck').exists()).toBe(false);
    expect(row(wrapper, 'insecure.example').find('.button-info').exists()).toBe(true);
    expect(wrapper.findAll('thead th').map(th => th.text())).not.toContain('Published');
  });

  async function recheck(wrapper, get, name, found, account) {
    const post = vi.spyOn(HTTP, 'post').mockResolvedValue({status: 200, data: found});
    get.mockImplementation(async url => {
      if (url === 'auth/account/') return {status: 200, data: account};
      throw new Error(`unexpected GET ${url}`);
    });
    await row(wrapper, name).find('.button-recheck').trigger('click');
    await flushPromises();
    return post;
  }

  it('updates the row and the limit when a re-check finds the domain secure', async () => {
    const {wrapper, get} = await mount();
    const found = {...SECURE, secure_since: '2026-10-24T12:00:00.000000Z'};
    const post = await recheck(wrapper, get, 'insecure.example', found, {limit_domains: 7, secure_domains: 3});

    expect(post).toHaveBeenCalledWith('domains/insecure.example/status/');
    expect(row(wrapper, 'insecure.example').text()).toContain('Secure');
    expect(wrapper.vm.limit_domains).toBe(7);
    expect(wrapper.vm.notification).toBe('<b>insecure.example</b> is now securely delegated. Your domain limit has grown to <b>7</b>.');
    expect(wrapper.vm.notificationColor).toBe('success');
  });

  it('updates the row and the limit when a re-check finds the domain no longer secure', async () => {
    const {wrapper, get} = await mount();
    await recheck(wrapper, get, 'secure.example', INSECURE, {limit_domains: 4, secure_domains: 1});

    expect(row(wrapper, 'secure.example').text()).toContain('No DNSSEC');
    expect(wrapper.vm.limit_domains).toBe(4);
    expect(wrapper.vm.notification).toBe('<b>secure.example</b> is no longer securely delegated. Your domain limit has dropped to <b>4</b>.');
    expect(wrapper.vm.notificationColor).toBe('warning');
  });

  it('mentions the limit only when it changed', async () => {
    // As for accounts whose limit support has set.
    const {wrapper, get} = await mount();
    await recheck(wrapper, get, 'insecure.example', SECURE, {limit_domains: 5, secure_domains: 3});
    expect(wrapper.vm.notification).toBe('<b>insecure.example</b> is now securely delegated.');
  });

  it('tells when a re-check could not be completed', async () => {
    const {wrapper, get} = await mount();
    const failed = {...SECURE, nameserver_status: 'error', security_status: 'error', nameservers: []};
    await recheck(wrapper, get, 'secure.example', failed, {limit_domains: 5, secure_domains: 2});

    expect(row(wrapper, 'secure.example').text()).toContain('Secure');
    expect(wrapper.vm.notification).toBe('We could not complete the check of secure.example. Please try again in a few minutes.');
    expect(wrapper.vm.notificationColor).toBe('warning');
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

  it('explains the limit with the number of securely delegated domains', async () => {
    const {wrapper} = await mount();
    expect(wrapper.vm.createText).toContain('You have 2 of 5 domains left.');
    expect(wrapper.vm.createText).toContain('<b>2</b> of your <b>3</b> domains are correctly delegated, with DNSSEC enabled (see <i>Delegation</i> column). Each domain you secure raises your limit.');
    expect(wrapper.vm.createText).toContain('<a href="/faq/#domain-limit" target="_blank">How does the limit work?</a>');
    expect(wrapper.vm.createWarningText).toBe('');
  });

  it('says what raises the limit once it is reached', async () => {
    const {wrapper} = await mount({account: {limit_domains: 3, secure_domains: 1}});
    expect(wrapper.vm.createWarningText).toBe(
        'Domain limit reached. <b>1</b> of your <b>3</b> domains is correctly delegated, with DNSSEC enabled (see <i>Delegation</i> column). Securing another one will raise your limit.'
        + ' <a href="/faq/#domain-limit" target="_blank">How does the limit work?</a>',
    );
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
