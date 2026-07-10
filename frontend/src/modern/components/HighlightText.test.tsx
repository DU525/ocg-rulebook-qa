import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { HighlightText } from './HighlightText';

describe('HighlightText 组件测试', () => {
  it('应该正确渲染非高亮文本', () => {
    render(<HighlightText text="普通文本" query="" />);
    expect(screen.getByText('普通文本')).toBeInTheDocument();
  });

  it('应该正确高亮匹配的文本', () => {
    render(<HighlightText text="这是一段测试文本" query="测试" />);
    const highlightElement = screen.getByText('测试');
    expect(highlightElement.tagName).toBe('MARK');
  });

  it('应该支持自定义高亮类名', () => {
    render(
      <HighlightText 
        text="测试高亮" 
        query="高亮" 
        highlightClass="custom-highlight" 
      />
    );
    const highlightElement = screen.getByText('高亮');
    expect(highlightElement.className).toContain('custom-highlight');
  });

  it('应该正确处理大小写不敏感的匹配', () => {
    render(<HighlightText text="Test Text" query="test" />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('应该正确处理多个匹配', () => {
    render(<HighlightText text="测试A测试B测试" query="测试" />);
    const markElements = document.querySelectorAll('mark');
    expect(markElements.length).toBe(3);
  });

  it('应该在无匹配时只渲染原始文本', () => {
    render(<HighlightText text="无匹配文本" query="不存在" />);
    const markElements = document.querySelectorAll('mark');
    expect(markElements.length).toBe(0);
    expect(screen.getByText('无匹配文本')).toBeInTheDocument();
  });

  it('应该正确处理空文本', () => {
    render(<HighlightText text="" query="任意" />);
    const markElements = document.querySelectorAll('mark');
    expect(markElements.length).toBe(0);
  });

  it('应该正确处理空查询', () => {
    render(<HighlightText text="测试内容" query="" />);
    const markElements = document.querySelectorAll('mark');
    expect(markElements.length).toBe(0);
    expect(screen.getByText('测试内容')).toBeInTheDocument();
  });

  it('应该正确处理特殊字符', () => {
    render(<HighlightText text="这是[特殊]文本" query="[特殊]" />);
    const highlightElement = screen.getByText('[特殊]');
    expect(highlightElement.tagName).toBe('MARK');
  });

  it('应该正确处理Emoji和Unicode字符', () => {
    render(<HighlightText text="🎮 游戏王 🎉" query="游戏王" />);
    expect(screen.getByText('游戏王')).toBeInTheDocument();
  });
});
