import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
import '../shared/i18n';

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock window.confirm & alert
window.confirm = vi.fn().mockReturnValue(true);
(globalThis as any).confirm = window.confirm;
window.alert = vi.fn();
(globalThis as any).alert = window.alert;

// Mock ResizeObserver
(globalThis as any).ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock HTMLCanvasElement.getContext
HTMLCanvasElement.prototype.getContext = vi.fn().mockImplementation((type) => {
  if (type === 'webgl' || type === 'experimental-webgl' || type === 'webgl2') {
    return {
      getExtension: vi.fn(),
      getParameter: vi.fn().mockReturnValue(16),
      createTexture: vi.fn(),
      bindTexture: vi.fn(),
      texParameteri: vi.fn(),
      texImage2D: vi.fn(),
      clearColor: vi.fn(),
      clear: vi.fn(),
      enable: vi.fn(),
      disable: vi.fn(),
      viewport: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
  }
  return null;
}) as any;

// Mock EventSource
(globalThis as any).EventSource = class EventSource {
  url: string;
  onmessage: ((ev: any) => void) | null = null;
  onerror: ((ev: any) => void) | null = null;
  close() {}
  constructor(url: string) {
    this.url = url;
  }
} as any;

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
});

// Mock @react-three/drei & @react-three/fiber for full jsdom DOM execution & coverage
vi.mock('@react-three/drei', () => ({
  OrbitControls: () => null,
  Html: ({ children, style, className }: any) => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'r3f-html', className, style }, children);
  },
  Text: ({ children }: any) => {
    const React = require('react');
    return React.createElement('span', null, children);
  },
  Billboard: ({ children }: any) => {
    const React = require('react');
    return React.createElement('div', null, children);
  },
}));

vi.mock('@react-three/fiber', async () => {
  return {
    Canvas: ({ children, className, style }: any) => {
      const React = require('react');
      return React.createElement('div', { 'data-testid': 'r3f-canvas', className, style }, children);
    },
    useFrame: vi.fn(),
    useThree: () => ({
      camera: { position: { set: vi.fn() }, lookAt: vi.fn() },
      scene: {},
      gl: {},
    }),
  };
});

