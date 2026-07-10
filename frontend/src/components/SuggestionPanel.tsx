import React, { useState, useEffect } from 'react';
import type { QuestionSuggestion } from '../types';
import { suggestionApi } from '../services/api';

interface SuggestionPanelProps {
  onSelect: (question: string) => void;
  isDm?: boolean;
  conversationId?: string;
  limit?: number;
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  '规则类': { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  '概念类': { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  '操作类': { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
};

const CATEGORY_COLORS_DM: Record<string, { bg: string; text: string; border: string }> = {
  '规则类': { bg: 'bg-purple-900/30', text: 'text-purple-300', border: 'border-purple-700/50' },
  '概念类': { bg: 'bg-cyan-900/30', text: 'text-cyan-300', border: 'border-cyan-700/50' },
  '操作类': { bg: 'bg-emerald-900/30', text: 'text-emerald-300', border: 'border-emerald-700/50' },
};

export default function SuggestionPanel({ onSelect, isDm = false, conversationId, limit = 10 }: SuggestionPanelProps) {
  const [suggestions, setSuggestions] = useState<QuestionSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [showCategories, setShowCategories] = useState(false);

  const categories = ['all', '规则类', '概念类', '操作类'];
  const categoryLabels: Record<string, string> = {
    'all': '全部',
    '规则类': '规则类',
    '概念类': '概念类',
    '操作类': '操作类',
  };

  useEffect(() => {
    const fetchSuggestions = async () => {
      setLoading(true);
      try {
        if (conversationId) {
          const response = await suggestionApi.getPersonalizedSuggestions(
            conversationId,
            limit,
            isDm ? 'dm' : 'ocg'
          );
          if (response.success && response.data) {
            setSuggestions(response.data.suggestions);
          }
        } else {
          const cat = selectedCategory === 'all' ? undefined : selectedCategory;
          const response = await suggestionApi.getHotSuggestions(
            cat,
            limit,
            isDm ? 'dm' : 'ocg'
          );
          if (response.success && response.data) {
            setSuggestions(response.data.suggestions);
          }
        }
      } catch (error) {
        console.error('Failed to fetch suggestions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSuggestions();
  }, [selectedCategory, conversationId, isDm, limit]);

  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
  };

  const handleSuggestionClick = (question: string) => {
    onSelect(question);
  };

  const getColors = (category: string) => {
    const colorMap = isDm ? CATEGORY_COLORS_DM : CATEGORY_COLORS;
    return colorMap[category] || { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' };
  };

  if (loading) {
    return (
      <div className={`p-4 ${isDm ? 'bg-dm-800/50' : 'bg-gray-50'}`}>
        <div className="flex items-center justify-center gap-2 text-sm">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className={isDm ? 'text-dm-300' : 'text-gray-500'}>加载热门问题...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-4 ${isDm ? 'bg-dm-800/50 border-dm-600/30' : 'bg-gray-50 border-gray-100'} border-t`}>
      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className={`text-sm font-semibold ${isDm ? 'text-white' : 'text-gray-700'}`}>
            <svg className="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            热门问题建议
          </h3>
          <button
            onClick={() => setShowCategories(!showCategories)}
            className={`text-xs px-2 py-1 rounded ${
              isDm 
                ? 'text-dm-300 hover:bg-dm-700' 
                : 'text-gray-500 hover:bg-gray-200'
            }`}
          >
            {showCategories ? '收起分类' : '筛选分类'}
          </button>
        </div>

        {showCategories && (
          <div className="flex gap-2 mb-3 flex-wrap">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => handleCategoryChange(cat)}
                className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                  selectedCategory === cat
                    ? isDm
                      ? 'bg-dm-600 border-dm-500 text-white'
                      : 'bg-primary-500 border-primary-500 text-white'
                    : isDm
                    ? 'border-dm-600 text-dm-300 hover:bg-dm-700'
                    : 'border-gray-300 text-gray-600 hover:bg-gray-100'
                }`}
              >
                {categoryLabels[cat]}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2">
        {suggestions.map((suggestion, index) => {
          const colors = getColors(suggestion.category);
          return (
            <button
              key={index}
              onClick={() => handleSuggestionClick(suggestion.question)}
              className={`text-left p-3 rounded-lg border transition-all hover:shadow-md ${
                isDm
                  ? 'bg-dm-800 border-dm-600/50 hover:bg-dm-700 hover:border-dm-500'
                  : `bg-white border-gray-200 hover:border-primary-300 hover:bg-primary-50/50`
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <p className={`text-sm ${isDm ? 'text-dm-100' : 'text-gray-800'}`}>
                    {suggestion.question}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`text-xs px-2 py-0.5 rounded border ${colors.bg} ${colors.text} ${colors.border}`}>
                      {suggestion.category}
                    </span>
                    {suggestion.frequency > 0 && (
                      <span className={`text-xs ${isDm ? 'text-dm-400' : 'text-gray-400'}`}>
                        {suggestion.frequency} 次查询
                      </span>
                    )}
                  </div>
                </div>
                <svg
                  className={`w-4 h-4 flex-shrink-0 ${isDm ? 'text-dm-400' : 'text-gray-400'}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </button>
          );
        })}
      </div>

      {suggestions.length === 0 && (
        <div className={`text-center py-6 text-sm ${isDm ? 'text-dm-400' : 'text-gray-500'}`}>
          暂无问题建议
        </div>
      )}
    </div>
  );
}
