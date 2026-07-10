import axios from 'axios';
import type { ApiResponse, Message, Conversation, Document, Metrics, AskQuestionResponse, Citation, QualityMetrics, RAGConfig, RAGConfigResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

export const dmChatApi = {
  askQuestion: async (
    question: string,
    conversationId?: string
  ): Promise<ApiResponse<AskQuestionResponse>> => {
    const response = await api.post('/dm/chat/question', { question, conversation_id: conversationId });
    return response.data;
  },

  askQuestionStream: (
    question: string,
    conversationId: string | undefined,
    onChunk: (chunk: string) => void,
    onComplete: (citations: Citation[], confidence: number, conversationId: string) => void,
    onError: (error: string) => void,
    signal?: AbortSignal
  ): () => void => {
    const controller = new AbortController();
    const combinedSignal = signal || controller.signal;

    const url = `${API_BASE_URL}/dm/chat/question/stream`;

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question, conversation_id: conversationId }),
      signal: combinedSignal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('ReadableStream not supported');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;

            const data = trimmed.slice(6);
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                onChunk(parsed.content);
              } else if (parsed.citations) {
                onComplete(parsed.citations, parsed.confidence || 0, conversationId || '');
              } else if (parsed.error) {
                onError(parsed.error);
              }
            } catch {
              // skip unparseable lines
            }
          }
        }
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        onError(err.message || 'Stream connection failed');
      });

    return () => controller.abort();
  },
};

export const dmConversationApi = {
  getList: async (): Promise<ApiResponse<Conversation[]>> => {
    const response = await api.get('/dm/conversations');
    return response.data;
  },

  getDetail: async (id: string): Promise<ApiResponse<Message[]>> => {
    const response = await api.get(`/dm/conversations/${id}`);
    return response.data;
  },

  delete: async (id: string): Promise<ApiResponse<void>> => {
    const response = await api.delete(`/dm/conversations/${id}`);
    return response.data;
  },
};

export const dmDocumentApi = {
  getList: async (status?: string): Promise<ApiResponse<Document[]>> => {
    const params = status && status !== 'all' ? { status } : {};
    const response = await api.get('/dm/documents', { params });
    return response.data;
  },

  upload: async (file: File): Promise<ApiResponse<{ id: string; name: string }>> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/dm/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  getProgress: async (docId: string): Promise<ApiResponse<any>> => {
    const response = await api.get(`/dm/documents/${docId}/progress`);
    return response.data;
  },

  getPreview: async (id: string): Promise<ApiResponse<any>> => {
    const response = await api.get(`/dm/documents/${id}/preview`);
    return response.data;
  },

  getChunks: async (id: string): Promise<ApiResponse<any[]>> => {
    const response = await api.get(`/dm/documents/${id}/chunks`);
    return response.data;
  },

  delete: async (id: string): Promise<ApiResponse<void>> => {
    const response = await api.delete(`/dm/documents/${id}`);
    return response.data;
  },
};

export const dmMetricsApi = {
  get: async (): Promise<ApiResponse<Metrics>> => {
    const response = await api.get('/dm/metrics');
    return response.data;
  },
};

export const dmHealthApi = {
  check: async (): Promise<ApiResponse<{ status: string; vector_store_count: number }>> => {
    const response = await api.get('/dm/health');
    return response.data;
  },
};

export const dmFeedbackApi = {
  submit: async (data: { message_id: string; conversation_id?: string; rating: string; reason?: string; reason_category?: string; custom_reason_text?: string }) => {
    const response = await api.post('/dm/feedback', data);
    return response.data;
  },
  getStatus: async (messageId: string) => {
    const response = await api.get(`/dm/feedback/${messageId}`);
    return response.data;
  },
  getStats: async () => {
    const response = await api.get('/dm/feedback/stats');
    return response.data;
  },
  getNegativeSamples: async (page = 1, limit = 20, reason = '') => {
    const response = await api.get('/dm/feedback/negative-samples', { params: { page, limit, reason } });
    return response.data;
  },
  getQuality: async (): Promise<ApiResponse<QualityMetrics>> => {
    const response = await api.get('/dm/metrics/quality');
    return response.data;
  },
};

export const dmConfigApi = {
  getRAG: async (): Promise<ApiResponse<RAGConfigResponse>> => {
    const response = await api.get('/dm/config/rag');
    return response.data;
  },
  updateRAG: async (config: Partial<RAGConfig>): Promise<ApiResponse<{ config: RAGConfig }>> => {
    const response = await api.put('/dm/config/rag', config);
    return response.data;
  },
};