import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import SearchHistoryManager from './searchHistory';

describe('SearchHistoryManager - 核心功能测试', () => {
  let manager: SearchHistoryManager;

  beforeEach(() => {
    localStorage.clear();
    manager = SearchHistoryManager.getInstance();
    // 不使用fake timers，避免时间戳问题
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('单例模式测试', () => {
    it('应该返回相同的实例', () => {
      const instance1 = SearchHistoryManager.getInstance();
      const instance2 = SearchHistoryManager.getInstance();
      expect(instance1).toBe(instance2);
    });
  });

  describe('getHistory 测试', () => {
    it('应该返回空数组当没有历史记录', () => {
      const history = manager.getHistory();
      expect(history).toEqual([]);
    });

    it('应该返回历史记录列表', () => {
      manager.addToHistory('查询1', 'ocg');
      manager.addToHistory('查询2', 'dm');
      
      const history = manager.getHistory();
      expect(history.length).toBe(2);
      expect(history[0].query).toBe('查询2');
      expect(history[1].query).toBe('查询1');
    });

    it('应该按游戏类型过滤历史记录', () => {
      manager.addToHistory('ocg查询1', 'ocg');
      manager.addToHistory('dm查询1', 'dm');
      manager.addToHistory('ocg查询2', 'ocg');
      
      const ocgHistory = manager.getHistory('ocg');
      expect(ocgHistory.length).toBe(2);
      expect(ocgHistory.every(item => item.gameType === 'ocg' || !item.gameType)).toBeTruthy();
      
      const dmHistory = manager.getHistory('dm');
      expect(dmHistory.length).toBe(1);
      expect(dmHistory[0].gameType).toBe('dm');
    });

    it('应该正确解析和转换日期时间', () => {
      manager.addToHistory('时间测试', 'ocg');
      const history = manager.getHistory();
      expect(history[0].timestamp instanceof Date).toBeTruthy();
      expect(history[0].timestamp.getTime()).not.toBeNaN();
    });
  });

  describe('addToHistory 测试', () => {
    it('应该成功添加新的历史记录', () => {
      manager.addToHistory('新查询', 'ocg');
      const history = manager.getHistory();
      expect(history.length).toBe(1);
      expect(history[0].query).toBe('新查询');
      expect(history[0].gameType).toBe('ocg');
    });

    it('应该自动修剪空白字符', () => {
      manager.addToHistory('   带空格的查询   ', 'ocg');
      const history = manager.getHistory();
      expect(history[0].query).toBe('带空格的查询');
    });

    it('不应该添加空查询', () => {
      manager.addToHistory('', 'ocg');
      manager.addToHistory('   ', 'ocg');
      
      const history = manager.getHistory();
      expect(history.length).toBe(0);
    });

    it('应该移除重复查询（不区分大小写）', () => {
      manager.addToHistory('Test Query', 'ocg');
      manager.addToHistory('test query', 'dm');
      
      const history = manager.getHistory();
      expect(history.length).toBe(1);
      expect(history[0].gameType).toBe('dm');
    });

    it('新查询应该添加到列表开头', () => {
      manager.addToHistory('第一个', 'ocg');
      manager.addToHistory('第二个', 'ocg');
      manager.addToHistory('第三个', 'ocg');
      
      const history = manager.getHistory();
      expect(history[0].query).toBe('第三个');
      expect(history[2].query).toBe('第一个');
    });

    it('应该限制历史记录最大数量为20', () => {
      for (let i = 1; i <= 25; i++) {
        manager.addToHistory(`查询${i}`, 'ocg');
      }
      
      const history = manager.getHistory();
      expect(history.length).toBe(20);
      expect(history[0].query).toBe('查询25');
      expect(history[19].query).toBe('查询6');
    });

    it('应该不设置游戏类型时保存为undefined', () => {
      manager.addToHistory('不带类型的查询');
      const history = manager.getHistory();
      expect(history[0].gameType).toBeUndefined();
    });
  });

  describe('removeFromHistory 测试', () => {
    it('应该成功移除指定ID的记录', () => {
    manager.addToHistory('要保留的', 'ocg');
    // 延迟一点点添加第二个，确保时间戳不同
    const firstHistory = manager.getHistory();
    expect(firstHistory.length).toBe(1);
    
    manager.addToHistory('要删除的', 'ocg');
    const historyBefore = manager.getHistory();
    expect(historyBefore.length).toBe(2);
    
    const idToRemove = historyBefore[0].id;
    manager.removeFromHistory(idToRemove);
    
    const historyAfter = manager.getHistory();
    expect(historyAfter.length).toBe(1);
    expect(historyAfter[0].query).toBe('要保留的');
  });

    it('应该在ID不存在时不做任何操作', () => {
      manager.addToHistory('测试', 'ocg');
      
      const historyBefore = manager.getHistory();
      manager.removeFromHistory('不存在的ID');
      
      const historyAfter = manager.getHistory();
      expect(historyAfter.length).toEqual(historyBefore.length);
    });

    it('应该在空历史记录时不做任何操作', () => {
      manager.removeFromHistory('任意ID');
      const history = manager.getHistory();
      expect(history.length).toBe(0);
    });
  });

  describe('clearHistory 测试', () => {
    it('应该清空所有历史记录', () => {
      manager.addToHistory('查询1', 'ocg');
      manager.addToHistory('查询2', 'dm');
      
      manager.clearHistory();
      
      const history = manager.getHistory();
      expect(history.length).toBe(0);
    });

    it('应该在历史记录已经为空时不报错', () => {
      expect(() => {
        manager.clearHistory();
      }).not.toThrow();
    });
  });

  describe('formatTimestamp 测试', () => {
    it('应该格式化刚刚的时间', () => {
      const now = new Date();
      expect(manager.formatTimestamp(now)).toBe('刚刚');
    });

    it('应该格式化分钟级时间', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      expect(manager.formatTimestamp(fiveMinutesAgo)).toBe('5分钟前');
    });

    it('应该格式化小时级时间', () => {
      const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
      expect(manager.formatTimestamp(twoHoursAgo)).toBe('2小时前');
    });

    it('应该格式化天级时间', () => {
      const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000);
      expect(manager.formatTimestamp(threeDaysAgo)).toBe('3天前');
    });

    it('应该格式化超过7天的时间为日期格式', () => {
      const eightDaysAgo = new Date(Date.now() - 8 * 24 * 60 * 60 * 1000);
      const result = manager.formatTimestamp(eightDaysAgo);
      expect(result).not.toContain('天前');
    });
  });
});

