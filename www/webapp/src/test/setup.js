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

config.global.stubs = {
  transition: false,
};
