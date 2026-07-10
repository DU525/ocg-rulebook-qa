interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expireTime: number;
}

interface CacheConfig {
  defaultTTL: number;
  maxSize: number;
  enableLocalStorage: boolean;
}

const DEFAULT_CONFIG: CacheConfig = {
  defaultTTL: 5 * 60 * 1000, // 5分钟
  maxSize: 100,
  enableLocalStorage: true
};

class ApiCache {
  private cache: Map<string, CacheEntry<any>> = new Map();
  private config: CacheConfig;
  private cacheKey = 'ocg_api_cache';

  constructor(config?: Partial<CacheConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.loadFromStorage();
  }

  private generateKey(method: string, url: string, data?: any): string {
    let key = `${method}:${url}`;
    if (data) {
      key += `:${JSON.stringify(data)}`;
    }
    return key;
  }

  private loadFromStorage(): void {
    if (!this.config.enableLocalStorage) return;
    
    try {
      const stored = localStorage.getItem(this.cacheKey);
      if (stored) {
        const { cache, timestamp } = JSON.parse(stored);
        const oneHour = 60 * 60 * 1000;
        
        if (Date.now() - timestamp < oneHour) {
          Object.entries(cache).forEach(([key, entry]: [string, any]) => {
            if (entry.expireTime > Date.now()) {
              this.cache.set(key, entry);
            }
          });
        }
      }
    } catch (error) {
      console.error('[ApiCache] 加载缓存失败:', error);
    }
  }

  private saveToStorage(): void {
    if (!this.config.enableLocalStorage) return;
    
    try {
      const cacheObject: Record<string, any> = {};
      this.cache.forEach((value, key) => {
        cacheObject[key] = value;
      });
      
      localStorage.setItem(this.cacheKey, JSON.stringify({
        cache: cacheObject,
        timestamp: Date.now()
      }));
    } catch (error) {
      console.error('[ApiCache] 保存缓存失败:', error);
    }
  }

  private cleanExpired(): void {
    const now = Date.now();
    const keysToDelete: string[] = [];
    
    this.cache.forEach((entry, key) => {
      if (entry.expireTime < now) {
        keysToDelete.push(key);
      }
    });
    
    keysToDelete.forEach(key => this.cache.delete(key));
  }

  private evictOldest(): void {
    if (this.cache.size >= this.config.maxSize) {
      let oldestKey: string | null = null;
      let oldestTime: number = Infinity;
      
      this.cache.forEach((entry, key) => {
        if (entry.timestamp < oldestTime) {
          oldestKey = key;
          oldestTime = entry.timestamp;
        }
      });
      
      if (oldestKey) {
        this.cache.delete(oldestKey);
      }
    }
  }

  get<T>(method: string, url: string, data?: any): T | null {
    this.cleanExpired();
    const key = this.generateKey(method, url, data);
    const entry = this.cache.get(key);
    
    if (entry) {
      if (entry.expireTime > Date.now()) {
        return entry.data;
      }
      this.cache.delete(key);
    }
    
    return null;
  }

  set<T>(method: string, url: string, data: any, value: T, ttl?: number): void {
    this.cleanExpired();
    this.evictOldest();
    
    const key = this.generateKey(method, url, data);
    const entry: CacheEntry<T> = {
      data: value,
      timestamp: Date.now(),
      expireTime: Date.now() + (ttl || this.config.defaultTTL)
    };
    
    this.cache.set(key, entry);
    this.saveToStorage();
  }

  invalidate(method?: string, url?: string): void {
    if (!method && !url) {
      this.cache.clear();
      this.saveToStorage();
      return;
    }
    
    const keysToDelete: string[] = [];
    this.cache.forEach((_, key) => {
      const [keyMethod, keyUrl] = key.split(':');
      const matchMethod = !method || keyMethod === method;
      const matchUrl = !url || keyUrl.includes(url);
      
      if (matchMethod && matchUrl) {
        keysToDelete.push(key);
      }
    });
    
    keysToDelete.forEach(key => this.cache.delete(key));
    this.saveToStorage();
  }

  getStats(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys())
    };
  }

  async cachedFetch<T>(
    fetchFn: () => Promise<T>,
    method: string,
    url: string,
    data?: any,
    ttl?: number,
    forceRefresh?: boolean
  ): Promise<T> {
    if (!forceRefresh) {
      const cached = this.get<T>(method, url, data);
      if (cached) {
        return cached;
      }
    }
    
    const result = await fetchFn();
    this.set(method, url, data, result, ttl);
    return result;
  }
}

export const apiCache = new ApiCache();

export default ApiCache;
