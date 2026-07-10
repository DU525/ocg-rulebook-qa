import axios from 'axios';
import type { 
  ApiResponse, Message, Conversation, Document, Metrics, AskQuestionResponse, 
  Citation, Alert, AlertRule, TrendData, DocumentPreview, DocumentChunk, 
  QualityMetrics, RAGConfig, RAGConfigResponse, SearchQualityMetrics,
  CitationDetail, ConversationSearchResponse, ImportUrlResponse, 
  ImportStatus, ModelsResponse, QuestionSuggestion, SuggestionsResponse,
  CategorySuggestions
} from '../types';
import { getCurrentTraceId } from './trace';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  config.headers['X-Trace-ID'] = getCurrentTraceId();
  return config;
});

api.interceptors.response.use(
  (response) => {
    const traceId = response.headers['x-trace-id'];
    if (traceId) {
      console.log(`[Frontend Trace] ${traceId} -> ${response.config.method?.toUpperCase()} ${response.config.url} ${response.status}`);
    }
    return response;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export const chatApi = {
  askQuestion: async (
    question: string,
    conversationId?: string
  ): Promise<ApiResponse<AskQuestionResponse>> => {
    // TODO: 待后端在 /chat/question 响应中增加 sources 字段（检索来源类型 BM25/向量/RRF + 分数 + 片段），
    // 当前前端通过 simulateSourcesFromCitations 根据 citations 模拟生成 sources 数据
    const response = await api.post('/chat/question', { question, conversation_id: conversationId });
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

    const url = `${API_BASE_URL}/chat/question/stream`;

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Trace-ID': getCurrentTraceId(),
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
                // TODO: 待后端在流式响应中增加 parsed.sources（检索来源类型 BM25/向量/RRF + 分数 + 片段），
                // 届时应将 parsed.sources 一并传入 onComplete，前端移除模拟逻辑
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

export const conversationApi = {
  getList: async (): Promise<ApiResponse<Conversation[]>> => {
    const response = await api.get('/conversations');
    return response.data;
  },

  getDetail: async (id: string): Promise<ApiResponse<Message[]>> => {
    const response = await api.get(`/conversations/${id}`);
    return response.data;
  },

  delete: async (id: string): Promise<ApiResponse<void>> => {
    const response = await api.delete(`/conversations/${id}`);
    return response.data;
  },

  search: async (q: string, page: number = 1, limit: number = 20): Promise<ApiResponse<ConversationSearchResponse>> => {
    const response = await api.get('/conversations/search', { params: { q, page, limit } });
    return response.data;
  },
};

export const documentApi = {
  getList: async (status?: string): Promise<ApiResponse<Document[]>> => {
    const params = status && status !== 'all' ? { status } : {};
    const response = await api.get('/documents', { params });
    return response.data;
  },

  search: async (keyword: string): Promise<ApiResponse<Document[]>> => {
    const response = await api.get('/documents/search', { params: { keyword } });
    return response.data;
  },

  upload: async (file: File): Promise<ApiResponse<{ id: string; name: string; status: string }>> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  importUrl: async (url: string, title?: string, selectors?: string[], autoChunk: boolean = true): Promise<ApiResponse<ImportUrlResponse>> => {
    const response = await api.post('/documents/import-url', { url, title, selectors, auto_chunk: autoChunk });
    return response.data;
  },

  getImportStatus: async (docId: string): Promise<ApiResponse<ImportStatus>> => {
    const response = await api.get(`/documents/${docId}/import-status`);
    return response.data;
  },

  getProgress: async (docId: string): Promise<ApiResponse<{
    id: string;
    name: string;
    status: string;
    progress: number;
    uploaded_bytes: number;
    total_bytes: number;
    chunk_count: number;
    error_message?: string;
  }>> => {
    const response = await api.get(`/documents/${docId}/progress`);
    return response.data;
  },

  getPreview: async (id: string): Promise<ApiResponse<DocumentPreview>> => {
    const response = await api.get(`/documents/${id}/preview`);
    return response.data;
  },

  getChunks: async (id: string): Promise<ApiResponse<DocumentChunk[]>> => {
    const response = await api.get(`/documents/${id}/chunks`);
    return response.data;
  },

  delete: async (id: string): Promise<ApiResponse<void>> => {
    const response = await api.delete(`/documents/${id}`);
    return response.data;
  },
};

export const citationApi = {
  getDetail: async (chunkId: string): Promise<ApiResponse<CitationDetail>> => {
    const response = await api.get(`/citations/${chunkId}/detail`);
    return response.data;
  },
};

export const modelApi = {
  getAvailableModels: async (): Promise<ApiResponse<ModelsResponse>> => {
    const response = await api.get('/config/models');
    return response.data;
  },

  switchModel: async (modelId: string): Promise<ApiResponse<{ message: string; current_model: string }>> => {
    const response = await api.put('/config/models', { model_id: modelId });
    return response.data;
  },
};

export const metricsApi = {
  get: async (): Promise<ApiResponse<Metrics>> => {
    const response = await api.get('/metrics');
    return response.data;
  },

  getTrend: async (days: number = 7): Promise<ApiResponse<{ days: number; data: TrendData[] }>> => {
    const response = await api.get(`/metrics/trend?days=${days}`);
    return response.data;
  },
};

export const alertApi = {
  getHistory: async (): Promise<ApiResponse<Alert[]>> => {
    const response = await api.get('/metrics/alerts/history');
    return response.data;
  },

  getUnread: async (): Promise<ApiResponse<Alert[]>> => {
    const response = await api.get('/metrics/alerts/unread');
    return response.data;
  },

  getRules: async (): Promise<ApiResponse<AlertRule[]>> => {
    const response = await api.get('/metrics/alerts');
    return response.data;
  },

  updateRule: async (rule: Partial<AlertRule> & { ruleType: string }): Promise<ApiResponse<void>> => {
    const response = await api.post('/metrics/alerts', {
      rule_type: rule.ruleType,
      threshold: rule.threshold,
      enabled: rule.enabled,
      description: rule.description
    });
    return response.data;
  },

  markRead: async (alertId: string): Promise<ApiResponse<void>> => {
    const response = await api.put(`/metrics/alerts/${alertId}/read`);
    return response.data;
  },
};

export const healthApi = {
  check: async (): Promise<ApiResponse<{ status: string; vector_store_count: number }>> => {
    const response = await api.get('/health');
    return response.data;
  },
};

export const feedbackApi = {
  submit: async (data: { message_id: string; conversation_id?: string; rating: string; reason?: string; reason_category?: string; custom_reason_text?: string }) => {
    const response = await api.post('/feedback', data);
    return response.data;
  },
  getStatus: async (messageId: string) => {
    const response = await api.get(`/feedback/${messageId}`);
    return response.data;
  },
  getStats: async () => {
    const response = await api.get('/feedback/stats');
    return response.data;
  },
  getNegativeSamples: async (page = 1, limit = 20, reason = '') => {
    const response = await api.get('/feedback/negative-samples', { params: { page, limit, reason } });
    return response.data;
  },
  getQuality: async (): Promise<ApiResponse<QualityMetrics>> => {
    const response = await api.get('/metrics/quality');
    return response.data;
  },
};

export const configApi = {
  getRAG: async (): Promise<ApiResponse<RAGConfigResponse>> => {
    const response = await api.get('/config/rag');
    return response.data;
  },
  updateRAG: async (config: Partial<RAGConfig>): Promise<ApiResponse<{ config: RAGConfig }>> => {
    const response = await api.put('/config/rag', config);
    return response.data;
  },
};

export const searchQualityApi = {
  get: async (days: number = 7): Promise<ApiResponse<SearchQualityMetrics>> => {
    const response = await api.get(`/metrics/search-quality?days=${days}`);
    return response.data;
  },
};

export const suggestionApi = {
  getHotSuggestions: async (
    category?: string,
    limit: number = 10,
    gameType?: string
  ): Promise<ApiResponse<SuggestionsResponse>> => {
    const params: Record<string, any> = { limit };
    if (category) params.category = category;
    if (gameType) params.game_type = gameType;
    const response = await api.get('/suggestions', { params });
    return response.data;
  },

  getCategorySuggestions: async (
    limit: number = 5,
    gameType?: string
  ): Promise<ApiResponse<{ categories: CategorySuggestions; game_type: string }>> => {
    const params: Record<string, any> = { limit };
    if (gameType) params.game_type = gameType;
    const response = await api.get('/suggestions/categories', { params });
    return response.data;
  },

  getPersonalizedSuggestions: async (
    conversationId: string,
    limit: number = 5,
    gameType?: string
  ): Promise<ApiResponse<SuggestionsResponse>> => {
    const params: Record<string, any> = { conversation_id: conversationId, limit };
    if (gameType) params.game_type = gameType;
    const response = await api.get('/suggestions/personalized', { params });
    return response.data;
  },
};
