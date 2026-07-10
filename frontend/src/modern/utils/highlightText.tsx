import React from 'react';
import { useState, useEffect } from 'react';

/**
 * 文本高亮工具函数
 * @param text 原始文本
 * @param query 搜索关键词
 * @param highlightClass 高亮样式类名
 * @returns 包含高亮元素的React片段
 */
export function highlightText(
  text: string,
  query: string,
  highlightClass: string = 'bg-yellow-200 text-yellow-800 px-0.5 rounded'
): React.ReactNode {
  if (!query.trim()) {
    return text;
  }

  // 转义正则表达式特殊字符
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, index) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={index} className={highlightClass}>
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </>
  );
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
