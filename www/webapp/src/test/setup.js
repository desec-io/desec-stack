import { config } from '@vue/test-utils';

class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

class IntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserver;
globalThis.IntersectionObserver = globalThis.IntersectionObserver || IntersectionObserver;
globalThis.matchMedia = globalThis.matchMedia || (() => ({
  matches: false,
  addEventListener: () => {},
  removeEventListener: () => {},
}));
// Used by Vuetify overlays (e.g. snackbars) to position themselves.
globalThis.visualViewport = globalThis.visualViewport || {
  width: 1024,
  height: 768,
  offsetLeft: 0,
  offsetTop: 0,
  scale: 1,
  addEventListener: () => {},
  removeEventListener: () => {},
};

config.global.stubs = {
  transition: false,
};
