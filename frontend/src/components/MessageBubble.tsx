import { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FiCopy, FiCheck } from 'react-icons/fi';
import type { Message, EnhancedCitation } from '../types';
import { feedbackApi } from '../services/api';
import { dmFeedbackApi } from '../dm/dmApi';
import CitationDetailModal from './CitationDetailModal';
import RetrievalTracePanel from './RetrievalTracePanel';

const FEEDBACK_REASONS = [
  { value: 'answer_inaccurate', label: '答案不准确' },
  { value: 'answer_irrelevant', label: '答案不相关' },
  { value: 'citation_missing', label: '引用缺失' },
  { value: 'format_issue', label: '格式问题' },
  { value: 'outdated_info', label: '信息过时' },
  { value: 'other', label: '其他' },
];

interface MessageBubbleProps {
  message: Message;
  onCitationClick: (text: string) => void;
  isDm?: boolean;
  conversationId?: string;
  isTyping?: boolean;
}

const UserAvatar = ({ isDm }: { isDm: boolean }) => (
  <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
    isDm 
      ? 'bg-gradient-to-br from-dm-400 to-dm-600 shadow-lg shadow-dm-500/30' 
      : 'bg-gradient-to-br from-primary-400 to-primary-600 shadow-lg shadow-primary-500/30'
  }`}>
    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  </div>
);

const AssistantAvatar = ({ isDm }: { isDm: boolean }) => (
  <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
    isDm
      ? 'bg-gradient-to-br from-dm-50 to-white shadow-lg border-2 border-dm-300'
      : 'bg-gradient-to-br from-blue-50 to-white shadow-lg border-2 border-primary-200'
  }`}>
    {isDm ? (
      <svg className="w-5 h-5 text-dm-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
      </svg>
    ) : (
      <svg className="w-5 h-5 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    )}
  </div>
);

const CitationCard = ({ 
  title, 
  relevance, 
  text, 
  isDm,
  chunkId,
  onClick 
}: { 
  title: string; 
  relevance: number; 
  text: string;
  isDm: boolean;
  chunkId?: string;
  onClick: () => void;
}) => {
  const percentage = Math.round(relevance * 100);
  
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-lg p-3 transition-all duration-200 hover:scale-[1.01] ${
        isDm 
          ? 'bg-dm-900/40 hover:bg-dm-900/60 border-l-4 border-dm-400' 
          : 'bg-amber-50/80 hover:bg-amber-100/80 border-l-4 border-amber-400'
      }`}
    >
      <div className="flex justify-between items-start mb-1.5">
        <span className={`font-semibold text-sm ${isDm ? 'text-dm-200' : 'text-amber-800'}`}>
          {title}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          percentage >= 90 
            ? (isDm ? 'bg-green-900/50 text-green-300' : 'bg-green-100 text-green-700')
            : percentage >= 70
              ? (isDm ? 'bg-yellow-900/50 text-yellow-300' : 'bg-yellow-100 text-yellow-700')
              : (isDm ? 'bg-dm-700 text-dm-300' : 'bg-gray-100 text-gray-600')
        }`}>
          {percentage}%
        </span>
      </div>
      <p className={`text-xs line-clamp-2 leading-relaxed ${isDm ? 'text-dm-300' : 'text-gray-600'}`}>
        {text}
      </p>
      {chunkId && (
        <div className={`mt-1 text-xs flex items-center gap-1 ${isDm ? 'text-dm-400' : 'text-amber-600'}`}>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          点击查看原文
        </div>
      )}
    </button>
  );
};

