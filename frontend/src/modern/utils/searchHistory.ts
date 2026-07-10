import { useState, useEffect, useCallback } from 'react';

interface SearchHistoryItem {
  id: string;
  query: string;
  timestamp: Date;
  gameType?: 'ocg' | 'dm';
}

const STORAGE_KEY = 'ocg-search-history';
const MAX_HISTORY_LENGTH = 20;

export class SearchHistoryManager {
  private static instance: SearchHistoryManager;
  private idCounter: number = 0;
  
  private constructor() {}

  public static getInstance(): SearchHistoryManager {
    if (!SearchHistoryManager.instance) {
      SearchHistoryManager.instance = new SearchHistoryManager();
    }
    return SearchHistoryManager.instance;
  }
  
  private generateId(): string {
    this.idCounter++;
    return `${Date.now()}-${this.idCounter}`;
  }

  public getHistory(gameType?: 'ocg' | 'dm'): SearchHistoryItem[] {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return [];
      
      let history = JSON.parse(stored) as SearchHistoryItem[];
      
      // 转换时间戳
      history = history.map(item => ({
        ...item,
        timestamp: new Date(item.timestamp),
      }));
      
      // 根据游戏类型过滤
      if (gameType) {
        history = history.filter(item => !item.gameType || item.gameType === gameType);
      }
      
      return history;
    } catch (error) {
      console.warn('[SearchHistory] Failed to get history:', error);
      return [];
    }
  }

  public addToHistory(query: string, gameType?: 'ocg' | 'dm'): void {
    try {
      const trimmedQuery = query.trim();
      if (!trimmedQuery) return;
      
      let history = this.getHistory();
      
      // 移除相同的查询（不管大小写）
      history = history.filter(
        item => item.query.toLowerCase() !== trimmedQuery.toLowerCase()
      );
      
      // 添加新的查询
    history.unshift({
      id: this.generateId(),
      query: trimmedQuery,
      timestamp: new Date(),
      gameType,
    });
      
      // 限制长度
      if (history.length > MAX_HISTORY_LENGTH) {
        history = history.slice(0, MAX_HISTORY_LENGTH);
      }
      
      // 保存
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch (error) {
      console.warn('[SearchHistory] Failed to add to history:', error);
    }
  }

  public removeFromHistory(id: string): void {
    try {
      let history = this.getHistory();
      history = history.filter(item => item.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch (error) {
      console.warn('[SearchHistory] Failed to remove from history:', error);
    }
  }

  public clearHistory(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.warn('[SearchHistory] Failed to clear history:', error);
    }
  }

  public formatTimestamp(date: Date): string {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
    });
  }
}

// Hook 用于管理搜索历史
export const useSearchHistory = (gameType?: 'ocg' | 'dm') => {
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);

  const refreshHistory = useCallback(() => {
    const manager = SearchHistoryManager.getInstance();
    setHistory(manager.getHistory(gameType));
  }, [gameType]);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  const addToHistory = useCallback((query: string) => {
    const manager = SearchHistoryManager.getInstance();
    manager.addToHistory(query, gameType);
    refreshHistory();
  }, [gameType, refreshHistory]);

  const removeFromHistory = useCallback((id: string) => {
    const manager = SearchHistoryManager.getInstance();
    manager.removeFromHistory(id);
    refreshHistory();
  }, [refreshHistory]);

  const clearHistory = useCallback(() => {
    const manager = SearchHistoryManager.getInstance();
    manager.clearHistory();
    refreshHistory();
  }, [refreshHistory]);

  return {
    history,
    addToHistory,
    removeFromHistory,
    clearHistory,
  };
};

export default SearchHistoryManager;
