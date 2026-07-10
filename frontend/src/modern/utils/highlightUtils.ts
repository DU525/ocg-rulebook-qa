import { useState, useEffect } from 'react';

/**
 * 文本高亮逻辑函数（纯JavaScript版本，用于测试通过分割字符串为高亮片段
 * @param text 原始文本
 * @param query 搜索关键词
 * @returns 文本片段数组，标记哪些部分需要高亮
 */
export function splitTextForHighlight(
  text: string,
  query: string
): Array<{ text: string; isHighlight: boolean }> {
  if (!query.trim()) {
    return [{ text, isHighlight: false }];
  }

  // 转义正则表达式特殊字符
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  const parts = text.split(regex);

  return parts.map((part) => ({
    text: part,
    isHighlight: part.toLowerCase() === query.toLowerCase(),
  }));
}

/**
 * 防抖Hook
 * @param value 要防抖的值
 * @param delay 延迟时间(ms)
 * @returns 防抖后的值
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
