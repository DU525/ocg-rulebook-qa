import { useState, useEffect } from 'react';
import type { ConversationSearchResult } from '../types';
import { conversationApi } from '../services/api';
import { HighlightText } from '../modern/components/HighlightText';
import { useSearchHistory } from '../modern/utils/searchHistory';
import { FiClock, FiTrash2, FiX } from 'react-icons/fi';

interface ConversationSearchProps {
  isDm: boolean;
  onSelectConversation: (id: string) => void;
}

export default function ConversationSearch({ isDm, onSelectConversation }: ConversationSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ConversationSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  
  const gameType = isDm ? 'dm' : 'ocg';
  const { history, addToHistory, removeFromHistory, clearHistory } = useSearchHistory(gameType);

  const inputBg = isDm ? 'bg-dm-800 border-dm-600 text-dm-100 placeholder-dm-400' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400';
  const resultBg = isDm ? 'bg-dm-800 hover:bg-dm-700' : 'bg-gray-50 hover:bg-gray-100';

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setShowResults(false);
      if (history.length > 0) {
        setShowHistory(true);
      }
      return;
    }

    setShowHistory(false);
    setIsSearching(true);
    const timer = setTimeout(async () => {
      try {
        const res = await conversationApi.search(query.trim(), 1, 10);
        if (res.success && res.data) {
          setResults(res.data.results);
          setShowResults(true);
        }
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setIsSearching(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [query, history.length]);

  const handleSelect = (convId: string) => {
    if (query.trim()) {
      addToHistory(query);
    }
    onSelectConversation(convId);
    setShowResults(false);
    setShowHistory(false);
    setQuery('');
  };

  const handleHistoryClick = (historyQuery: string) => {
    setQuery(historyQuery);
    setShowHistory(false);
  };

  const handleClearQuery = () => {
    setQuery('');
    setShowResults(false);
    if (history.length > 0) {
      setShowHistory(true);
    }
  };

  return (
    <div className="relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            if (!query.trim() && history.length > 0) {
              setShowHistory(true);
            }
          }}
          placeholder="搜索对话历史..."
          className={`w-full px-3 py-2 pl-9 pr-9 text-sm rounded-lg border focus:outline-none focus:ring-2 ${isDm ? 'focus:ring-dm-500' : 'focus:ring-primary-500'} ${inputBg}`}
        />
        <svg className={`absolute left-2.5 top-2.5 w-4 h-4 ${isDm ? 'text-dm-400' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        {query && (
          <button
            onClick={handleClearQuery}
            className={`absolute right-2.5 top-2.5 p-0.5 rounded-full hover:bg-black/10 ${isDm ? 'text-dm-400 hover:text-dm-200' : 'text-gray-400 hover:text-gray-600'}`}
          >
            <FiX className="w-3.5 h-3.5" />
          </button>
        )}
        {isSearching && (
          <div className="absolute right-2.5 top-2.5">
            <div className={`w-4 h-4 border-2 rounded-full animate-spin ${isDm ? 'border-dm-400 border-t-transparent' : 'border-gray-400 border-t-transparent'}`} />
          </div>
        )}
      </div>

      {/* 搜索结果 */}
      {showResults && results.length > 0 && (
        <div className={`absolute z-50 w-full mt-1 rounded-lg shadow-lg border ${isDm ? 'bg-dm-900 border-dm-700' : 'bg-white border-gray-200'} max-h-80 overflow-y-auto`}>
          {results.map((result) => (
            <button
              key={result.message_id}
              onClick={() => handleSelect(result.conversation_id)}
              className={`w-full text-left px-3 py-2.5 border-b last:border-b-0 ${isDm ? 'border-dm-700' : 'border-gray-100'} ${resultBg}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`text-xs font-medium truncate ${isDm ? 'text-dm-300' : 'text-gray-600'}`}>
                  <HighlightText 
                    text={result.conversation_title} 
                    query={query} 
                    highlightClass={isDm ? 'bg-purple-500/30 text-purple-100 px-0.5 rounded' : 'bg-yellow-200 text-yellow-800 px-0.5 rounded'} 
                  />
                </span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  result.role === 'user'
                    ? isDm ? 'bg-dm-700 text-dm-200' : 'bg-blue-100 text-blue-700'
                    : isDm ? 'bg-dm-600 text-dm-100' : 'bg-green-100 text-green-700'
                }`}>
                  {result.role === 'user' ? '我' : '助手'}
                </span>
              </div>
              <p className={`text-xs line-clamp-2 ${isDm ? 'text-dm-400' : 'text-gray-500'}`}>
                <HighlightText 
                  text={result.matched_context} 
                  query={query} 
                  highlightClass={isDm ? 'bg-purple-500/30 text-purple-100 px-0.5 rounded' : 'bg-yellow-200 text-yellow-800 px-0.5 rounded'} 
                />
              </p>
            </button>
          ))}
        </div>
      )}

      {/* 搜索历史 */}
      {showHistory && history.length > 0 && (
        <div className={`absolute z-50 w-full mt-1 rounded-lg shadow-lg border ${isDm ? 'bg-dm-900 border-dm-700' : 'bg-white border-gray-200'} max-h-64 overflow-y-auto`}>
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-dm-700">
            <span className={`text-xs font-medium flex items-center gap-1.5 ${isDm ? 'text-dm-300' : 'text-gray-600'}`}>
              <FiClock className="w-3 h-3" />
              搜索历史
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                clearHistory();
                setShowHistory(false);
              }}
              className={`text-xs flex items-center gap-1 hover:underline ${isDm ? 'text-dm-400 hover:text-dm-200' : 'text-gray-500 hover:text-gray-700'}`}
            >
              <FiTrash2 className="w-3 h-3" />
              清空
            </button>
          </div>
          {history.map((item) => (
            <div key={item.id} className="group flex items-center gap-2 px-3 py-2 border-b last:border-b-0 border-gray-100 dark:border-dm-700 hover:bg-gray-50 dark:hover:bg-dm-800">
              <button
                onClick={() => handleHistoryClick(item.query)}
                className="flex-1 text-left"
              >
                <span className={`text-sm truncate ${isDm ? 'text-dm-200' : 'text-gray-800'}`}>
                  {item.query}
                </span>
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeFromHistory(item.id);
                }}
                className={`p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity ${isDm ? 'text-dm-500 hover:text-dm-300 hover:bg-dm-700' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
              >
                <FiX className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 无结果 */}
      {showResults && results.length === 0 && !isSearching && (
        <div className={`absolute z-50 w-full mt-1 rounded-lg shadow-lg border px-3 py-4 text-center text-sm ${isDm ? 'bg-dm-900 border-dm-700 text-dm-400' : 'bg-white border-gray-200 text-gray-500'}`}>
          未找到相关对话
        </div>
      )}
    </div>
  );
}
