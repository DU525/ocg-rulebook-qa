import axios from 'axios';
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

export interface UnifiedQueryRequest {
  query: string;
  user_id?: string;
  enable_memory?: boolean;
  enable_hierarchical?: boolean;
}

export interface UnifiedQueryResponse {
  query: string;
  route: {
    selected: string;
    strategy: string;
    confidence: number;
  } | null;
  memory_context: Array<{
    content: string;
    score: number;
    type: string;
  }>;
  retrieved_docs: Array<{
    content: string;
    score: number;
    metadata: Record<string, any>;
  }>;
  answer: string | null;
  metadata: {
    response_time_ms: number;
    memory_enabled: boolean;
    hierarchical_enabled: boolean;
  };
}

export interface MemoryAddRequest {
  content: string;
  memory_type?: 'episodic' | 'factual' | 'semantic' | 'working';
  importance?: number;
  tags?: string[];
  user_id?: string;
}

export interface MemoryRetrieveResponse {
  memories: Array<{
    memory_id: string;
    content: string;
    score: number;
    type: string;
    importance: number;
  }>;
  count: number;
}

export interface MemoryStats {
  short_term_count: number;
  long_term_count: number;
  working_count: number;
}

export interface RouteResult {
  selected_route: string;
  strategy: string;
  confidence: number;
  all_scores: Record<string, number>;
}

export interface RouteInfo {
  name: string;
  description: string;
  keywords: string[];
}

export interface RAGSearchResult {
  chunk_id: string;
  content: string;
  score: number;
  metadata: Record<string, any>;
  parent_id: string | null;
}

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, any>;
}

export interface ChunkingStrategy {
  current_strategy: string;
  available_strategies: string[];
}

export interface SystemStatus {
  initialized: boolean;
  services: Record<string, {
    available: boolean;
    status: string;
    stats?: any;
  }>;
}

export const advancedApi = {
  healthCheck: async (): Promise<any> => {
    const response = await api.get('/advanced/health');
    return response.data;
  },

  unifiedQuery: async (request: UnifiedQueryRequest): Promise<any> => {
    const response = await api.post('/advanced/query/unified', request);
    return response.data;
  },

  memory: {
    add: async (request: MemoryAddRequest): Promise<any> => {
      const response = await api.post('/advanced/memory/add', request);
      return response.data;
    },

    retrieve: async (query: string, limit: number = 5): Promise<any> => {
      const response = await api.get('/advanced/memory/retrieve', {
        params: { query, limit }
      });
      return response.data;
    },

    stats: async (): Promise<any> => {
      const response = await api.get('/advanced/memory/stats');
      return response.data;
    },
  },

  routing: {
    route: async (query: string): Promise<any> => {
      const response = await api.post('/advanced/routing/route', { query });
      return response.data;
    },

    listRoutes: async (): Promise<any> => {
      const response = await api.get('/advanced/routing/routes');
      return response.data;
    },

    addRoute: async (route: {
      name: string;
      description?: string;
      examples?: string[];
      keywords?: string[];
    }): Promise<any> => {
      const response = await api.post('/advanced/routing/routes', route);
      return response.data;
    },
  },

  rag: {
    search: async (
      query: string,
      top_k: number = 5,
      parent_top_k: number = 10
    ): Promise<any> => {
      const response = await api.get('/advanced/rag/search', {
        params: { query, top_k, parent_top_k }
      });
      return response.data;
    },

    stats: async (): Promise<any> => {
      const response = await api.get('/advanced/rag/stats');
      return response.data;
    },
  },

  tools: {
    list: async (): Promise<any> => {
      const response = await api.get('/advanced/tools/list');
      return response.data;
    },

    execute: async (
      tool_name: string,
      parameters: Record<string, any> = {}
    ): Promise<any> => {
      const response = await api.post('/advanced/tools/execute', {
        tool_name,
        parameters
      });
      return response.data;
    },
  },

  chunking: {
    getStrategy: async (): Promise<any> => {
      const response = await api.get('/advanced/chunking/strategy');
      return response.data;
    },

    chunk: async (request: {
      text: string;
      strategy?: string;
      max_chunk_size?: number;
    }): Promise<any> => {
      const response = await api.post('/advanced/chunking/chunk', request);
      return response.data;
    },
  },

  status: async (): Promise<any> => {
    const response = await api.get('/advanced/status');
    return response.data;
  },
};

export default advancedApi;