const CodeBlock = ({ language, code, isDm }: { language: string; code: string; isDm: boolean }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textArea = document.createElement('textarea');
      textArea.value = code;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [code]);

  return (
    <div className="relative group my-3">
      <div className={`flex justify-between items-center px-3 py-2 rounded-t-lg ${
        isDm ? 'bg-gray-800' : 'bg-gray-700'
      }`}>
        <span className="text-xs text-gray-400 font-mono">
          {language || 'text'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-1 text-xs text-gray-300 hover:text-white bg-gray-700 hover:bg-gray-600 rounded transition-colors"
        >
          {copied ? (
            <>
              <FiCheck className="w-3.5 h-3.5" />
              已复制
            </>
          ) : (
            <>
              <FiCopy className="w-3.5 h-3.5" />
              复制
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        style={atomDark}
        language={language || 'text'}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: '0 0 8px 8px',
          fontSize: '0.875rem',
          lineHeight: '1.5',
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
};

export default function MessageBubble({ message, onCitationClick, isDm = false, conversationId, isTyping = false }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const [feedbackStatus, setFeedbackStatus] = useState<'positive' | 'negative' | null>(null);
  const [showReasonDialog, setShowReasonDialog] = useState(false);
  const [selectedReason, setSelectedReason] = useState('');
  const [customReasonText, setCustomReasonText] = useState('');
  const [additionalNote, setAdditionalNote] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [copied, setCopied] = useState(false);
  const [selectedCitationChunkId, setSelectedCitationChunkId] = useState<string | null>(null);
  const feedbackApiRef = isDm ? dmFeedbackApi : feedbackApi;

  useEffect(() => {
    if (!isUser && message.id) {
      feedbackApiRef.getStatus(message.id).then((res) => {
        if (res.data && res.data.rating) {
          setFeedbackStatus(res.data.rating);
        }
      }).catch(() => {});
    }
  }, [message.id, isUser]);

  const handleCopyMessage = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textArea = document.createElement('textarea');
      textArea.value = message.content;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [message.content]);

  const handleFeedback = async (rating: 'positive' | 'negative') => {
    if (feedbackStatus || submittingFeedback || feedbackSubmitted) return;

    if (rating === 'negative') {
      setShowReasonDialog(true);
      return;
    }

    setSubmittingFeedback(true);
    try {
      await feedbackApiRef.submit({
        message_id: message.id,
        conversation_id: conversationId,
        rating,
      });
      setFeedbackStatus('positive');
      setFeedbackSubmitted(true);
    } catch {
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleSubmitNegativeFeedback = async () => {
    if (!selectedReason || submittingFeedback) return;
    setSubmittingFeedback(true);
    try {
      await feedbackApiRef.submit({
        message_id: message.id,
        conversation_id: conversationId,
        rating: 'negative',
        reason_category: selectedReason,
        custom_reason_text: selectedReason === 'other' ? customReasonText : undefined,
        reason: additionalNote.trim() || undefined,
      });
      setFeedbackStatus('negative');
      setFeedbackSubmitted(true);
      setShowReasonDialog(false);
      setSelectedReason('');
      setCustomReasonText('');
      setAdditionalNote('');
    } catch {
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleCancelReason = () => {
    setShowReasonDialog(false);
    setSelectedReason('');
    setCustomReasonText('');
    setAdditionalNote('');
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} items-end gap-2`}>
      {!isUser && <AssistantAvatar isDm={isDm} />}

      <div
        className={`max-w-[70%] rounded-2xl p-4 ${
          isUser
            ? isDm
              ? 'bg-gradient-to-br from-dm-500 to-dm-600 text-white message-bubble-user'
              : 'bg-primary-500 text-white'
            : isDm
              ? 'bg-gradient-to-br from-dm-50 to-white shadow-lg border-l-4 border-dm-400 message-bubble-assistant'
              : 'bg-white shadow-md border border-gray-100'
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <div className={`markdown-content ${isTyping ? 'typing typing-cursor' : ''} ${isDm ? 'dm-mode' : ''}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-2" {...props} />,
                ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-2" {...props} />,
                li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                a: ({ node, ...props }) => <a className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto mb-3">
                    <table className="min-w-full border-collapse border border-gray-300" {...props} />
                  </div>
                ),
                th: ({ node, ...props }) => (
                  <th className="border border-gray-300 px-3 py-2 bg-gray-100 font-semibold text-sm" {...props} />
                ),
                td: ({ node, ...props }) => (
                  <td className="border border-gray-300 px-3 py-2 text-sm" {...props} />
                ),
                blockquote: ({ node, ...props }) => (
                  <blockquote className="border-l-4 border-gray-300 pl-3 py-1 my-2 text-gray-600 italic" {...props} />
                ),
                code: ({ node, inline, className, children, ...props }: any) => {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeContent = String(children).replace(/\n$/, '');
                  
                  if (!inline && match) {
                    return (
                      <CodeBlock
                        language={match[1]}
                        code={codeContent}
                        isDm={isDm}
                      />
                    );
                  }
                  
                  return (
                    <code
                      className={`px-1.5 py-0.5 rounded text-sm font-mono ${
                        isDm
                          ? 'bg-dm-200 text-dm-900'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                      {...props}
                    >
                      {codeContent}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {!isUser && (
          <div className="flex justify-end mt-2">
            <button
              onClick={handleCopyMessage}
              className={`flex items-center gap-1 px-2 py-1 text-xs rounded transition-all ${
                isDm
                  ? 'text-dm-500 hover:text-dm-600 hover:bg-dm-100'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              }`}
              title="复制消息"
            >
              {copied ? (
                <>
                  <FiCheck className="w-3.5 h-3.5" />
                  已复制
                </>
              ) : (
                <>
                  <FiCopy className="w-3.5 h-3.5" />
                  复制
                </>
              )}
            </button>
          </div>
        )}

        {!isUser && message.citations && message.citations.length > 0 && (
          <div className={`mt-3 pt-3 ${isDm ? 'border-t border-dm-300/50' : 'border-t border-gray-200'}`}>
            <div className={`text-xs mb-2 flex items-center gap-1.5 ${isDm ? 'text-dm-400' : 'text-gray-500'}`}>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              参考来源：
            </div>
            <div className="space-y-2">
              {message.citations.map((citation: any, idx) => (
                <CitationCard
                  key={idx}
                  title={citation.title}
                  relevance={citation.relevance}
                  text={citation.text}
                  isDm={isDm}
                  chunkId={citation.chunk_id}
                  onClick={() => {
                    if (citation.chunk_id) {
                      setSelectedCitationChunkId(citation.chunk_id);
                    } else {
                      onCitationClick(citation.text);
                    }
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {selectedCitationChunkId && (
          <CitationDetailModal
            chunkId={selectedCitationChunkId}
            isDm={isDm}
            onClose={() => setSelectedCitationChunkId(null)}
          />
        )}

        {/* 检索溯源面板：展示 Top-3 检索片段及来源类型（BM25/向量/RRF） */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <RetrievalTracePanel sources={message.sources} isDark={isDm} />
        )}

        {!isUser && (
          <div className={`mt-3 pt-2 ${isDm ? 'border-t border-dm-300/50' : 'border-t border-gray-200'}`}>
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleFeedback('positive')}
                disabled={!!feedbackStatus || submittingFeedback || feedbackSubmitted}
                title={feedbackSubmitted ? '已评价' : '赞'}
                className={`text-sm px-1.5 py-0.5 rounded transition-colors ${
                  feedbackStatus === 'positive'
                    ? 'text-green-600 bg-green-50'
                    : `text-gray-400 hover:text-green-600 hover:bg-green-50 ${(feedbackStatus || feedbackSubmitted) ? 'cursor-not-allowed' : 'cursor-pointer'}`
                }`}
              >
                👍
              </button>
              <button
                onClick={() => handleFeedback('negative')}
                disabled={!!feedbackStatus || submittingFeedback || feedbackSubmitted}
                title={feedbackSubmitted ? '已评价' : '踩'}
                className={`text-sm px-1.5 py-0.5 rounded transition-colors ${
                  feedbackStatus === 'negative'
                    ? 'text-red-600 bg-red-50'
                    : `text-gray-400 hover:text-red-600 hover:bg-red-50 ${(feedbackStatus || feedbackSubmitted) ? 'cursor-not-allowed' : 'cursor-pointer'}`
                }`}
              >
                👎
              </button>
              {feedbackSubmitted && (
                <span className="ml-2 text-xs text-green-600">
                  已提交反馈 ✓
                </span>
              )}
            </div>

            {showReasonDialog && (
              <div className={`mt-3 p-3 rounded-lg border ${
                isDm
                  ? 'bg-dm-800/50 border-dm-500'
                  : 'bg-gray-50 border-gray-200'
              }`}>
                <div className={`text-xs mb-2 font-medium ${isDm ? 'text-dm-200' : 'text-gray-700'}`}>
                  请选择不满意的原因：
                </div>
                <div className="grid grid-cols-2 gap-1.5 mb-3">
                  {FEEDBACK_REASONS.map((reason) => (
                    <button
                      key={reason.value}
                      onClick={() => setSelectedReason(reason.value)}
                      className={`text-xs px-2.5 py-1.5 rounded border transition-all ${
                        selectedReason === reason.value
                          ? isDm
                            ? 'bg-dm-600 border-dm-400 text-white'
                            : 'bg-red-500 border-red-400 text-white'
                          : isDm
                            ? 'border-dm-500 text-dm-300 hover:bg-dm-700'
                            : 'border-gray-300 text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      {reason.label}
                    </button>
                  ))}
                </div>

                {selectedReason === 'other' && (
                  <input
                    type="text"
                    value={customReasonText}
                    onChange={(e) => setCustomReasonText(e.target.value)}
                    placeholder="请说明具体原因..."
                    className={`w-full text-xs px-2 py-1.5 rounded border mb-2 ${
                      isDm
                        ? 'bg-dm-700 border-dm-500 text-dm-100 placeholder-dm-400'
                        : 'bg-white border-gray-300 text-gray-700 placeholder-gray-400'
                    } focus:outline-none focus:ring-1 focus:ring-red-400`}
                  />
                )}

                <input
                  type="text"
                  value={additionalNote}
                  onChange={(e) => setAdditionalNote(e.target.value)}
                  placeholder="补充说明（可选）..."
                  className={`w-full text-xs px-2 py-1.5 rounded border mb-2 ${
                    isDm
                      ? 'bg-dm-700 border-dm-500 text-dm-100 placeholder-dm-400'
                      : 'bg-white border-gray-300 text-gray-700 placeholder-gray-400'
                  } focus:outline-none focus:ring-1 focus:ring-red-400`}
                />

                <div className="flex gap-1.5">
                  <button
                    onClick={handleSubmitNegativeFeedback}
                    disabled={!selectedReason || submittingFeedback || (selectedReason === 'other' && !customReasonText.trim())}
                    className="text-xs px-3 py-1.5 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submittingFeedback ? '提交中...' : '提交反馈'}
                  </button>
                  <button
                    onClick={handleCancelReason}
                    className={`text-xs px-3 py-1.5 rounded border ${
                      isDm
                        ? 'border-dm-500 text-dm-300 hover:bg-dm-600'
                        : 'border-gray-300 text-gray-500 hover:bg-gray-100'
                    }`}
                  >
                    取消
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {isUser && <UserAvatar isDm={isDm} />}
    </div>
  );
}
