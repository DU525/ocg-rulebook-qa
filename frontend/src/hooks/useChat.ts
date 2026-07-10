import { useCallback, useState, useRef, useEffect } from 'react';
import { useAppStore } from '../stores/appStore';
import { chatApi } from '../services/api';
import { simulateSourcesFromCitations } from '../utils/retrievalSources';
import type { Message, Conversation, Citation } from '../types';

const TICK_MS = 24;
const CHARS_PER_TICK = 2;

class TypewriterBuffer {
  private buffer = '';
  private emitted = '';
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private onUpdate: (fullContent: string) => void;
  private onComplete: () => void;
  private flushed = false;

  constructor(onUpdate: (fullContent: string) => void, onComplete: () => void) {
    this.onUpdate = onUpdate;
    this.onComplete = onComplete;
    this.start();
  }

  addChunk(chunk: string) {
    if (this.flushed) return;
    this.buffer += chunk;
  }

  private start() {
    this.intervalId = setInterval(() => {
      if (this.buffer.length > 0) {
        const charsToEmit = this.buffer.slice(0, CHARS_PER_TICK);
        this.emitted += charsToEmit;
        this.buffer = this.buffer.slice(CHARS_PER_TICK);
        this.onUpdate(this.emitted);
      } else if (this.flushed && this.buffer.length === 0) {
        this.stop();
        this.onComplete();
      }
    }, TICK_MS);
  }

  flush() {
    if (this.flushed) return;
    this.flushed = true;
    
    if (this.buffer.length > 0) {
      this.emitted += this.buffer;
      this.buffer = '';
      this.onUpdate(this.emitted);
    }
    
    this.stop();
    this.onComplete();
  }

  private stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  getEmittedLength(): number {
    return this.emitted.length;
  }
}

export function useChat() {
  const {
    messages,
    addMessage,
    setAssistantMessageContent,
    updateLastAssistantCitations,
    addConversation,
    setIsLoading,
    currentConversation,
    setCurrentConversation
  } = useAppStore();

  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const cancelStreamRef = useRef<(() => void) | null>(null);
  const typewriterRef = useRef<TypewriterBuffer | null>(null);
  const assistantMessageIdRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (typewriterRef.current) {
        typewriterRef.current.flush();
      }
    };
  }, []);

  const sendMessage = useCallback(async (question: string) => {
    setIsLoading(true);
    setError(null);

    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }

    if (typewriterRef.current) {
      typewriterRef.current.flush();
      typewriterRef.current = null;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
      createdAt: new Date().toISOString(),
    };
    addMessage(userMessage);

    const assistantId = (Date.now() + 1).toString();
    assistantMessageIdRef.current = assistantId;
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      citations: [],
      createdAt: new Date().toISOString(),
    };
    addMessage(assistantMessage);

    const typewriter = new TypewriterBuffer(
      (fullContent: string) => {
        if (assistantMessageIdRef.current) {
          setAssistantMessageContent(assistantMessageIdRef.current, fullContent);
        }
      },
      () => {
        assistantMessageIdRef.current = null;
      }
    );
    typewriterRef.current = typewriter;

    try {
      const cancel = chatApi.askQuestionStream(
        question,
        currentConversation?.id,
        (chunk: string) => {
          typewriter.addChunk(chunk);
        },
        (citations: Citation[], _confidence: number, conversationId: string) => {
          if (typewriterRef.current) {
            typewriterRef.current.flush();
            typewriterRef.current = null;
          }
          // TODO: 后端流式响应暂未返回检索来源类型（BM25/向量/RRF），
          // 此处根据 citations 模拟生成 sources 数据，待后端支持后改用真实数据
          const simulatedSources = simulateSourcesFromCitations(citations);
          updateLastAssistantCitations(citations, simulatedSources);

          if (!currentConversation) {
            const newConversation: Conversation = {
              id: conversationId,
              title: question.slice(0, 50),
              messages: messagesRef.current,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            };
            addConversation(newConversation);
            setCurrentConversation(newConversation);
          } else {
            setCurrentConversation({
              ...currentConversation,
              messages: [...currentConversation.messages, userMessage, { ...assistantMessage, citations, sources: simulatedSources }].slice(-20),
            });
          }

          setIsLoading(false);
        },
        (err: string) => {
          if (typewriterRef.current) {
            typewriterRef.current.flush();
            typewriterRef.current = null;
          }
          setError(err);
          if (assistantMessageIdRef.current) {
            setAssistantMessageContent(assistantMessageIdRef.current, `\n\n[错误: ${err}]`);
          }
          setIsLoading(false);
        }
      );

      cancelStreamRef.current = cancel;
    } catch (err: any) {
      if (typewriterRef.current) {
        typewriterRef.current.flush();
        typewriterRef.current = null;
      }
      console.error('发送消息失败:', err);
      setError(err.message || '网络连接失败');
      if (assistantMessageIdRef.current) {
        setAssistantMessageContent(assistantMessageIdRef.current, '\n\n[抱歉，网络连接出现问题，请稍后重试。]');
      }
      setIsLoading(false);
    }
  }, [currentConversation, addMessage, setAssistantMessageContent, updateLastAssistantCitations, addConversation, setIsLoading, setCurrentConversation]);

  const cancelStream = useCallback(() => {
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    if (typewriterRef.current) {
      typewriterRef.current.flush();
      typewriterRef.current = null;
    }
    setIsLoading(false);
  }, [setIsLoading]);

  return { messages, sendMessage, error, cancelStream };
}
