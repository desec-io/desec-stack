import { describe, expect, it } from 'vitest';
import { VBtn } from 'vuetify/components';

import { mountWithVuetify } from './vuetify';

describe('Vuetify test setup', () => {
  it('mounts Vuetify components', () => {
    const wrapper = mountWithVuetify(VBtn, {
      slots: {
        default: 'Test button',
      },
    });

    expect(wrapper.text()).toContain('Test button');
  });
});
