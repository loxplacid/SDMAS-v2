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

// jsdom does not implement EventSource — the NotificationBell subscribes to
// SSE for live unread-count updates. Provide a minimal no-op polyfill so the
// subscription mounts cleanly in tests (events are covered via API mocks).
if (typeof window !== 'undefined' && !window.EventSource) {
  class EventSourceStub {
    static CONNECTING = 0
    static OPEN = 1
    static CLOSED = 2
    readyState: number = EventSourceStub.CONNECTING
    onopen: ((ev: Event) => void) | null = null
    onmessage: ((ev: MessageEvent) => void) | null = null
    onerror: ((ev: Event) => void) | null = null
    private handlers: Record<string, Array<(ev: any) => void>> = {}
    constructor(private url: string, private opts?: { withCredentials?: boolean }) {}
    addEventListener(type: string, cb: (ev: any) => void) {
      ;(this.handlers[type] ||= []).push(cb)
    }
    removeEventListener(type: string, cb: (ev: any) => void) {
      this.handlers[type] = (this.handlers[type] || []).filter((h) => h !== cb)
    }
    dispatchEvent(ev: any): boolean {
      ;(this.handlers[ev.type] || []).forEach((h) => h(ev))
      return true
    }
    close() {}
  }
  ;(window as unknown as { EventSource: typeof EventSource }).EventSource =
    EventSourceStub as unknown as typeof EventSource
}