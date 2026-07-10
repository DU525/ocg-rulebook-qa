import { useState } from 'react';
import { FiChevronDown, FiSearch } from 'react-icons/fi';
import type { RetrievalSource } from '../types';

interface RetrievalTracePanelProps {
  /** 检索来源片段列表 */
  sources: RetrievalSource[];
  /** 是否深色主题（经典 UI 中 isDm=true 为深色；现代 UI 中 isDark=true 为深色） */
  isDark?: boolean;
}

/** 来源类型标签配置：颜色 + 中文标签 */
const SOURCE_TYPE_CONFIG: Record<
  RetrievalSource['sourceType'],
  { label: string; darkClass: string; lightClass: string }
> = {
  BM25: {
    label: 'BM25',
    darkClass: 'bg-blue-900/60 text-blue-300 border border-blue-700/50',
    lightClass: 'bg-blue-100 text-blue-700 border border-blue-200',
  },
  vector: {
    label: '向量',
    darkClass: 'bg-purple-900/60 text-purple-300 border border-purple-700/50',
    lightClass: 'bg-purple-100 text-purple-700 border border-purple-200',
  },
  RRF: {
    label: 'RRF',
    darkClass: 'bg-amber-900/60 text-amber-300 border border-amber-700/50',
    lightClass: 'bg-amber-100 text-amber-700 border border-amber-200',
  },
};

/** 截断文本到指定长度 */
function truncate(text: string, maxLen: number = 100): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

/**
 * 检索溯源面板
 * 在 AI 回复消息下方展示 Top-3 检索片段，包含来源类型标签、相关度分数和文本摘要。
 * 默认折叠，点击标题展开/收起，带 max-height 过渡动画。
 */
export default function RetrievalTracePanel({
  sources,
  isDark = false,
}: RetrievalTracePanelProps) {
  const [expanded, setExpanded] = useState(false);

  // 仅展示 Top-3
  const topSources = sources.slice(0, 3);

  if (topSources.length === 0) return null;

  return (
    <div
      className={`mt-3 rounded-lg border overflow-hidden transition-colors ${
        isDark
          ? 'bg-slate-800/60 border-slate-700'
          : 'bg-gray-50 border-gray-200'
      }`}
    >
      {/* 折叠标题栏 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full flex items-center justify-between px-3 py-2 text-xs font-medium transition-colors ${
          isDark
            ? 'text-slate-300 hover:bg-slate-700/50'
            : 'text-gray-600 hover:bg-gray-100'
        }`}
        aria-expanded={expanded}
      >
        <span className="flex items-center gap-1.5">
          <FiSearch className="w-3.5 h-3.5" />
          检索溯源
          <span
            className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] ${
              isDark
                ? 'bg-slate-700 text-slate-400'
                : 'bg-gray-200 text-gray-500'
            }`}
          >
            {topSources.length}
          </span>
        </span>
        <FiChevronDown
          className={`w-4 h-4 transition-transform duration-300 ${
            expanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* 展开内容：使用 max-height 过渡动画 */}
      <div
        className={`transition-all duration-300 ease-in-out overflow-hidden ${
          expanded ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-3 pb-3 space-y-2">
          {topSources.map((source, idx) => {
            const config = SOURCE_TYPE_CONFIG[source.sourceType] || SOURCE_TYPE_CONFIG.BM25;
            const percentage = Math.round(source.score * 100);

            return (
              <div
                key={idx}
                className={`rounded-md p-2.5 text-left ${
                  isDark
                    ? 'bg-slate-900/50 border border-slate-700/50'
                    : 'bg-white border border-gray-200'
                }`}
              >
                {/* 来源标签 + 相关度分数 */}
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                      isDark ? config.darkClass : config.lightClass
                    }`}
                  >
                    {config.label}
                  </span>
                  <span
                    className={`text-[10px] font-mono ${
                      percentage >= 80
                        ? isDark ? 'text-green-400' : 'text-green-600'
                        : percentage >= 60
                          ? isDark ? 'text-yellow-400' : 'text-yellow-600'
                          : isDark ? 'text-slate-400' : 'text-gray-500'
                    }`}
                  >
                    相关度 {percentage}%
                  </span>
                </div>
                {/* 文本摘要（截断 100 字） */}
                <p
                  className={`text-xs leading-relaxed line-clamp-3 ${
                    isDark ? 'text-slate-300' : 'text-gray-600'
                  }`}
                >
                  {source.title && (
                    <span
                      className={`font-medium mr-1 ${
                        isDark ? 'text-slate-200' : 'text-gray-800'
                      }`}
                    >
                      {source.title}:
                    </span>
                  )}
                  {truncate(source.text, 100)}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
