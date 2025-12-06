/**
 * Performance Monitoring Utilities
 * 
 * Client-side performance tracking for Core Web Vitals,
 * custom metrics, and user experience monitoring.
 */

// ============================================================================
// Types
// ============================================================================

export interface PerformanceMetric {
  name: string;
  value: number;
  unit: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

export interface WebVitals {
  LCP: number | null;  // Largest Contentful Paint
  FID: number | null;  // First Input Delay
  CLS: number | null;  // Cumulative Layout Shift
  TTFB: number | null; // Time to First Byte
  FCP: number | null;  // First Contentful Paint
  INP: number | null;  // Interaction to Next Paint
}

export interface NavigationTiming {
  dnsLookup: number;
  tcpConnection: number;
  tlsHandshake: number;
  requestTime: number;
  responseTime: number;
  domInteractive: number;
  domComplete: number;
  loadComplete: number;
}

export interface ResourceTiming {
  name: string;
  type: string;
  duration: number;
  size: number;
  protocol: string;
}

type MetricCallback = (metric: PerformanceMetric) => void;

// ============================================================================
// Performance Monitor Class
// ============================================================================

class PerformanceMonitor {
  private metrics: PerformanceMetric[] = [];
  private callbacks: MetricCallback[] = [];
  private webVitals: WebVitals = {
    LCP: null,
    FID: null,
    CLS: null,
    TTFB: null,
    FCP: null,
    INP: null,
  };

  constructor() {
    if (typeof window !== 'undefined') {
      this.initWebVitals();
      this.initResourceObserver();
    }
  }

  // Subscribe to metric updates
  subscribe(callback: MetricCallback): () => void {
    this.callbacks.push(callback);
    return () => {
      const index = this.callbacks.indexOf(callback);
      if (index > -1) this.callbacks.splice(index, 1);
    };
  }

  // Record a custom metric
  recordMetric(name: string, value: number, unit: string = 'ms', metadata?: Record<string, unknown>): void {
    const metric: PerformanceMetric = {
      name,
      value,
      unit,
      timestamp: Date.now(),
      metadata,
    };

    this.metrics.push(metric);
    this.notifyCallbacks(metric);

    // Keep only last 100 metrics in memory
    if (this.metrics.length > 100) {
      this.metrics = this.metrics.slice(-100);
    }
  }

  // Measure function execution time
  measure<T>(name: string, fn: () => T): T {
    const start = performance.now();
    const result = fn();
    const duration = performance.now() - start;
    this.recordMetric(name, duration, 'ms');
    return result;
  }

  // Measure async function execution time
  async measureAsync<T>(name: string, fn: () => Promise<T>): Promise<T> {
    const start = performance.now();
    const result = await fn();
    const duration = performance.now() - start;
    this.recordMetric(name, duration, 'ms');
    return result;
  }

  // Start a timer and return a stop function
  startTimer(name: string): () => number {
    const start = performance.now();
    return () => {
      const duration = performance.now() - start;
      this.recordMetric(name, duration, 'ms');
      return duration;
    };
  }

  // Get current Web Vitals
  getWebVitals(): WebVitals {
    return { ...this.webVitals };
  }

  // Get navigation timing
  getNavigationTiming(): NavigationTiming | null {
    if (typeof window === 'undefined') return null;

    const timing = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    if (!timing) return null;

    return {
      dnsLookup: timing.domainLookupEnd - timing.domainLookupStart,
      tcpConnection: timing.connectEnd - timing.connectStart,
      tlsHandshake: timing.secureConnectionStart > 0 
        ? timing.connectEnd - timing.secureConnectionStart 
        : 0,
      requestTime: timing.responseStart - timing.requestStart,
      responseTime: timing.responseEnd - timing.responseStart,
      domInteractive: timing.domInteractive - timing.fetchStart,
      domComplete: timing.domComplete - timing.fetchStart,
      loadComplete: timing.loadEventEnd - timing.fetchStart,
    };
  }

  // Get resource timing for slow resources
  getSlowResources(thresholdMs: number = 500): ResourceTiming[] {
    if (typeof window === 'undefined') return [];

    const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
    
    return resources
      .filter(r => r.duration > thresholdMs)
      .map(r => ({
        name: r.name,
        type: r.initiatorType,
        duration: r.duration,
        size: r.transferSize || 0,
        protocol: r.nextHopProtocol || 'unknown',
      }))
      .sort((a, b) => b.duration - a.duration);
  }

  // Get all recorded metrics
  getMetrics(): PerformanceMetric[] {
    return [...this.metrics];
  }

  // Get metrics summary
  getMetricsSummary(): Record<string, { avg: number; min: number; max: number; count: number }> {
    const summary: Record<string, { values: number[]; unit: string }> = {};

    for (const metric of this.metrics) {
      if (!summary[metric.name]) {
        summary[metric.name] = { values: [], unit: metric.unit };
      }
      summary[metric.name].values.push(metric.value);
    }

    const result: Record<string, { avg: number; min: number; max: number; count: number }> = {};
    
    for (const [name, data] of Object.entries(summary)) {
      const values = data.values;
      result[name] = {
        avg: values.reduce((a, b) => a + b, 0) / values.length,
        min: Math.min(...values),
        max: Math.max(...values),
        count: values.length,
      };
    }

    return result;
  }

  // Clear recorded metrics
  clearMetrics(): void {
    this.metrics = [];
  }

