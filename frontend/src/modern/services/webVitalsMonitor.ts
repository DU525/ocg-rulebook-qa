import { onCLS, onFCP, onLCP, onTTFB, onINP } from 'web-vitals';

interface PerformanceMetrics {
  cls: number | null;
  fid: number | null;
  fcp: number | null;
  lcp: number | null;
  ttfb: number | null;
  inp: number | null;
}

interface PerformanceRecord {
  timestamp: Date;
  metrics: Partial<PerformanceMetrics>;
}

export class WebVitalsMonitor {
  private metrics: Partial<PerformanceMetrics> = {};
  private history: PerformanceRecord[] = [];
  private onMetricUpdate: ((metrics: Partial<PerformanceMetrics>) => void) | null = null;

  constructor() {
    this.initializeMonitoring();
    this.loadFromStorage();
  }

  private initializeMonitoring(): void {
    if (typeof window === 'undefined') return;

    // CLS (Cumulative Layout Shift)
    onCLS((metric: any) => {
      this.metrics.cls = metric.value;
      this.handleMetric('cls', metric.value);
    });

    // FCP (First Contentful Paint)
    onFCP((metric: any) => {
      this.metrics.fcp = metric.value;
      this.handleMetric('fcp', metric.value);
    });

    // LCP (Largest Contentful Paint)
    onLCP((metric: any) => {
      this.metrics.lcp = metric.value;
      this.handleMetric('lcp', metric.value);
    });

    // TTFB (Time to First Byte)
    onTTFB((metric: any) => {
      this.metrics.ttfb = metric.value;
      this.handleMetric('ttfb', metric.value);
    });

    // INP (Interaction to Next Paint)
    onINP((metric: any) => {
      this.metrics.inp = metric.value;
      this.handleMetric('inp', metric.value);
    });
  }

  private handleMetric(name: keyof PerformanceMetrics, value: number): void {
    this.history.push({
      timestamp: new Date(),
      metrics: { [name]: value },
    });

    // 限制历史记录长度
    if (this.history.length > 100) {
      this.history = this.history.slice(-100);
    }

    this.saveToStorage();
    
    if (this.onMetricUpdate) {
      this.onMetricUpdate(this.metrics);
    }

    // 检查是否需要警告
    this.checkThreshold(name, value);
  }

  private checkThreshold(name: keyof PerformanceMetrics, value: number): void {
    const thresholds = {
      cls: { good: 0.1, needsImprovement: 0.25 },
      fid: { good: 100, needsImprovement: 300 },
      fcp: { good: 1800, needsImprovement: 3000 },
      lcp: { good: 2500, needsImprovement: 4000 },
      ttfb: { good: 800, needsImprovement: 1800 },
      inp: { good: 200, needsImprovement: 500 },
    };

    const threshold = thresholds[name];
    if (threshold) {
      let level: 'good' | 'needs-improvement' | 'poor' = 'good';
      if (value > threshold.needsImprovement) {
        level = 'poor';
      } else if (value > threshold.good) {
        level = 'needs-improvement';
      }

      if (level !== 'good') {
        console.warn(`[WebVitals] ${name.toUpperCase()} is ${level}: ${value.toFixed(1)}ms`);
      }
    }
  }

  private saveToStorage(): void {
    try {
      const data = JSON.stringify({
        metrics: this.metrics,
        latest: this.history.slice(-10),
      });
      sessionStorage.setItem('ocg-web-vitals', data);
    } catch (error) {
      console.warn('[WebVitals] Failed to save to storage:', error);
    }
  }

  private loadFromStorage(): void {
    try {
      const data = sessionStorage.getItem('ocg-web-vitals');
      if (data) {
        const parsed = JSON.parse(data);
        this.metrics = parsed.metrics || {};
        this.history = parsed.latest || [];
      }
    } catch (error) {
      console.warn('[WebVitals] Failed to load from storage:', error);
    }
  }

  public setMetricUpdateCallback(callback: ((metrics: Partial<PerformanceMetrics>) => void) | null): void {
    this.onMetricUpdate = callback;
  }

  public getMetrics(): Partial<PerformanceMetrics> {
    return { ...this.metrics };
  }

  public getHistory(): PerformanceRecord[] {
    return [...this.history];
  }

  public getScore(): { overall: number; metrics: Record<string, 'good' | 'needs-improvement' | 'poor'> } {
    const thresholds = {
      cls: { good: 0.1, needsImprovement: 0.25, weight: 15 },
      fid: { good: 100, needsImprovement: 300, weight: 15 },
      fcp: { good: 1800, needsImprovement: 3000, weight: 10 },
      lcp: { good: 2500, needsImprovement: 4000, weight: 25 },
      ttfb: { good: 800, needsImprovement: 1800, weight: 10 },
      inp: { good: 200, needsImprovement: 500, weight: 25 },
    };

    let totalScore = 0;
    let totalWeight = 0;
    const metricStatuses: Record<string, 'good' | 'needs-improvement' | 'poor'> = {};

    for (const [name, threshold] of Object.entries(thresholds)) {
      const value = this.metrics[name as keyof PerformanceMetrics];
      if (value !== null && value !== undefined) {
        let score: number;
        let status: 'good' | 'needs-improvement' | 'poor';
        
        if (value <= threshold.good) {
          score = 100;
          status = 'good';
        } else if (value <= threshold.needsImprovement) {
          score = 50;
          status = 'needs-improvement';
        } else {
          score = 0;
          status = 'poor';
        }
        
        totalScore += score * threshold.weight;
        totalWeight += threshold.weight;
        metricStatuses[name] = status;
      }
    }

    const overall = totalWeight > 0 ? Math.round(totalScore / totalWeight) : 0;
    return { overall, metrics: metricStatuses };
  }

  public reset(): void {
    this.metrics = {};
    this.history = [];
    try {
      sessionStorage.removeItem('ocg-web-vitals');
    } catch (error) {
      console.warn('[WebVitals] Failed to reset storage:', error);
    }
  }
}

// 单例实例
let instance: WebVitalsMonitor | null = null;

export const getWebVitalsMonitor = (): WebVitalsMonitor => {
  if (!instance) {
    instance = new WebVitalsMonitor();
  }
  return instance;
};

export default WebVitalsMonitor;