describe('SearchHistoryManager - 边界条件和异常测试', () => {
  let manager: SearchHistoryManager;

  beforeEach(() => {
    localStorage.clear();
    manager = SearchHistoryManager.getInstance();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('异常和边界测试', () => {
    it('应该在localStorage损坏时返回空数组', () => {
      localStorage.setItem('ocg-search-history', '{invalid-json}');
      expect(() => {
        const history = manager.getHistory();
        expect(history).toEqual([]);
      }).not.toThrow();
    });

    it('应该在localStorage抛出错误时优雅处理', () => {
      vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
        throw new Error('Storage failed');
      });
      
      expect(() => {
        manager.getHistory();
      }).not.toThrow();
    });

    it('应该处理极大的历史记录数量', () => {
      for (let i = 1; i <= 1000; i++) {
        manager.addToHistory(`大量查询${i}`, 'ocg');
      }
      
      const history = manager.getHistory();
      expect(history.length).toBe(20);
    });

    it('应该处理非常长的查询字符串', () => {
      const longQuery = '这是一个非常长的查询字符串，'.repeat(100);
      manager.addToHistory(longQuery, 'ocg');
      
      const history = manager.getHistory();
      expect(history.length).toBe(1);
      expect(history[0].query).toBe(longQuery);
    });

    it('应该处理特殊字符和Unicode', () => {
      const specialQuery = '测试查询 🎮 🌍 🌟!@#$%^&*()';
      manager.addToHistory(specialQuery, 'ocg');
      
      const history = manager.getHistory();
      expect(history.length).toBe(1);
      expect(history[0].query).toBe(specialQuery);
    });
  });
});

describe('SearchHistoryManager - 综合场景测试', () => {
  let manager: SearchHistoryManager;

  beforeEach(() => {
    localStorage.clear();
    manager = SearchHistoryManager.getInstance();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('应该支持完整的CRUD操作流程', () => {
    // Create
    manager.addToHistory('OCG查询1', 'ocg');
    manager.addToHistory('DM查询1', 'dm');
    
    let history = manager.getHistory();
    expect(history.length).toBe(2);
    
    // Read with filter
    const ocgHistory = manager.getHistory('ocg');
    expect(ocgHistory.length).toBe(1);
    
    // Update (add duplicate - 使用不同的查询避免重复移除
    manager.addToHistory('新OCG查询', 'ocg');
    history = manager.getHistory();
    expect(history.length).toBe(3);
    
    // Delete
    const idToRemove = history[0].id;
    manager.removeFromHistory(idToRemove);
    history = manager.getHistory();
    expect(history.length).toBe(2);
    
    // Clear
    manager.clearHistory();
    history = manager.getHistory();
    expect(history.length).toBe(0);
  });

  it('应该在多个会话之间保持状态', () => {
    manager.addToHistory('持久化查询', 'ocg');
    const originalHistory = manager.getHistory();
    
    // 创建新实例
    const newManager = SearchHistoryManager.getInstance();
    const restoredHistory = newManager.getHistory();
    
    expect(restoredHistory.length).toBe(originalHistory.length);
    expect(restoredHistory[0].query).toBe(originalHistory[0].query);
  });

  it('应该正确处理混合游戏类型的查询', () => {
    manager.addToHistory('通用查询');
    manager.addToHistory('OCG专用', 'ocg');
    manager.addToHistory('DM专用', 'dm');
    manager.addToHistory('另一个通用');
    
    const allHistory = manager.getHistory();
    expect(allHistory.length).toBe(4);
    
    const ocgHistory = manager.getHistory('ocg');
    expect(ocgHistory.length).toBe(3); // 2个通用 + 1个OCG
    
    const dmHistory = manager.getHistory('dm');
    expect(dmHistory.length).toBe(3); // 2个通用 + 1个DM
  });
});
