import { flushPromises } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { mountWithVuetify } from '@/test/vuetify';
import FaqPage from './FaqPage.vue';

async function mount(hash = '') {
  const push = vi.fn();
  const wrapper = mountWithVuetify(FaqPage, {
    global: {
      mocks: {
        $route: {hash, fullPath: `/faq/${hash}`},
        $router: {push},
      },
    },
    attachTo: document.body,
  });
  await flushPromises();
  return {wrapper, push};
}

function anchors(sections) {
  return sections.flatMap(section => [
    section.id,
    ...section.questions.flatMap(q => [q.id, ...(q.guide ? [q.guide.id] : [])]),
  ]);
}

function inPageLinks(sections) {
  const html = sections
      .flatMap(section => section.questions)
      .flatMap(q => [q.a, q.guide?.text || ''])
      .join('');
  return [...html.matchAll(/href="#([^"]+)"/g)].map(match => match[1]);
}

describe('FaqPage', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('gives every section, question, and guide its own anchor', async () => {
    const {wrapper} = await mount();
    const ids = anchors(wrapper.vm.sections);
    expect(new Set(ids).size).toBe(ids.length);
    ids.filter(id => !id.endsWith('-guide')).forEach(id => expect(document.getElementById(id)).not.toBeNull());
  });

  it('links only to anchors that exist', async () => {
    const {wrapper} = await mount();
    const ids = anchors(wrapper.vm.sections);
    // Also linked from elsewhere: the domain list, the setup instructions, and the API.
    const linked = [...inPageLinks(wrapper.vm.sections), 'domain-limit', 'delegation-states', 'migrate-dnssec-guide'];
    linked.forEach(id => expect(ids).toContain(id));
  });

  it('opens a guide when the address names it', async () => {
    await mount('#migrate-dnssec-guide');
    const guide = document.getElementById('migrate-dnssec-guide');
    expect(guide.textContent).toContain("Add deSEC's DS records at your registrar.");
  });

  it('keeps guides closed otherwise', async () => {
    await mount();
    const guide = document.getElementById('migrate-dnssec-guide');
    expect(guide.textContent).toContain('Step by step');
    expect(guide.textContent).not.toContain("Add deSEC's DS records at your registrar.");
  });

  it('follows links within the webapp through the router', async () => {
    const {push} = await mount();
    document.querySelector('a[href="#delegation-states"]').click();
    expect(push).toHaveBeenCalledWith({hash: '#delegation-states'});
    document.querySelector('a[href="/donate/"]').click();
    expect(push).toHaveBeenCalledWith('/donate/');
  });
});
