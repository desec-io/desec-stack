import { afterEach, describe, expect, it, vi } from 'vitest';

import { mountWithVuetify } from '@/test/vuetify';
import DelegationStatus from './DelegationStatus.vue';

const INSECURE = {
  secure_since: null,
  checked: '2026-10-24T08:00:00.000000Z',
  nameserver_status: 'correctly_delegated',
  security_status: 'insecure',
  nameservers: ['ns1.desec.io.'],
};

function mount(props) {
  return mountWithVuetify(DelegationStatus, {
    props: {domain: 'example.com', suffixes: ['dedyn.io'], ...props},
  });
}

describe('DelegationStatus', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows the status as a chip', () => {
    const wrapper = mount({modelValue: INSECURE});
    expect(wrapper.find('.v-chip').exists()).toBe(true);
    expect(wrapper.text()).toContain('No DNSSEC');
  });

  it('shows that a check is under way', () => {
    const wrapper = mount({modelValue: INSECURE, checking: true});
    expect(wrapper.text()).toContain('Checking…');
    expect(wrapper.text()).not.toContain('No DNSSEC');
    expect(wrapper.find('.v-progress-circular').exists()).toBe(true);
  });

  it('shows domains under a local public suffix as secure', () => {
    // They count towards the secure domains, so the chips must add up.
    for (const domain of ['mine.dedyn.io', 'sub.mine.dedyn.io']) {
      const wrapper = mount({domain, modelValue: {...INSECURE, checked: null}});
      expect(wrapper.find('.v-chip').text()).toBe('Secure');
    }
  });

  it('shows only the icon on phones', () => {
    vi.stubGlobal('innerWidth', 400);
    const wrapper = mountWithVuetify(DelegationStatus, {
      props: {domain: 'example.com', modelValue: INSECURE, suffixes: []},
    });
    const chip = wrapper.find('.v-chip');
    expect(chip.text()).not.toContain('No DNSSEC');
    expect(chip.attributes('aria-label')).toBe('No DNSSEC');
    expect(chip.find('.v-icon').exists()).toBe(true);
  });

  it('is not disabled along with the fields of the row', () => {
    const wrapper = mountWithVuetify(DelegationStatus, {
      props: {domain: 'example.com', modelValue: INSECURE, suffixes: []},
      attrs: {disabled: true, readonly: true},
    });
    expect(wrapper.find('.v-chip--disabled').exists()).toBe(false);
  });
});
