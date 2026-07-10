import { useState, useEffect, useRef, useCallback } from 'react';

interface PerformanceConfig {
  logEnabled?: boolean;
  longTaskThreshold?: number;
}

interface PerformanceMetrics {
  renderTime: number;
  mountTime: number;
  updateCount: number;
}

const DEFAULT_CONFIG: PerformanceConfig = {
  logEnabled: true,
  longTaskThreshold: 100
};

export const usePerformance = (
  componentName: string,
  config: PerformanceConfig = {}
) => {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };
  const startTimeRef = useRef<number>(0);
  const mountTimeRef = useRef<number>(0);
  const updateCountRef = useRef<number>(0);
  const previousPropsRef = useRef<any>(null);

  // 组件挂载
  useEffect(() => {
    mountTimeRef.current = performance.now();
    
    if (mergedConfig.logEnabled) {
      console.log(`[Performance] ${componentName} mounted in ${mountTimeRef.current.toFixed(2)}ms`);
    }

    return () => {
      const unmountTime = performance.now();
      if (mergedConfig.logEnabled) {
        console.log(`[Performance] ${componentName} lifecycle duration: ${(unmountTime - mountTimeRef.current).toFixed(2)}ms`);
      }
    };
  }, [componentName, mergedConfig.logEnabled]);

  // 渲染计时
  const startRender = useCallback(() => {
    startTimeRef.current = performance.now();
  }, []);

  const endRender = useCallback(() => {
    updateCountRef.current++;
    const renderTime = performance.now() - startTimeRef.current;
    
    if (mergedConfig.logEnabled && renderTime > mergedConfig.longTaskThreshold!) {
      console.warn(`[Performance] ${componentName} render took ${renderTime.toFixed(2)}ms (update #${updateCountRef.current})`);
    }
    
    return renderTime;
  }, [componentName, mergedConfig.logEnabled, mergedConfig.longTaskThreshold]);

  // 测量函数执行时间
  const measureFunction = useCallback(async <T>(
    fnName: string,
    fn: () => T | Promise<T>
  ): Promise<T> => {
    const start = performance.now();
    
    try {
      const result = await fn();
      const duration = performance.now() - start;
      
      if (mergedConfig.logEnabled && duration > mergedConfig.longTaskThreshold!) {
        console.warn(`[Performance] ${componentName}.${fnName} took ${duration.toFixed(2)}ms`);
      }
      
      return result;
    } catch (error) {
      console.error(`[Performance] ${componentName}.${fnName} error:`, error);
      throw error;
    }
  }, [componentName, mergedConfig.logEnabled, mergedConfig.longTaskThreshold]);

  // 获取当前指标
  const getMetrics = useCallback((): PerformanceMetrics => {
    return {
      renderTime: performance.now() - startTimeRef.current,
      mountTime: mountTimeRef.current,
      updateCount: updateCountRef.current
    };
  }, []);

  return {
    startRender,
    endRender,
    measureFunction,
    getMetrics,
    updateCount: updateCountRef.current
  };
};

// 防抖Hook
export const useDebounce = <T>(value: T, delay: number = 300): T => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

// 节流Hook
export const useThrottle = <T>(value: T, limit: number = 300): T => {
  const [throttledValue, setThrottledValue] = useState(value);
  const lastTimeRef = useRef<number>(0);

  useEffect(() => {
    const now = Date.now();
    
    if (now - lastTimeRef.current >= limit) {
      lastTimeRef.current = now;
      setThrottledValue(value);
    }
  }, [value, limit]);

  return throttledValue;
};

// 异步Hook，带AbortController
export const useAsync = <T, E = any>() => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<E | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const execute = useCallback(async (
    asyncFn: (controller: AbortController) => Promise<T>
  ): Promise<T | null> => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setLoading(true);
    setError(null);

    try {
      const result = await asyncFn(abortControllerRef.current);
      setLoading(false);
      return result;
    } catch (err) {
      if (!abortControllerRef.current.signal.aborted) {
        setError(err as E);
      }
      setLoading(false);
      return null;
    }
  }, []);

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  useEffect(() => {
    return () => {
      cancel();
    };
  }, [cancel]);

  return { loading, error, execute, cancel };
};

export default usePerformance;
