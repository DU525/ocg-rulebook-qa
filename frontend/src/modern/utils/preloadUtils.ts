import { useState, useEffect, useCallback } from 'react';

interface PreloadItem {
  key: string;
  loader: () => Promise<any>;
  loaded: boolean;
  promise?: Promise<any>;
}

class RoutePreloader {
  private preloadedItems: Map<string, PreloadItem> = new Map();
  
  constructor() {
    // 预加载关键模块的入口
  }

  /**
   * 预加载一个模块
   */
  preload(key: string, loader: () => Promise<any>): Promise<any> {
    // 如果已经加载过或正在加载，直接返回
    const existing = this.preloadedItems.get(key);
    if (existing?.loaded) {
      return Promise.resolve(existing.promise);
    }
    if (existing?.promise) {
      return existing.promise;
    }

    const promise = loader()
      .then(result => {
        this.preloadedItems.set(key, { key, loader, loaded: true, promise: Promise.resolve(result) });
        return result;
      })
      .catch(error => {
        console.warn(`[RoutePreloader] Preload failed for ${key}:`, error);
        this.preloadedItems.delete(key);
        throw error;
      });

    this.preloadedItems.set(key, { key, loader, loaded: false, promise });
    return promise;
  }

  /**
   * 智能预加载 - 基于用户行为预测
   */
  preloadOnHover(key: string, loader: () => Promise<any>) {
    return () => {
      if (!this.preloadedItems.has(key)) {
        this.preload(key, loader);
      }
    };
  }

  /**
   * 批量预加载
   */
  preloadMultiple(items: Array<{ key: string; loader: () => Promise<any> }>): Promise<any[]> {
    return Promise.all(items.map(item => this.preload(item.key, item.loader)));
  }

  /**
   * 清除预加载缓存
   */
  clear() {
    this.preloadedItems.clear();
  }

  /**
   * 获取预加载状态
   */
  getStatus(key: string): { loaded: boolean; loading: boolean } {
    const item = this.preloadedItems.get(key);
    return {
      loaded: item?.loaded ?? false,
      loading: !!(item?.promise && !item.loaded),
    };
  }
}

// 全局预加载器实例
export const routePreloader = new RoutePreloader();

/**
 * React Hook - 组件挂载时预加载
 */
export function usePreload(key: string, loader: () => Promise<any>) {
  useEffect(() => {
    routePreloader.preload(key, loader);
  }, [key, loader]);
}

/**
 * React Hook - 智能预加载触发
 */
export function usePreloadOnHover(key: string, loader: () => Promise<any>) {
  return useCallback(() => {
    routePreloader.preload(key, loader);
  }, [key, loader]);
}
