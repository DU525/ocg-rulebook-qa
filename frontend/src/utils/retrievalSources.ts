import type { Citation, RetrievalSource } from '../types';

/**
 * 模拟检索溯源数据
 *
 * TODO: 当前后端 /chat/question/stream 响应仅返回 citations（source/title/text/relevance），
 * 未返回检索来源类型（BM25/向量/RRF）。此函数根据 citations 模拟生成 sources 数据，
 * 轮流分配 BM25 / 向量 / RRF 标签。待后端在流式响应中增加 sources 字段后，
 * 应直接使用后端返回的真实数据，移除此模拟逻辑。
 *
 * @param citations 后端返回的引用列表
 * @returns 模拟的检索溯源来源片段（Top-3）
 */
export function simulateSourcesFromCitations(
  citations: Citation[]
): RetrievalSource[] {
  const sourceTypes: RetrievalSource['sourceType'][] = ['BM25', 'vector', 'RRF'];

  return citations.slice(0, 3).map((citation, index) => ({
    sourceType: sourceTypes[index % sourceTypes.length],
    score: citation.relevance,
    text: citation.text,
    title: citation.title,
  }));
}
