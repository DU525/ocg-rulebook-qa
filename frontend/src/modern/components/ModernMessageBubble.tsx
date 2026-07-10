import React from 'react';
import { FiUser, FiCpu } from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { RetrievalSource } from '../../types';
import RetrievalTracePanel from '../../components/RetrievalTracePanel';

interface ModernMessageBubbleProps {
  message: {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    citations?: any[];
    confidence?: number;
    // 检索溯源数据（Top-3 检索片段）
    sources?: RetrievalSource[];
  };
  isDark?: boolean;
  isOcg?: boolean;
}

const ModernMessageBubble: React.FC<ModernMessageBubbleProps> = ({
  message,
  isDark = false,
  isOcg = true
}) => {
  const isUser = message.role === 'user';
  
  return (
    <div className={`
      flex items-start space-x-3 animate-fade-in-up
      ${isUser ? 'flex-row-reverse space-x-reverse' : ''}
    `}>
      {/* 头像 */}
      <div className={`
        flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center
        ${isUser 
          ? isOcg
            ? 'bg-gradient-to-br from-blue-500 to-blue-600'
            : 'bg-gradient-to-br from-purple-500 to-purple-600'
          : isDark
            ? 'bg-slate-700'
            : 'bg-gray-100'
        }
      `}>
        {isUser ? (
          <FiUser className="w-5 h-5 text-white" />
        ) : (
          <FiCpu className={`w-5 h-5 ${isDark ? 'text-slate-300' : 'text-gray-600'}`} />
        )}
      </div>

      {/* 消息内容 */}
      <div className={`
        flex-1 max-w-[70%]
        ${isUser ? 'items-end' : 'items-start'}
      `}>
        <div
          className={`
            rounded-2xl px-5 py-3
            ${isUser
              ? isOcg
                ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white'
                : 'bg-gradient-to-br from-purple-500 to-purple-600 text-white'
              : isDark
                ? 'bg-slate-800 text-white border border-slate-700'
                : 'bg-white text-gray-900 border border-gray-200 shadow-sm'
            }
            ${isUser ? 'rounded-br-sm' : 'rounded-bl-sm'}
          `}
        >
          {!isUser && (
            <div className="mb-2">
              <span className={`
                text-xs font-medium
                ${isDark ? 'text-purple-400' : 'text-blue-600'}
              `}>
                AI助手
              </span>
              {message.confidence && (
                <span className={`
                  ml-2 text-xs
                  ${isDark ? 'text-slate-400' : 'text-gray-500'}
                `}>
                  置信度: {(message.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>
          )}
          
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => (
                  <p className={`mb-2 last:mb-0 ${isUser ? 'text-white' : isDark ? 'text-slate-200' : 'text-gray-800'}`}>
                    {children}
                  </p>
                ),
                code: ({ children, className }) => {
                  const isInline = !className;
                  return isInline ? (
                    <code className={`
                      px-1.5 py-0.5 rounded text-sm font-mono
                      ${isUser 
                        ? 'bg-blue-700/50 text-blue-100' 
                        : isDark
                          ? 'bg-slate-700 text-purple-300'
                          : 'bg-gray-100 text-gray-800'
                      }
                    `}>
                      {children}
                    </code>
                  ) : (
                    <code className={`
                      block p-3 rounded-lg text-sm font-mono overflow-x-auto
                      ${isDark ? 'bg-slate-900 text-green-400' : 'bg-gray-900 text-green-400'}
                    `}>
                      {children}
                    </code>
                  );
                },
                h1: ({ children }) => (
                  <h1 className={`
                    text-xl font-bold mb-3
                    ${isUser ? 'text-white' : isDark ? 'text-white' : 'text-gray-900'}
                  `}>
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className={`
                    text-lg font-semibold mb-2
                    ${isUser ? 'text-white' : isDark ? 'text-white' : 'text-gray-900'}
                  `}>
                    {children}
                  </h2>
                ),
                ul: ({ children }) => (
                  <ul className={`
                    list-disc list-inside mb-2 space-y-1
                    ${isUser ? 'text-white' : isDark ? 'text-slate-300' : 'text-gray-700'}
                  `}>
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className={`
                    list-decimal list-inside mb-2 space-y-1
                    ${isUser ? 'text-white' : isDark ? 'text-slate-300' : 'text-gray-700'}
                  `}>
                    {children}
                  </ol>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`
                      underline
                      ${isUser 
                        ? 'text-blue-200 hover:text-blue-100' 
                        : isDark
                          ? 'text-purple-400 hover:text-purple-300'
                          : 'text-blue-600 hover:text-blue-800'
                      }
                    `}
                  >
                    {children}
                  </a>
                ),
                blockquote: ({ children }) => (
                  <blockquote className={`
                    border-l-4 pl-4 italic my-2
                    ${isUser 
                      ? 'border-blue-400 text-blue-100' 
                      : isDark
                        ? 'border-purple-500 text-slate-300'
                        : 'border-blue-500 text-gray-600'
                    }
                  `}>
                    {children}
                  </blockquote>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* 引用来源 */}
          {message.citations && message.citations.length > 0 && (
            <div className={`
              mt-3 pt-3 border-t
              ${isDark ? 'border-slate-600' : 'border-gray-200'}
            `}>
              <div className={`
                text-xs font-medium mb-2
                ${isDark ? 'text-slate-400' : 'text-gray-500'}
              `}>
                引用来源 ({message.citations.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {message.citations.map((citation, index) => (
                  <button
                    key={index}
                    className={`
                      text-xs px-2 py-1 rounded-lg transition-all
                      ${isDark 
                        ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                      }
                    `}
                  >
                    {citation.source || `来源 ${index + 1}`}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 检索溯源面板：展示 Top-3 检索片段及来源类型（BM25/向量/RRF） */}
          {!isUser && message.sources && message.sources.length > 0 && (
            <RetrievalTracePanel sources={message.sources} isDark={isDark} />
          )}
        </div>
      </div>
    </div>
  );
};

export default ModernMessageBubble;
