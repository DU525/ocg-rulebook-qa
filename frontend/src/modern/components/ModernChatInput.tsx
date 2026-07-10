import React, { useState } from 'react';
import { FiSend, FiPaperclip, FiMic } from 'react-icons/fi';

interface ModernChatInputProps {
  onSend: (message: string) => void;
  isDark?: boolean;
  isOcg?: boolean;
  disabled?: boolean;
}

const ModernChatInput: React.FC<ModernChatInputProps> = ({
  onSend,
  isDark = false,
  isOcg = true,
  disabled = false
}) => {
  const [message, setMessage] = useState('');

  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSend(message);
      setMessage('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`
      rounded-2xl border-2 p-2
      ${isDark 
        ? 'bg-slate-800 border-slate-700' 
        : 'bg-white border-gray-200'
      }
      ${disabled ? 'opacity-50' : ''}
      transition-all duration-300
    `}>
      <div className="flex items-end space-x-2">
        {/* 输入框 */}
        <div className="flex-1">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入您的问题..."
            disabled={disabled}
            className={`
              w-full px-4 py-3 rounded-xl resize-none
              focus:outline-none
              ${isDark 
                ? 'bg-slate-900 text-white placeholder-slate-500' 
                : 'bg-gray-50 text-gray-900 placeholder-gray-400'
              }
              ${disabled ? 'cursor-not-allowed' : ''}
            `}
            rows={1}
          />
        </div>

        {/* 附件按钮 */}
        <button
          className={`
            p-3 rounded-xl transition-all duration-300
            ${isDark 
              ? 'bg-slate-700 text-slate-400 hover:bg-slate-600' 
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }
          `}
        >
          <FiPaperclip className="w-5 h-5" />
        </button>

        {/* 发送按钮 */}
        <button
          onClick={handleSend}
          disabled={!message.trim() || disabled}
          className={`
            p-3 rounded-xl transition-all duration-300
            ${message.trim() && !disabled
              ? isOcg
                ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg hover:shadow-xl'
                : 'bg-gradient-to-br from-purple-500 to-purple-600 text-white shadow-lg hover:shadow-xl'
              : isDark
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
            }
          `}
        >
          <FiSend className="w-5 h-5" />
        </button>
      </div>

      {/* 快捷提示 */}
      <div className={`
        mt-2 flex items-center space-x-2 text-xs
        ${isDark ? 'text-slate-500' : 'text-gray-400'}
      `}>
        <span>按</span>
        <kbd className={`
          px-2 py-0.5 rounded
          ${isDark ? 'bg-slate-700' : 'bg-gray-100'}
        `}>Enter</kbd>
        <span>发送</span>
        <span className="mx-2">|</span>
        <span>按</span>
        <kbd className={`
          px-2 py-0.5 rounded
          ${isDark ? 'bg-slate-700' : 'bg-gray-100'}
        `}>Shift + Enter</kbd>
        <span>换行</span>
      </div>
    </div>
  );
};

export default ModernChatInput;
