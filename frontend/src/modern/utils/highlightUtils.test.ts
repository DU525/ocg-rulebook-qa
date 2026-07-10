import { describe, it, expect } from 'vitest';
import { splitTextForHighlight } from './highlightUtils';

describe('splitTextForHighlight - 基础功能测试', () => {
  it('应该返回完整的非高亮文本当查询为空', () => {
    const result = splitTextForHighlight('测试文本', '');
    expect(result).toEqual([{ text: '测试文本', isHighlight: false }]);
  });

  it('应该正确分割文本并标记匹配的部分', () => {
    const result = splitTextForHighlight('这是一段测试文本', '测试');
    expect(result).toEqual([
      { text: '这是一段', isHighlight: false },
      { text: '测试', isHighlight: true },
      { text: '文本', isHighlight: false },
    ]);
  });
});

describe('splitTextForHighlight - 大小写处理测试', () => {
  it('应该支持大小写不敏感的匹配', () => {
    const result = splitTextForHighlight('Test Text', 'test');
    expect(result).toContainEqual({ text: 'Test', isHighlight: true });
  });

  it('应该处理混合大小写的文本和查询', () => {
    const result = splitTextForHighlight('HeLLo WoRLd', 'hello');
    expect(result).toContainEqual({ text: 'HeLLo', isHighlight: true });
  });
});

describe('splitTextForHighlight - 边界条件测试', () => {
  it('应该正确处理没有匹配的情况', () => {
    const result = splitTextForHighlight('这是一段测试文本', '不存在');
    expect(result).toEqual([{ text: '这是一段测试文本', isHighlight: false }]);
  });

  it('应该正确处理查询比文本长的情况', () => {
    const result = splitTextForHighlight('短文本', '很长的查询字符串');
    expect(result).toEqual([{ text: '短文本', isHighlight: false }]);
  });

  it('应该处理空文本', () => {
    const result = splitTextForHighlight('', '查询');
    expect(result).toEqual([{ text: '', isHighlight: false }]);
  });

  it('应该处理空查询', () => {
    const result = splitTextForHighlight('任意文本', '');
    expect(result).toEqual([{ text: '任意文本', isHighlight: false }]);
  });
});

describe('splitTextForHighlight - 特殊字符测试', () => {
  it('应该正确处理包含特殊字符的查询', () => {
    const result = splitTextForHighlight('这是一段[测试]文本', '[测试]');
    expect(result).toEqual([
      { text: '这是一段', isHighlight: false },
      { text: '[测试]', isHighlight: true },
      { text: '文本', isHighlight: false },
    ]);
  });

  it('应该处理正则表达式特殊字符', () => {
    const result = splitTextForHighlight('这是(测试)文本', '(测试)');
    expect(result).toEqual([
      { text: '这是', isHighlight: false },
      { text: '(测试)', isHighlight: true },
      { text: '文本', isHighlight: false },
    ]);
  });

  it('应该处理所有特殊字符的组合', () => {
    const text = '这是.*+?^${}()[]\\/|文本';
    const query = '.*+?^${}()[]\\/|';
    const result = splitTextForHighlight(text, query);
    expect(result.some(item => item.isHighlight)).toBeTruthy();
  });
});

describe('splitTextForHighlight - 多次匹配测试', () => {
  it('应该处理文本中出现多次相同查询的情况', () => {
    const result = splitTextForHighlight('测试这是测试测试文本', '测试');
    expect(result.filter(item => item.isHighlight).length).toBe(3);
  });

  it('应该正确标记连续出现的匹配', () => {
    const result = splitTextForHighlight('aaabaaa', 'a');
    const highlightCount = result.filter(item => item.isHighlight).length;
    expect(highlightCount).toBeGreaterThan(0);
  });
});

describe('splitTextForHighlight - 多语言和Unicode测试', () => {
  it('应该正确处理中文文本', () => {
    const result = splitTextForHighlight('游戏王规则问答', '规则');
    expect(result).toContainEqual({ text: '规则', isHighlight: true });
  });

  it('应该正确处理日文文本', () => {
    const result = splitTextForHighlight('ゲームのルールです', 'ルール');
    expect(result).toContainEqual({ text: 'ルール', isHighlight: true });
  });

  it('应该处理emoji和特殊符号', () => {
    const result = splitTextForHighlight('🎮 游戏王 🎉', '游戏王');
    expect(result).toContainEqual({ text: '游戏王', isHighlight: true });
  });
});

describe('splitTextForHighlight - 精确匹配测试', () => {
  it('应该只高亮精确匹配的部分', () => {
    const result = splitTextForHighlight('这是一段很长的测试文本', '长');
    const highlightedItems = result.filter(item => item.isHighlight);
    expect(highlightedItems.every(item => item.text === '长')).toBeTruthy();
  });

  it('应该正确处理部分匹配的情况', () => {
    // 注意：splitTextForHighlight 会匹配子字符串，这是正常行为
    const result = splitTextForHighlight('testing', 'test');
    expect(result.some(item => item.isHighlight)).toBeTruthy();
  });
});

describe('splitTextForHighlight - 综合场景测试', () => {
  it('应该正确处理复杂的混合场景', () => {
    const text = '这是1段包含Test TEST 测试 [特殊]字符的文本';
    const result = splitTextForHighlight(text, 'test');
    expect(result.some(item => item.isHighlight)).toBeTruthy();
  });

  it('应该正确处理超长文本', () => {
    const longText = '这是一段很长的文本，'.repeat(100) + '需要搜索的关键词' + '继续很长的文本，'.repeat(100);
    const result = splitTextForHighlight(longText, '需要搜索的关键词');
    expect(result.some(item => item.isHighlight)).toBeTruthy();
  });
});
