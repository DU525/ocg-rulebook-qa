import React, { useState, useEffect, useRef } from 'react';
import ModernHeader from './ModernHeader';
import ModernChatInput from './ModernChatInput';
import ModernMessageBubble from './ModernMessageBubble';
import ModernSuggestionPanel from './ModernSuggestionPanel';
import MemorySidebar from '../../components/MemorySidebar';
import { FiRefreshCw, FiTrash2, FiMessageSquare, FiZap } from 'react-icons/fi';
import { chatApi, suggestionApi } from '../../services/api';
import { simulateSourcesFromCitations } from '../../utils/retrievalSources';
import type { RetrievalSource } from '../../types';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: any[];
  confidence?: number;
  // 检索溯源数据（Top-3 检索片段）
  sources?: RetrievalSource[];
  createdAt?: string;
}

interface ModernChatAppProps {
  gameType: 'ocg' | 'dm';
  onMaintenance?: () => void;
}

const ModernChatApp: React.FC<ModernChatAppProps> = ({
  gameType,
  onMaintenance
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [memoryOpen, setMemoryOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const isOcg = gameType === 'ocg';
  const isDark = !isOcg;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadSuggestions();
  }, [gameType]);

  const loadSuggestions = async () => {
    try {
      const response = await suggestionApi.getHotSuggestions(undefined, 5, gameType);
      if (response.success && response.data?.suggestions) {
        setSuggestions(response.data.suggestions.map((s: any) => s.text || s.question));
      }
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    }
  };

  const handleSend = async (question: string) => {
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
      createdAt: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await chatApi.askQuestion(question, conversationId);
      
      if (response.success && response.data) {
        // TODO: 后端 /chat/question 响应暂未返回检索来源类型（BM25/向量/RRF），
        // 此处根据 citations 模拟生成 sources 数据，待后端支持后改用 response.data.sources
        const simulatedSources = simulateSourcesFromCitations(response.data.citations);
        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: response.data.answer,
          citations: response.data.citations,
          confidence: response.data.confidence,
          sources: simulatedSources,
          createdAt: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        
        if (response.data.conversation_id) {
          setConversationId(response.data.conversation_id);
        }
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: '抱歉，发生了错误。请稍后再试。',
        createdAt: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    handleSend(suggestion);
  };

  const handleClear = () => {
    setMessages([]);
    setConversationId(undefined);
  };

  return (
    <div className={`
      min-h-screen flex flex-col
      ${isDark 
        ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900' 
        : 'bg-gradient-to-br from-blue-50 via-white to-slate-50'
      }
    `}>
      {/* Header */}
      <ModernHeader
        currentGame={gameType}
        onGameSwitch={() => {}}
        onMaintenance={onMaintenance || (() => {})}
        isDark={isDark}
      />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Messages Area */}
        <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full p-4 relative">
          {/* 对话记忆切换按钮 */}
          <button
            onClick={() => setMemoryOpen(!memoryOpen)}
            className={`absolute top-2 right-2 z-10 p-2 rounded-lg transition-all ${
              memoryOpen
                ? isOcg
                  ? 'bg-blue-600 text-white'
                  : 'bg-purple-600 text-white'
                : isDark
                  ? 'bg-slate-700/80 text-slate-300 hover:bg-slate-600'
                  : 'bg-white/80 text-gray-500 hover:bg-gray-100 shadow-sm'
            }`}
            title="对话记忆"
          >
            <FiZap className="w-4 h-4" />
          </button>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto modern-scrollbar space-y-4 pb-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full space-y-6 animate-fade-in-up">
                {/* 欢迎信息 */}
                <div className={`
                  text-center
                  ${isDark ? 'text-white' : 'text-gray-900'}
                `}>
                  <h2 className="text-2xl font-bold mb-2">
                    欢迎使用{isOcg ? '游戏王OCG' : '数码宝贝DCG'}规则问答助手
                  </h2>
                  <p className={isDark ? 'text-slate-400' : 'text-gray-600'}>
                    基于官方规则书的智能问答系统，助您快速解答游戏王规则问题
                  </p>
                </div>

                {/* Logo */}
                <div className={`
                  w-24 h-24 rounded-2xl flex items-center justify-center
                  ${isOcg 
                    ? 'bg-gradient-to-br from-blue-500 to-blue-600' 
                    : 'bg-gradient-to-br from-purple-500 to-purple-600'
                  }
                  shadow-2xl
                `}>
                  <span className="text-white font-bold text-3xl">
                    {isOcg ? 'OCG' : 'DM'}
                  </span>
                </div>

                {/* 建议面板 */}
                {suggestions.length > 0 && (
                  <div className="w-full max-w-2xl">
                    <ModernSuggestionPanel
                      suggestions={suggestions}
                      onSuggestionClick={handleSuggestionClick}
                      isDark={isDark}
                      isOcg={isOcg}
                    />
                  </div>
                )}
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <ModernMessageBubble
                    key={message.id}
                    message={message}
                    isDark={isDark}
                    isOcg={isOcg}
                  />
                ))}
                
                {/* 加载指示器 */}
                {isLoading && (
                  <div className="flex items-start space-x-3 animate-fade-in-up">
                    <div className={`
                      flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center
                      ${isDark ? 'bg-slate-700' : 'bg-gray-100'}
                    `}>
                      <FiMessageSquare className={`w-5 h-5 ${isDark ? 'text-slate-300' : 'text-gray-600'}`} />
                    </div>
                    <div className={`
                      rounded-2xl px-5 py-3
                      ${isDark ? 'bg-slate-800 text-white' : 'bg-white text-gray-900 border border-gray-200'}
                    `}>
                      <div className="flex items-center space-x-2">
                        <div className="flex space-x-1">
                          <div className={`
                            w-2 h-2 rounded-full animate-bounce
                            ${isOcg ? 'bg-blue-500' : 'bg-purple-500'}
                          `} style={{ animationDelay: '0ms' }} />
                          <div className={`
                            w-2 h-2 rounded-full animate-bounce
                            ${isOcg ? 'bg-blue-500' : 'bg-purple-500'}
                          `} style={{ animationDelay: '150ms' }} />
                          <div className={`
                            w-2 h-2 rounded-full animate-bounce
                            ${isOcg ? 'bg-blue-500' : 'bg-purple-500'}
                          `} style={{ animationDelay: '300ms' }} />
                        </div>
                        <span className={isDark ? 'text-slate-400' : 'text-gray-500'}>
                          正在思考...
                        </span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Actions & Input */}
          <div className="space-y-3 pt-4">
            {/* Action Buttons */}
            {messages.length > 0 && (
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleClear}
                    className={`
                      px-3 py-1.5 rounded-lg text-sm transition-all
                      ${isDark 
                        ? 'text-slate-400 hover:text-white hover:bg-slate-800' 
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                      }
                    `}
                  >
                    <FiTrash2 className="w-4 h-4 inline mr-1" />
                    清空对话
                  </button>
                </div>
                <div className={`
                  text-sm
                  ${isDark ? 'text-slate-500' : 'text-gray-500'}
                `}>
                  {messages.length} 条消息
                </div>
              </div>
            )}

            {/* Input */}
            <ModernChatInput
              onSend={handleSend}
              isDark={isDark}
              isOcg={isOcg}
              disabled={isLoading}
            />
          </div>
        </div>

        {/* 对话记忆侧栏 */}
        {memoryOpen && (
          <MemorySidebar isDark={isDark} onClose={() => setMemoryOpen(false)} />
        )}
      </div>
    </div>
  );
};

export default ModernChatApp;
