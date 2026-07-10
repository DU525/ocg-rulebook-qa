import React, { useRef, useEffect, useCallback } from 'react';
import { useChat } from '../hooks/useChat';
import { useDmChat } from '../dm/useDmChat';
import { useAppStore } from '../stores/appStore';
import { useDmStore } from '../dm/dmStore';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import SuggestionPanel from './SuggestionPanel';

interface ChatWindowProps {
  isDm?: boolean;
}

export default function ChatWindow({ isDm = false }: ChatWindowProps) {
  const { messages: ocgMessages, sendMessage: sendOcgMessage, error: ocgError } = useChat();
  const { messages: dmMessages, sendMessage: sendDmMessage, error: dmError } = useDmChat();
  
  const { isLoading: ocgLoading, currentConversation, setMessages, clearCurrentConversation } = useAppStore();
  const { dmIsLoading, dmCurrentConversation, setDmMessages, clearDmCurrentConversation } = useDmStore();
  
  const [input, setInput] = React.useState('');
  const [selectedCitation, setSelectedCitation] = React.useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const rafIdRef = useRef<number | null>(null);

  const messages = isDm ? dmMessages : ocgMessages;
  const isLoading = isDm ? dmIsLoading : ocgLoading;
  const currentConversationData = isDm ? dmCurrentConversation : currentConversation;
  const setMessagesFn = isDm ? setDmMessages : setMessages;
  const clearConversation = isDm ? clearDmCurrentConversation : clearCurrentConversation;
  const sendMessage = isDm ? sendDmMessage : sendOcgMessage;
  const error = isDm ? dmError : ocgError;

  const isStreaming = isLoading && messages.length > 0 && messages[messages.length - 1].role === 'assistant';
  const typingMessageId = isStreaming ? messages[messages.length - 1].id : null;

  // 当切换对话时，加载对话历史消息
  useEffect(() => {
    if (currentConversationData && currentConversationData.messages.length > 0) {
      const recentMessages = currentConversationData.messages.slice(-20);
      setMessagesFn(recentMessages);
    } else if (!currentConversationData) {
      setMessagesFn([]);
    }
  }, [currentConversationData, setMessagesFn]);

  const scrollToBottom = useCallback(() => {
    if (!shouldAutoScrollRef.current) return;
    
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
    }
    
    rafIdRef.current = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      rafIdRef.current = null;
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, []);

  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    shouldAutoScrollRef.current = isNearBottom;
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      if (!currentConversationData) {
        clearConversation();
      }
      await sendMessage(input.trim());
      setInput('');
    }
  };

  const placeholder = isDm 
    ? "输入您关于数码宝贝卡牌游戏规则的问题..." 
    : "输入您关于游戏王OCG规则的问题...";
  
  const welcomeTitle = isDm ? "欢迎使用数码宝贝DCG规则问答" : "欢迎使用OCG规则问答";
  const welcomeDesc = isDm ? "基于官方规则书的数码宝贝卡牌游戏智能问答助手" : "基于官方规则书的智能问答助手";
  
  const exampleQuestions = isDm ? [
    "「内存指示物的规则是什么？」",
    "「数码宝贝如何进化？」",
    "「安全区攻击的规则是什么？」"
  ] : [
    "「什么是通常召唤？」",
    "「灵摆召唤的规则是什么？」",
    "「陷阱卡和魔法卡有什么区别？」"
  ];

  const handleSuggestionSelect = (question: string) => {
    setInput(question);
    setTimeout(() => {
      if (input.trim() && !isLoading) {
        if (!currentConversationData) {
          clearConversation();
        }
        sendMessage(question.trim());
        setInput('');
      }
    }, 100);
  };

  return (
    <div className="flex flex-col h-full">
      <div ref={containerRef} onScroll={handleScroll} className={`flex-1 overflow-y-auto p-4 space-y-4 ${isDm ? 'scrollbar-dm' : 'scrollbar-thin'}`}>
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className={`text-center ${isDm ? 'text-dm-200' : 'text-gray-500'}`}>
              <div className="text-6xl mb-4">
                {isDm ? (
                  <img
                    src="/src/assets/logo.png"
                    alt=""
                    className="w-20 h-20 mx-auto object-contain rounded-lg"
                  />
                ) : (
                  <svg className="w-16 h-16 mx-auto text-ocg-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
              </div>
              <h2 className={`text-xl font-semibold mb-2 ${isDm ? 'text-white' : 'text-gray-700'}`}>
                {welcomeTitle}
              </h2>
              <p className={`text-sm ${isDm ? 'text-dm-300' : 'text-gray-500'}`}>
                {welcomeDesc}
              </p>
              <div className={`mt-4 text-sm ${isDm ? 'text-dm-400' : 'text-gray-400'}`}>
                <p>你可以问：</p>
                <ul className="mt-2 space-y-1">
                  {exampleQuestions.map((q, i) => (
                    <li key={i}>「{q}」</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onCitationClick={(text) => setSelectedCitation(text)}
              isDm={isDm}
              conversationId={currentConversationData?.id}
              isTyping={message.id === typingMessageId}
            />
          ))
        )}

        {isLoading && (
          <TypingIndicator
            isDm={isDm}
            hasAssistantMessage={
              messages.length > 0 &&
              messages[messages.length - 1].role === 'assistant' &&
              messages[messages.length - 1].content.length > 0
            }
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {selectedCitation && (
        <div className={`border-t p-4 ${isDm ? 'bg-dm-900/50 border-dm-600/30' : 'bg-amber-50'}`}>
          <div className="flex justify-between items-start">
            <div className={`text-sm ${isDm ? 'text-dm-200' : ''}`}>{selectedCitation}</div>
            <button
              onClick={() => setSelectedCitation(null)}
              className={`${isDm ? 'text-dm-400 hover:text-dm-200' : 'text-gray-500 hover:text-gray-700'}`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <div className={`border-t p-4 ${isDm ? 'bg-dm-800 border-dm-600/30' : 'bg-white'}`}>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={placeholder}
            className={`flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-colors ${
              isDm 
                ? 'bg-dm-700 border-dm-500 text-white placeholder-dm-300 focus:ring-dm-400 focus:border-dm-400' 
                : 'border-gray-300 focus:ring-primary-500 focus:border-transparent'
            }`}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={`px-6 py-2 text-white rounded-lg hover:disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2 ${
              isDm 
                ? 'bg-gradient-to-r from-dm-500 to-dm-600 hover:from-dm-600 hover:to-dm-700' 
                : 'bg-primary-500 hover:bg-primary-600'
            }`}
          >
            {isLoading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                发送中...
              </>
            ) : '发送'}
          </button>
        </form>
        {error && (
          <div className={`mt-2 text-sm flex items-center gap-2 ${isDm ? 'text-red-400' : 'text-red-500'}`}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}