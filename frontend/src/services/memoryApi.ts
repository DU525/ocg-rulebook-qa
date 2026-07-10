import axios from 'axios';
import { getCurrentTraceId } from './trace';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  config.headers['X-Trace-ID'] = getCurrentTraceId();
  return config;
});

/* =========================================================================
 * 对话记忆类型定义
 * ========================================================================= */

/** 记忆类型 */
export type MemoryType = 'short_term' | 'long_term' | 'working' | 'episodic' | 'factual' | 'semantic';

/** 单条记忆条目 */
export interface MemoryItem {
  /** 记忆唯一标识 */
  id: string;
  /** 记忆内容摘要 */
  content: string;
  /** 记忆类型 */
  type: MemoryType;
  /** 相关度/检索分数 0-1（检索时返回） */
  score?: number;
  /** 重要性 0-1 */
  importance?: number;
  /** 标签 */
  tags?: string[];
  /** 创建时间 ISO 字符串 */
  createdAt: string;
}

/** 记忆统计信息 */
export interface MemoryStats {
  shortTermCount: number;
  longTermCount: number;
  workingCount: number;
}

/** 完整记忆状态：短期 + 长期 */
export interface MemoryState {
  shortTerm: MemoryItem[];
  longTerm: MemoryItem[];
  stats: MemoryStats | null;
}

/** 添加记忆请求 */
export interface MemoryAddRequest {
  content: string;
  memory_type?: MemoryType;
  importance?: number;
  tags?: string[];
  user_id?: string;
}

/* =========================================================================
 * 对话记忆 API
 *
 * 说明：后端 advancedApi 中已有 /advanced/memory/* 系列端点（add/retrieve/stats），
 * 但缺少"列出短期/长期记忆"的专用接口。本服务封装现有端点并定义完整接口结构，
 * 标注 TODO 的方法需要后端新增对应接口后对接。
 * ========================================================================= */

export const memoryApi = {
  /**
   * 获取短期记忆（当前对话中系统保留的关键信息，最近 N 条摘要）
   *
   * TODO: 后端暂无"列出短期记忆"的专用接口。
   * 当前实现通过 /advanced/memory/retrieve 传入空查询获取最近记忆作为占位，
   * 待后端新增 GET /advanced/memory/short-term 接口后替换为真实数据。
   */
  getShortTerm: async (limit: number = 5): Promise<MemoryItem[]> => {
    try {
      const response = await api.get('/advanced/memory/retrieve', {
        params: { query: '', limit },
      });
      const data = response.data;
      const memories = data.memories || data.data?.memories || [];
      return memories.slice(0, limit).map((m: any): MemoryItem => ({
        id: m.memory_id || m.id || String(Math.random()),
        content: m.content || '',
        type: 'short_term',
        score: m.score,
        importance: m.importance,
        createdAt: m.created_at || m.createdAt || new Date().toISOString(),
      }));
    } catch {
      return [];
    }
  },

  /**
   * 获取长期记忆（系统持久化的事实记忆，列表形式）
   *
   * TODO: 后端暂无"列长期记忆"的专用接口。
   * 当前实现通过 /advanced/memory/retrieve 获取并过滤 factual/semantic 类型记忆，
   * 待后端新增 GET /advanced/memory/long-term 接口后替换为真实数据。
   */
  getLongTerm: async (limit: number = 20): Promise<MemoryItem[]> => {
    try {
      const response = await api.get('/advanced/memory/retrieve', {
        params: { query: '', limit: limit * 2 },
      });
      const data = response.data;
      const memories = data.memories || data.data?.memories || [];
      return memories
        .filter((m: any) => ['factual', 'semantic', 'long_term', 'episodic'].includes(m.type))
        .slice(0, limit)
        .map((m: any): MemoryItem => ({
          id: m.memory_id || m.id || String(Math.random()),
          content: m.content || '',
          type: 'long_term',
          score: m.score,
          importance: m.importance,
          createdAt: m.created_at || m.createdAt || new Date().toISOString(),
        }));
    } catch {
      return [];
    }
  },

  /**
   * 获取记忆统计信息
   * 对接后端 GET /advanced/memory/stats
   */
  getStats: async (): Promise<MemoryStats | null> => {
    try {
      const response = await api.get('/advanced/memory/stats');
      const data = response.data;
      const stats = data.stats || data.data || data;
      return {
        shortTermCount: stats.short_term_count ?? stats.shortTermCount ?? 0,
        longTermCount: stats.long_term_count ?? stats.longTermCount ?? 0,
        workingCount: stats.working_count ?? stats.workingCount ?? 0,
      };
    } catch {
      return null;
    }
  },

  /**
   * 获取完整记忆状态（短期 + 长期 + 统计），并发请求提升性能
   */
  getAll: async (shortTermLimit: number = 5, longTermLimit: number = 20): Promise<MemoryState> => {
    const [shortTerm, longTerm, stats] = await Promise.all([
      memoryApi.getShortTerm(shortTermLimit),
      memoryApi.getLongTerm(longTermLimit),
      memoryApi.getStats(),
    ]);
    return { shortTerm, longTerm, stats };
  },

  /**
   * 添加记忆
   * 对接后端 POST /advanced/memory/add
   */
  add: async (request: MemoryAddRequest): Promise<any> => {
    const response = await api.post('/advanced/memory/add', request);
    return response.data;
  },

  /**
   * 检索相关记忆
   * 对接后端 GET /advanced/memory/retrieve
   */
  retrieve: async (query: string, limit: number = 5): Promise<MemoryItem[]> => {
    const response = await api.get('/advanced/memory/retrieve', {
      params: { query, limit },
    });
    const data = response.data;
    const memories = data.memories || data.data?.memories || [];
    return memories.map((m: any): MemoryItem => ({
      id: m.memory_id || m.id || String(Math.random()),
      content: m.content || '',
      type: m.type || 'short_term',
      score: m.score,
      importance: m.importance,
      createdAt: m.created_at || m.createdAt || new Date().toISOString(),
    }));
  },
};

export default memoryApi;
