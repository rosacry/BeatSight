import '@testing-library/jest-dom';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { server } from './mocks/server';

// Mock canvas for components that use it (e.g., ParticleBackground)
HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    scale: vi.fn(),
    translate: vi.fn(),
    rotate: vi.fn(),
    drawImage: vi.fn(),
    createLinearGradient: vi.fn(() => ({
        addColorStop: vi.fn(),
    })),
    createRadialGradient: vi.fn(() => ({
        addColorStop: vi.fn(),
    })),
})) as unknown as typeof HTMLCanvasElement.prototype.getContext;

// Mock window.scrollTo for scroll restoration
Object.defineProperty(window, 'scrollTo', {
    value: vi.fn(),
    writable: true,
});

// Establish API mocking before all tests
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));

// Reset any request handlers that are declared in a test
afterEach(() => server.resetHandlers());

// Clean up after the tests are finished
afterAll(() => server.close());
