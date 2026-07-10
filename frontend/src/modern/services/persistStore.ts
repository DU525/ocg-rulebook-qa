interface PersistConfig {
  key: string;
  version: string;
  defaultVersion: number;
}

const DEFAULT_CONFIG: PersistConfig = {
  key: 'ocg_app_state',
  version: '1.0.0',
  defaultVersion: 1
};

class PersistStore {
  private config: PersistConfig;

  constructor(config?: Partial<PersistConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  private getVersionKey(): string {
    return `${this.config.key}_version`;
  }

  private getStateKey(): string {
    return this.config.key;
  }

  private validateVersion(): boolean {
    try {
      const storedVersion = localStorage.getItem(this.getVersionKey());
      if (!storedVersion) {
        return false;
      }
      return storedVersion === this.config.version;
    } catch (error) {
      console.error('[PersistStore] 版本验证失败:', error);
      return false;
    }
  }

  save<T>(state: T): boolean {
    try {
      const serialized = JSON.stringify(state);
      localStorage.setItem(this.getStateKey(), serialized);
      localStorage.setItem(this.getVersionKey(), this.config.version);
      return true;
    } catch (error) {
      console.error('[PersistStore] 保存状态失败:', error);
      return false;
    }
  }

  load<T>(fallback: T): T {
    try {
      if (!this.validateVersion()) {
        console.log('[PersistStore] 版本不匹配，使用默认值');
        this.clear();
        return fallback;
      }

      const serialized = localStorage.getItem(this.getStateKey());
      if (!serialized) {
        return fallback;
      }

      return JSON.parse(serialized);
    } catch (error) {
      console.error('[PersistStore] 加载状态失败:', error);
      return fallback;
    }
  }

  clear(): void {
    try {
      localStorage.removeItem(this.getStateKey());
      localStorage.removeItem(this.getVersionKey());
    } catch (error) {
      console.error('[PersistStore] 清除状态失败:', error);
    }
  }
}

export const persistStore = new PersistStore();

export default PersistStore;
