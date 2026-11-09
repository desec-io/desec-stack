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
// Vuetify (>= 4.3) computes its display breakpoints from min-width media
// queries, so they are evaluated against the window width. Anything else
// does not match.
function matchesMediaQuery(query) {
  const width = window.innerWidth;
  return query.split(/\s+and\s+/).every(part => {
    const m = part.match(/^\(\s*(min|max)-width:\s*([\d.]+)px\s*\)$/);
    if (!m) return false;
    return m[1] === 'min' ? width >= Number(m[2]) : width <= Number(m[2]);
  });
}
globalThis.matchMedia = globalThis.matchMedia || (query => ({
  media: query,
  matches: matchesMediaQuery(query),
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
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
