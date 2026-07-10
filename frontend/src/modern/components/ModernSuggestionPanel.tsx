import React from 'react';
import { FiZap } from 'react-icons/fi';

interface ModernSuggestionPanelProps {
  suggestions: string[];
  onSuggestionClick: (suggestion: string) => void;
  isDark?: boolean;
  isOcg?: boolean;
}

const ModernSuggestionPanel: React.FC<ModernSuggestionPanelProps> = ({
  suggestions,
  onSuggestionClick,
  isDark = false,
  isOcg = true
}) => {
  if (suggestions.length === 0) return null;

  return (
    <div className={`
      rounded-2xl p-4
      ${isDark ? 'bg-slate-800/50 border border-slate-700' : 'bg-white border border-gray-200'}
    `}>
      <div className={`
        flex items-center space-x-2 mb-3
        ${isDark ? 'text-purple-400' : 'text-blue-600'}
      `}>
        <FiZap className="w-4 h-4" />
        <span className="text-sm font-medium">快捷问题</span>
      </div>
      
      <div className="flex flex-wrap gap-2">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSuggestionClick(suggestion)}
            className={`
              text-sm px-3 py-2 rounded-xl transition-all duration-300
              ${isOcg
                ? 'bg-blue-50 text-blue-700 hover:bg-blue-100 hover:text-blue-800'
                : 'bg-purple-50 text-purple-700 hover:bg-purple-100 hover:text-purple-800'
              }
              ${isDark
                ? 'bg-slate-700/50 hover:bg-slate-700'
                : ''
              }
              hover:shadow-md active:scale-95
            `}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
};

export default ModernSuggestionPanel;
