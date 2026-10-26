import { flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { reactive } from 'vue';

import { mountWithVuetify } from '@/test/vuetify';
import DomainSetupDialog from './DomainSetupDialog.vue';

const INSECURE = {
  secure_since: null,
  checked: '2026-10-24T08:00:00.000000Z',
  nameserver_status: 'correctly_delegated',
  security_status: 'insecure',
  nameservers: ['ns1.desec.io.'],
};

async function mount(props) {
  const wrapper = mountWithVuetify(DomainSetupDialog, {
    props: {
      domain: 'example.com',
      ds: ['1 13 2 abc'],
      dnskey: ['257 3 13 xyz'],
      item: {name: 'example.com', status: INSECURE},
      ...props,
    },
    attachTo: document.body,
  });
  await flushPromises();
  return wrapper;
}

function statusBlock() {
  return document.querySelector('.delegation-status-block');
}

describe('DomainSetupDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.stubEnv('VITE_APP_LOCAL_PUBLIC_SUFFIXES', 'dedyn.io');
    vi.stubEnv('VITE_APP_DESECSTACK_NS', 'ns1.desec.io ns2.desec.org');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete navigator.clipboard;
    document.body.innerHTML = '';
  });

  it('explains the delegation status above the instructions', async () => {
    await mount();
    const text = statusBlock().textContent;
    expect(text).toContain('No DNSSEC');
    expect(text).toContain('example.com is delegated to deSEC, but the parent zone has no DS records for it.');
    expect(text).toContain('Copy request for your registrar');
    expect(text).toContain('Re-check');
  });

  it('asks for a re-check through its parent', async () => {
    const wrapper = await mount();
    statusBlock().querySelector('button').click();
    expect(wrapper.emitted('recheck')).toHaveLength(1);
  });

  it('shows that a check is under way, and follows its result', async () => {
    const item = reactive({name: 'example.com', status: INSECURE});
    const checking = reactive({'example.com': true});
    await mount({item, checking});
    expect(statusBlock().textContent).toContain('Checking…');
    expect(statusBlock().textContent).toContain('This usually takes a few seconds.');

    delete checking['example.com'];
    item.status = {...INSECURE, secure_since: '2026-10-24T12:00:00Z', security_status: 'secure'};
    await flushPromises();
    expect(statusBlock().textContent).toContain('Secure');
    expect(statusBlock().textContent).not.toContain('Checking…');
    expect(statusBlock().textContent).not.toContain('Re-check');
  });

  it('copies a request for the registrar', async () => {
    const writeText = vi.fn().mockResolvedValue();
    Object.defineProperty(navigator, 'clipboard', {value: {writeText}, configurable: true});
    await mount();
    [...statusBlock().querySelectorAll('button')].find(b => b.textContent.includes('Copy request')).click();
    await flushPromises();
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('Please publish the following DS records for example.com:\n\n1 13 2 abc'));
    expect(statusBlock().textContent).toContain('Copied');
  });

  it('shows no status for a domain just created', async () => {
    await mount({isNew: true});
    expect(statusBlock()).toBeNull();
  });

  it('shows no status for domains under a local public suffix', async () => {
    await mount({domain: 'mine.dedyn.io', item: {name: 'mine.dedyn.io', status: {...INSECURE, checked: null}}});
    expect(statusBlock()).toBeNull();
  });
});
