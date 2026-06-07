import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

import 'vuetify/styles';

export function createVuetifyPlugin(options = {}) {
  return createVuetify({
    components,
    directives,
    ...options,
  });
}

export function mountWithVuetify(component, options = {}) {
  const vuetify = createVuetifyPlugin(options.vuetify);
  return mount(component, {
    ...options,
    global: {
      ...options.global,
      plugins: [
        vuetify,
        ...(options.global?.plugins || []),
      ],
    },
  });
}
