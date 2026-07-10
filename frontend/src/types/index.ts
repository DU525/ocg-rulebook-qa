export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  // 检索溯源：展示 Top-N 检索片段及其来源类型（BM25/向量/RRF）
  // TODO: 当前为前端模拟数据，待后端在 /chat/question/stream 响应中返回 sources 字段后对接
  sources?: RetrievalSource[];
  createdAt: string;
}

/**
 * 检索溯源来源片段
 * 用于在 AI 回复下方展示检索过程的透明度
 */
export interface RetrievalSource {
  /** 来源类型：BM25 关键词检索 / 向量语义检索 / RRF 融合排序 */
  sourceType: 'BM25' | 'vector' | 'RRF';
  /** 相关度分数 0-1 */
  score: number;
  /** 检索片段文本摘要 */
  text: string;
  /** 来源标题（可选） */
  title?: string;
}

export interface Citation {
  source: string;
  title: string;
  text: string;
  relevance: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export interface Document {
  id: string;
  name: string;
  source: 'builtin' | 'uploaded';
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'uploading';
  chunkCount: number;
  fileSize?: number;
  uploadTime?: string;
  // 上传进度相关字段
  uploadProgress?: number;      // 0-100 百分比
  uploadedBytes?: number;       // 已上传字节数
  totalBytes?: number;          // 总字节数
  errorMessage?: string;        // 错误信息
  createdAt: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
}

export interface Metrics {
  totalConversations: number;
  totalMessages: number;
  knowledgeBaseSize: number;
  unreadAlerts?: number;
  avgResponseTimeMs?: number;
  messagesToday?: number;
  conversationsThisWeek?: number;
  topKeywords?: Array<{ keyword: string; count: number }>;
}

export interface TrendData {
  date: string;
  messages: number;
  conversations: number;
}

export interface Alert {
  id: string;
  ruleType: string;
  message: string;
  isRead: number;
  createdAt: string;
}

export interface AlertRule {
  id: string;
  ruleType: string;
  threshold: number;
  enabled: number;
  description: string;
}

export interface AskQuestionResponse {
  answer: string;
  citations: Citation[];
  // TODO: 待后端在问答响应中返回检索溯源数据（来源类型 + 分数 + 片段），当前前端模拟
  sources?: RetrievalSource[];
  conversation_id: string;
  confidence: number;
  response_time_ms: number;
}

export interface DocumentPreview {
  id: string;
  name: string;
  source: 'builtin' | 'uploaded';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  file_size: number;
  preview_text: string;
  created_at: string;
}

export interface DocumentChunk {
  id: string;
  text: string;
  chunk_index: number;
}

export interface FeedbackData {
  id?: string;
  messageId: string;
  conversationId?: string;
  rating: 'positive' | 'negative';
  reason?: string;
  createdAt?: string;
}

export interface QualityMetrics {
  totalFeedbacks: number;
  positiveCount: number;
  negativeCount: number;
  positiveRate: number;
  dailyTrend: Array<{date: string; positive: number; negative: number}>;
  topNegativeReasons: Array<{reason: string; count: number}>;
}

export interface RAGConfig {
  top_k: number;
  temperature: number;
  max_tokens: number;
  system_prompt_template: string;
  streaming_enabled: boolean;
  similarity_threshold: number;
}

export interface RAGTemplate {
  id: string;
  name: string;
}

export interface RAGConfigResponse {
  config: RAGConfig;
  available_templates: RAGTemplate[];
}

export interface SearchQualityMetrics {
  days: number;
  positive_rate: number;
  total_feedbacks: number;
  positive_count: number;
  negative_count: number;
  daily_quality: Array<{date: string; positive: number; negative: number; rate: number | null}>;
  top_negative_reasons: Array<{reason: string; count: number}>;
  avg_response_time_ms: number;
  response_distribution: {
    fast: number;
    medium: number;
    slow: number;
  };
}

export interface CitationDetail {
  chunk_id: string;
  text: string;
  metadata: Record<string, any>;
  source: string;
  chapter: string;
  section: string;
}

export interface ConversationSearchResult {
  conversation_id: string;
  conversation_title: string;
  message_id: string;
  role: 'user' | 'assistant';
  matched_context: string;
  created_at: string;
}

export interface ConversationSearchResponse {
  results: ConversationSearchResult[];
  total: number;
  page: number;
  limit: number;
}

export interface ImportUrlResponse {
  id: string;
  url: string;
  status: 'processing' | 'completed' | 'failed';
  message: string;
}

export interface ImportStatus {
  id: string;
  name: string;
  status: string;
  progress: number;
  chunk_count: number;
  error_message?: string;
  source_url?: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  model_name: string;
  enabled: boolean;
  provider: string;
}

export interface ModelsResponse {
  current_model: string;
  available_models: ModelInfo[];
}

export interface EnhancedCitation extends Citation {
  chunk_id?: string;
  document_id?: string;
  page_number?: number;
  section_path?: string;
}

export interface QuestionSuggestion {
  question: string;
  category: string;
  frequency: number;
  relevance_score: number;
  time_decay?: number;
  is_default?: boolean;
}

export interface SuggestionsResponse {
  suggestions: QuestionSuggestion[];
  total: number;
  category?: string;
  game_type?: string;
  conversation_id?: string;
}

export interface CategorySuggestions {
  [category: string]: QuestionSuggestion[];
}