  // Send metrics to analytics endpoint
  async flushMetrics(endpoint: string): Promise<void> {
    if (this.metrics.length === 0) return;

    const payload = {
      webVitals: this.webVitals,
      metrics: this.metrics,
      navigation: this.getNavigationTiming(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      timestamp: Date.now(),
    };

    try {
      // Use sendBeacon for reliability on page unload
      if (navigator.sendBeacon) {
        navigator.sendBeacon(endpoint, JSON.stringify(payload));
      } else {
        await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          keepalive: true,
        });
      }

      this.clearMetrics();
    } catch (error) {
      console.warn('Failed to flush performance metrics:', error);
    }
  }

  // Initialize Web Vitals tracking
  private initWebVitals(): void {
    // Largest Contentful Paint
    this.observePerformanceEntry('largest-contentful-paint', (entry) => {
      this.webVitals.LCP = entry.startTime;
      this.recordMetric('LCP', entry.startTime, 'ms');
    });

    // First Input Delay
    this.observePerformanceEntry('first-input', (entry) => {
      const fid = (entry as PerformanceEventTiming).processingStart - entry.startTime;
      this.webVitals.FID = fid;
      this.recordMetric('FID', fid, 'ms');
    });

    // Cumulative Layout Shift
    let clsValue = 0;
    this.observePerformanceEntry('layout-shift', (entry) => {
      const layoutShift = entry as LayoutShift;
      if (!layoutShift.hadRecentInput) {
        clsValue += layoutShift.value;
        this.webVitals.CLS = clsValue;
      }
    });

    // First Contentful Paint
    this.observePerformanceEntry('paint', (entry) => {
      if (entry.name === 'first-contentful-paint') {
        this.webVitals.FCP = entry.startTime;
        this.recordMetric('FCP', entry.startTime, 'ms');
      }
    });

    // Time to First Byte
    const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    if (navEntry) {
      this.webVitals.TTFB = navEntry.responseStart - navEntry.requestStart;
      this.recordMetric('TTFB', this.webVitals.TTFB, 'ms');
    }
  }

  // Observe resource loading
  private initResourceObserver(): void {
    this.observePerformanceEntry('resource', (entry) => {
      const resource = entry as PerformanceResourceTiming;
      
      // Track slow resources (> 1 second)
      if (resource.duration > 1000) {
        this.recordMetric('slow_resource', resource.duration, 'ms', {
          url: resource.name,
          type: resource.initiatorType,
        });
      }
    });
  }

  // Helper to observe performance entries
  private observePerformanceEntry(
    type: string,
    callback: (entry: PerformanceEntry) => void
  ): void {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          callback(entry);
        }
      });

      observer.observe({ type, buffered: true });
    } catch {
      // Observer not supported for this entry type
    }
  }

  // Notify all subscribers
  private notifyCallbacks(metric: PerformanceMetric): void {
    for (const callback of this.callbacks) {
      try {
        callback(metric);
      } catch (error) {
        console.warn('Performance metric callback error:', error);
      }
    }
  }
}

// Layout Shift interface
interface LayoutShift extends PerformanceEntry {
  value: number;
  hadRecentInput: boolean;
}

// ============================================================================
// Singleton Instance
// ============================================================================

export const performanceMonitor = new PerformanceMonitor();

// ============================================================================
// React Hook
// ============================================================================

import { useEffect, useState, useCallback } from 'react';

export function usePerformanceMetrics() {
  const [metrics, setMetrics] = useState<PerformanceMetric[]>([]);
  const [webVitals, setWebVitals] = useState<WebVitals>(performanceMonitor.getWebVitals());

  useEffect(() => {
    const unsubscribe = performanceMonitor.subscribe((metric) => {
      setMetrics(prev => [...prev.slice(-99), metric]);
      setWebVitals(performanceMonitor.getWebVitals());
    });

    return unsubscribe;
  }, []);

  const recordMetric = useCallback((name: string, value: number, unit?: string) => {
    performanceMonitor.recordMetric(name, value, unit);
  }, []);

  const startTimer = useCallback((name: string) => {
    return performanceMonitor.startTimer(name);
  }, []);

  return {
    metrics,
    webVitals,
    recordMetric,
    startTimer,
    getSummary: performanceMonitor.getMetricsSummary.bind(performanceMonitor),
    getSlowResources: performanceMonitor.getSlowResources.bind(performanceMonitor),
  };
}

// ============================================================================
// Component Performance HOC
// ============================================================================

export function withPerformanceTracking<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  componentName: string
) {
  return function WithPerformanceTracking(props: P) {
    useEffect(() => {
      const stopTimer = performanceMonitor.startTimer(`component.${componentName}.mount`);
      return () => {
        stopTimer();
      };
    }, []);

    return <WrappedComponent {...props} />;
  };
}

// ============================================================================
// Performance Utilities
// ============================================================================

/**
 * Debounced performance recording to avoid overwhelming with metrics.
 */
export function createDebouncedRecorder(name: string, delayMs: number = 100) {
  let timeout: ReturnType<typeof setTimeout>;
  let lastValue: number;

  return (value: number, unit?: string) => {
    lastValue = value;
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      performanceMonitor.recordMetric(name, lastValue, unit);
    }, delayMs);
  };
}

/**
 * Track render performance of a component.
 */
export function trackRenderPerformance(componentName: string) {
  const renderCount = { current: 0 };
  const lastRender = { current: performance.now() };

  return {
    onRender: () => {
      const now = performance.now();
      const timeSinceLastRender = now - lastRender.current;
      lastRender.current = now;
      renderCount.current++;

      performanceMonitor.recordMetric(
        `component.${componentName}.render`,
        timeSinceLastRender,
        'ms',
        { renderCount: renderCount.current }
      );
    },
    getRenderCount: () => renderCount.current,
  };
}
