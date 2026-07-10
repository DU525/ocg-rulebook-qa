import { useState, useEffect, useCallback } from 'react';
import { FiX, FiClock, FiDatabase, FiRefreshCw, FiZap } from 'react-icons/fi';
import { memoryApi, type MemoryItem, type MemoryStats } from '../services/memoryApi';

interface MemorySidebarProps {
  /** 是否深色主题（经典 UI 中 isDm=true 为深色；现代 UI 中 isDark=true 为深色） */
  isDark?: boolean;
  /** 关闭侧栏回调 */
  onClose?: () => void;
}

/** 格式化时间戳为简短显示 */
function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffMin < 1) return '刚刚';
    if (diffMin < 60) return `${diffMin}分钟前`;
    if (diffHour < 24) return `${diffHour}小时前`;
    if (diffDay < 7) return `${diffDay}天前`;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

/** 单条记忆卡片 */
function MemoryCard({
  item,
  isDark,
}: {
  item: MemoryItem;
  isDark: boolean;
}) {
  return (
    <div
      className={`rounded-lg p-2.5 text-xs transition-colors ${
        isDark
          ? 'bg-slate-800/60 border border-slate-700/50 hover:border-slate-600'
          : 'bg-white border border-gray-200 hover:border-gray-300'
      }`}
    >
      <p
        className={`leading-relaxed line-clamp-2 ${
          isDark ? 'text-slate-300' : 'text-gray-700'
        }`}
      >
        {item.content}
      </p>
      <div className="flex items-center justify-between mt-1.5">
        <span className={`text-[10px] ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>
          {formatTime(item.createdAt)}
        </span>
        {item.importance != null && (
          <span
            className={`text-[10px] px-1 py-0.5 rounded ${
              item.importance >= 0.7
                ? isDark ? 'bg-amber-900/50 text-amber-300' : 'bg-amber-100 text-amber-700'
                : isDark ? 'bg-slate-700 text-slate-400' : 'bg-gray-100 text-gray-500'
            }`}
          >
            重要度 {Math.round(item.importance * 100)}%
          </span>
        )}
      </div>
    </div>
  );
}

/** 空状态提示 */
function EmptyState({ isDark }: { isDark: boolean }) {
  return (
    <div className={`text-center py-6 text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>
      暂无记忆数据
    </div>
  );
}

/**
 * 对话记忆侧栏
 * 展示系统当前记住的上下文，分为"短期记忆"和"长期记忆"两个区域。
 * 宽度约 280px，深色主题，卡片样式，每条一行摘要 + 时间戳。
 */
export default function MemorySidebar({ isDark = false, onClose }: MemorySidebarProps) {
  const [shortTerm, setShortTerm] = useState<MemoryItem[]>([]);
  const [longTerm, setLongTerm] = useState<MemoryItem[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadMemory = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    try {
      const state = await memoryApi.getAll(5, 20);
      setShortTerm(state.shortTerm);
      setLongTerm(state.longTerm);
      setStats(state.stats);
    } catch {
      // 静默失败，保持空状态
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadMemory();
    // 每 30 秒自动刷新一次记忆数据
    const interval = setInterval(() => loadMemory(), 30000);
    return () => clearInterval(interval);
  }, [loadMemory]);

  return (
    <div
      className={`w-[280px] flex-shrink-0 flex flex-col h-full border-l overflow-hidden ${
        isDark
          ? 'bg-slate-900/80 border-slate-700/50'
          : 'bg-gray-50 border-gray-200'
      }`}
    >
      {/* 标题栏 */}
      <div
        className={`flex items-center justify-between px-3 py-3 border-b ${
          isDark ? 'border-slate-700/50' : 'border-gray-200'
        }`}
      >
        <div className="flex items-center gap-2">
          <FiZap className={`w-4 h-4 ${isDark ? 'text-purple-400' : 'text-blue-500'}`} />
          <h3 className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-800'}`}>
            对话记忆
          </h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => loadMemory(true)}
            disabled={refreshing}
            className={`p-1.5 rounded-lg transition-colors ${
              isDark
                ? 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
            }`}
            title="刷新记忆"
          >
            <FiRefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className={`p-1.5 rounded-lg transition-colors ${
                isDark
                  ? 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
              }`}
              title="关闭"
            >
              <FiX className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* 统计概览 */}
      {stats && (
        <div
          className={`flex items-center justify-around px-3 py-2 border-b text-[11px] ${
            isDark ? 'border-slate-700/50 text-slate-400' : 'border-gray-200 text-gray-500'
          }`}
        >
          <span>短期 {stats.shortTermCount}</span>
          <span className={isDark ? 'text-slate-600' : 'text-gray-300'}>|</span>
          <span>长期 {stats.longTermCount}</span>
          <span className={isDark ? 'text-slate-600' : 'text-gray-300'}>|</span>
          <span>工作 {stats.workingCount}</span>
        </div>
      )}

      {/* 记忆列表 */}
      <div className={`flex-1 overflow-y-auto p-3 space-y-4 ${isDark ? 'scrollbar-thin' : ''}`}>
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className={`h-16 rounded-lg animate-pulse ${
                  isDark ? 'bg-slate-800' : 'bg-gray-200'
                }`}
              />
            ))}
          </div>
        ) : (
          <>
            {/* 短期记忆区域 */}
            <div>
              <div
                className={`flex items-center gap-1.5 mb-2 text-xs font-medium ${
                  isDark ? 'text-slate-400' : 'text-gray-600'
                }`}
              >
                <FiClock className="w-3.5 h-3.5" />
                短期记忆
                <span
                  className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${
                    isDark ? 'bg-slate-700 text-slate-400' : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  最近 {shortTerm.length} 条
                </span>
              </div>
              <div className="space-y-2">
                {shortTerm.length > 0 ? (
                  shortTerm.map((item) => (
                    <MemoryCard key={item.id} item={item} isDark={isDark} />
                  ))
                ) : (
                  <EmptyState isDark={isDark} />
                )}
              </div>
            </div>

            {/* 长期记忆区域 */}
            <div>
              <div
                className={`flex items-center gap-1.5 mb-2 text-xs font-medium ${
                  isDark ? 'text-slate-400' : 'text-gray-600'
                }`}
              >
                <FiDatabase className="w-3.5 h-3.5" />
                长期记忆
                <span
                  className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${
                    isDark ? 'bg-slate-700 text-slate-400' : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {longTerm.length} 条
                </span>
              </div>
              <div className="space-y-2">
                {longTerm.length > 0 ? (
                  longTerm.map((item) => (
                    <MemoryCard key={item.id} item={item} isDark={isDark} />
                  ))
                ) : (
                  <EmptyState isDark={isDark} />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
