import '@testing-library/jest-dom'

// jsdom does not implement window.matchMedia — components like AnimatedCount
// query it for prefers-reduced-motion. Provide a minimal polyfill.
// `matches: true` reports reduced motion so animated components jump straight
// to their final value instead of running requestAnimationFrame loops in tests.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: true,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}