import re
import math
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class ChunkingStrategy(Enum):
    """分块策略类型"""
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"
    ADAPTIVE = "adaptive"


@dataclass
class ChunkQualityMetrics:
    """分块质量评估指标"""
    completeness: float = 0.0  # 完整性评分 (0-1)
    coherence: float = 0.0  # 连贯性评分 (0-1)
    readability: float = 0.0  # 可读性评分 (0-1)
    coverage: float = 0.0  # 内容覆盖率评分 (0-1)
    overall_score: float = 0.0  # 综合评分


@dataclass
class ChunkResult:
    """分块结果"""
    content: str
    start_index: int
    end_index: int
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Optional[ChunkQualityMetrics] = None


class ChunkingStrategyBase:
    """分块策略基类"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk(self, text: str) -> List[ChunkResult]:
        """执行分块操作，子类必须实现"""
        raise NotImplementedError
    
    def _calculate_quality(self, chunk: str, text: str, start_idx: int, end_idx: int) -> ChunkQualityMetrics:
        """计算分块质量指标"""
        metrics = ChunkQualityMetrics()
        
        # 完整性：基于句子完整性
        sentences = re.split(r'[。！？；.!?;]', chunk)
        complete_sentences = [s for s in sentences if s.strip()]
        metrics.completeness = len(complete_sentences) / max(1, len(sentences))
        
        # 连贯性：基于标点符号分布
        punct_count = len(re.findall(r'[，,。.！!？?；;]', chunk))
        metrics.coherence = min(1.0, punct_count / max(1, len(chunk) / 30))
        
        # 可读性：基于平均句子长度
        avg_sentence_len = len(chunk) / max(1, len(complete_sentences))
        metrics.readability = max(0.0, 1.0 - abs(avg_sentence_len - 80) / 160)
        
        # 覆盖率：基于分块占总文本的比例
        metrics.coverage = (end_idx - start_idx) / max(1, len(text))
        
        # 综合评分
        metrics.overall_score = (
            metrics.completeness * 0.3 +
            metrics.coherence * 0.3 +
            metrics.readability * 0.2 +
            metrics.coverage * 0.2
        )
        
        return metrics


class SentenceChunkingStrategy(ChunkingStrategyBase):
    """基于句子的分块策略"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        super().__init__(chunk_size, chunk_overlap)
    
    def chunk(self, text: str) -> List[ChunkResult]:
        """基于句子边界分块"""
        if not text.strip():
            return []
        
        # 按句子分割，保留标点
        sentence_pattern = r'([^。！？；.!?;]+[。！？；.!?;]?)'
        sentences = re.findall(sentence_pattern, text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_idx = 0
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                chunks.append(ChunkResult(
                    content=current_chunk,
                    start_index=current_start,
                    end_index=current_start + len(current_chunk),
                    chunk_index=chunk_idx,
                    metadata={'strategy': 'sentence'},
                    quality_metrics=self._calculate_quality(current_chunk, text, current_start, current_start + len(current_chunk))
                ))
                chunk_idx += 1
                
                # 处理重叠
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:]
                current_start += overlap_start
            
            current_chunk += sentence if not current_chunk else (' ' + sentence)
        
        # 添加最后一个分块
        if current_chunk:
            chunks.append(ChunkResult(
                content=current_chunk,
                start_index=current_start,
                end_index=current_start + len(current_chunk),
                chunk_index=chunk_idx,
                metadata={'strategy': 'sentence'},
                quality_metrics=self._calculate_quality(current_chunk, text, current_start, current_start + len(current_chunk))
            ))
        
        return chunks


class ParagraphChunkingStrategy(ChunkingStrategyBase):
    """基于段落的分块策略"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        super().__init__(chunk_size, chunk_overlap)
    
    def chunk(self, text: str) -> List[ChunkResult]:
        """基于段落边界分块"""
        if not text.strip():
            return []
        
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_idx = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                chunks.append(ChunkResult(
                    content=current_chunk,
                    start_index=current_start,
                    end_index=current_start + len(current_chunk),
                    chunk_index=chunk_idx,
                    metadata={'strategy': 'paragraph'},
                    quality_metrics=self._calculate_quality(current_chunk, text, current_start, current_start + len(current_chunk))
                ))
                chunk_idx += 1
                
                # 处理重叠
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:]
                current_start += overlap_start
            
            current_chunk += '\n\n' + para if current_chunk else para
        
        # 添加最后一个分块
        if current_chunk:
            chunks.append(ChunkResult(
                content=current_chunk,
                start_index=current_start,
                end_index=current_start + len(current_chunk),
                chunk_index=chunk_idx,
                metadata={'strategy': 'paragraph'},
                quality_metrics=self._calculate_quality(current_chunk, text, current_start, current_start + len(current_chunk))
            ))
        
        return chunks


class SemanticBoundaryDetector:
    """语义边界检测器"""
    
    def __init__(self):
        # 常见的语义边界模式
        self.boundary_patterns = [
            r'^#{1,6}\s',  # Markdown 标题
            r'^\d+\.\s',  # 数字编号标题
            r'^[一二三四五六七八九十]+[、.]\s',  # 中文编号标题
            r'^[A-Z][A-Za-z\s]+?:',  # 英文标题带冒号
            r'---+',  # 分隔线
            r'==+',  # 分隔线
            r'^\*\*\*+\s*$',  # 星号分隔线
        ]
    
    def detect_boundaries(self, text: str) -> List[int]:
        """检测文本中的语义边界位置"""
        boundaries = [0]
        lines = text.split('\n')
        current_pos = 0
        
        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            
            for pattern in self.boundary_patterns:
                if re.match(pattern, line.strip()):
                    boundaries.append(current_pos)
                    break
            
            current_pos += line_length
        
        boundaries.append(len(text))
        return sorted(list(set(boundaries)))


class SemanticChunkingStrategy(ChunkingStrategyBase):
    """基于语义的分块策略"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        super().__init__(chunk_size, chunk_overlap)
        self.boundary_detector = SemanticBoundaryDetector()
    
    def chunk(self, text: str) -> List[ChunkResult]:
        """基于语义边界分块"""
        if not text.strip():
            return []
        
        # 检测语义边界
        boundaries = self.boundary_detector.detect_boundaries(text)
        
        chunks = []
        current_start = 0
        chunk_idx = 0
        
        for i in range(1, len(boundaries)):
            segment_start = boundaries[i-1]
            segment_end = boundaries[i]
            segment = text[segment_start:segment_end]
            
            # 如果当前累积内容超过目标大小，创建分块
            if segment_end - current_start > self.chunk_size and current_start < segment_start:
                chunk_content = text[current_start:segment_start]
                chunks.append(ChunkResult(
                    content=chunk_content,
                    start_index=current_start,
                    end_index=segment_start,
                    chunk_index=chunk_idx,
                    metadata={'strategy': 'semantic'},
                    quality_metrics=self._calculate_quality(chunk_content, text, current_start, segment_start)
                ))
                chunk_idx += 1
                
                # 处理重叠
                current_start = max(current_start, segment_start - self.chunk_overlap)
            
            # 如果单个段落超过目标大小，使用句子分块
            if len(segment) > self.chunk_size:
                sentence_chunker = SentenceChunkingStrategy(self.chunk_size, self.chunk_overlap)
                sub_chunks = sentence_chunker.chunk(segment)
                
                for sub_chunk in sub_chunks:
                    chunks.append(ChunkResult(
                        content=sub_chunk.content,
                        start_index=segment_start + sub_chunk.start_index,
                        end_index=segment_start + sub_chunk.end_index,
                        chunk_index=chunk_idx,
                        metadata={'strategy': 'semantic', 'sub_strategy': 'sentence'},
                        quality_metrics=sub_chunk.quality_metrics
                    ))
                    chunk_idx += 1
                
                current_start = segment_end
        
        # 添加剩余内容
        if current_start < len(text):
            chunk_content = text[current_start:]
            chunks.append(ChunkResult(
                content=chunk_content,
                start_index=current_start,
                end_index=len(text),
                chunk_index=chunk_idx,
                metadata={'strategy': 'semantic'},
                quality_metrics=self._calculate_quality(chunk_content, text, current_start, len(text))
            ))
        
        return chunks


class OverlapOptimizer:
    """智能重叠优化器"""
    
    def __init__(self, min_overlap: int = 32, max_overlap: int = 128):
        self.min_overlap = min_overlap
        self.max_overlap = max_overlap
    
    def calculate_optimal_overlap(
        self, 
        chunk1: str, 
        chunk2: str, 
        base_overlap: int
    ) -> int:
        """计算最优重叠大小"""
        # 分析两个分块的语义连贯性
        overlap = base_overlap
        
        # 检查前一分块的结尾是否有未完成的句子
        chunk1_end = chunk1[-200:] if len(chunk1) > 200 else chunk1
        has_unfinished_sentence = not re.search(r'[。！？；.!?;]', chunk1_end)
        
        if has_unfinished_sentence:
            # 如果句子未完成，增加重叠
            overlap = min(self.max_overlap, overlap + 32)
        
        # 检查是否有代码块、列表等需要保持完整的结构
        code_blocks = re.findall(r'```[\s\S]*?```', chunk1)
        if code_blocks:
            overlap = min(self.max_overlap, overlap + 16)
        
        return max(self.min_overlap, overlap)


class AdaptiveChunkingStrategy(ChunkingStrategyBase):
    """自适应分块策略"""
    
    def __init__(
        self, 
        min_chunk_size: int = 256, 
        max_chunk_size: int = 1024,
        target_chunk_size: int = 512
    ):
        super().__init__(target_chunk_size, 64)
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.target_chunk_size = target_chunk_size
        self.overlap_optimizer = OverlapOptimizer()
    
    def _analyze_text_complexity(self, text: str) -> float:
        """分析文本复杂度 (0-1)"""
        if not text:
            return 0.5
        
        # 基于字符多样性
        unique_chars = len(set(text))
        diversity = unique_chars / max(1, len(text))
        
        # 基于句子长度方差
        sentences = re.split(r'[。！？；.!?;]', text)
        sentence_lengths = [len(s) for s in sentences if s.strip()]
        if len(sentence_lengths) < 2:
            variance = 0
        else:
            variance = np.var(sentence_lengths)
            variance = min(variance / 10000, 1.0)
        
        # 基于特殊字符密度
        special_chars = len(re.findall(r'[0-9]|[@#$%^&*()_+{}[\]:;"\'<>|]', text))
        special_density = special_chars / max(1, len(text))
        
        complexity = (diversity * 0.4 + variance * 0.3 + special_density * 0.3)
        return min(1.0, complexity)
    
    def _adjust_chunk_size(self, text: str) -> int:
        """根据文本复杂度动态调整分块大小"""
        complexity = self._analyze_text_complexity(text)
        
        # 复杂文本使用较小的分块，简单文本使用较大的分块
        adjusted_size = int(
            self.max_chunk_size - 
            complexity * (self.max_chunk_size - self.min_chunk_size)
        )
        
        return adjusted_size
    
    def chunk(self, text: str) -> List[ChunkResult]:
        """自适应分块"""
        if not text.strip():
            return []
        
        # 动态调整分块大小
        optimal_chunk_size = self._adjust_chunk_size(text)
        
        # 使用语义分块作为基础
        semantic_chunker = SemanticChunkingStrategy(optimal_chunk_size, self.chunk_overlap)
        chunks = semantic_chunker.chunk(text)
        
        # 优化重叠
        optimized_chunks = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev_chunk = chunks[i-1]
                optimal_overlap = self.overlap_optimizer.calculate_optimal_overlap(
                    prev_chunk.content,
                    chunk.content,
                    self.chunk_overlap
                )
                
                # 调整当前分块的起始位置
                new_start = max(0, chunk.start_index - (optimal_overlap - self.chunk_overlap))
                chunk.content = text[new_start:chunk.end_index]
                chunk.start_index = new_start
            
            # 更新质量指标
            chunk.quality_metrics = self._calculate_quality(
                chunk.content, 
                text, 
                chunk.start_index, 
                chunk.end_index
            )
            chunk.metadata['adaptive_chunk_size'] = optimal_chunk_size
            chunk.metadata['strategy'] = 'adaptive'
            
            optimized_chunks.append(chunk)
        
        return optimized_chunks


class ChunkingStrategySystem:
    """智能分块策略系统"""
    
    def __init__(self, default_strategy: ChunkingStrategy = ChunkingStrategy.ADAPTIVE):
        self.default_strategy = default_strategy
        self.strategies = {
            ChunkingStrategy.SENTENCE: SentenceChunkingStrategy,
            ChunkingStrategy.PARAGRAPH: ParagraphChunkingStrategy,
            ChunkingStrategy.SEMANTIC: SemanticChunkingStrategy,
            ChunkingStrategy.ADAPTIVE: AdaptiveChunkingStrategy,
        }
    
    def chunk_text(
        self, 
        text: str, 
        strategy: Optional[ChunkingStrategy] = None,
        **kwargs
    ) -> List[ChunkResult]:
        """使用指定策略分块文本"""
        if strategy is None:
            strategy = self.default_strategy
        
        strategy_class = self.strategies.get(strategy)
        if not strategy_class:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
        
        chunker = strategy_class(**kwargs)
        return chunker.chunk(text)
    
    def evaluate_chunking(
        self, 
        chunks: List[ChunkResult], 
        text: str
    ) -> Dict[str, Any]:
        """评估分块质量"""
        if not chunks:
            return {
                'total_chunks': 0,
                'average_score': 0.0,
                'best_chunk': None,
                'worst_chunk': None,
                'coverage': 0.0
            }
        
        total_score = 0.0
        best_chunk = chunks[0]
        worst_chunk = chunks[0]
        covered_positions = set()
        
        for chunk in chunks:
            if chunk.quality_metrics:
                total_score += chunk.quality_metrics.overall_score
                
                if chunk.quality_metrics.overall_score > best_chunk.quality_metrics.overall_score:
                    best_chunk = chunk
                if chunk.quality_metrics.overall_score < worst_chunk.quality_metrics.overall_score:
                    worst_chunk = chunk
            
            for pos in range(chunk.start_index, chunk.end_index):
                covered_positions.add(pos)
        
        return {
            'total_chunks': len(chunks),
            'average_score': total_score / len(chunks),
            'best_chunk': {
                'index': best_chunk.chunk_index,
                'score': best_chunk.quality_metrics.overall_score if best_chunk.quality_metrics else 0.0,
                'content_length': len(best_chunk.content)
            },
            'worst_chunk': {
                'index': worst_chunk.chunk_index,
                'score': worst_chunk.quality_metrics.overall_score if worst_chunk.quality_metrics else 0.0,
                'content_length': len(worst_chunk.content)
            },
            'coverage': len(covered_positions) / max(1, len(text))
        }
    
    def auto_select_strategy(self, text: str) -> ChunkingStrategy:
        """根据文本特征自动选择最优策略"""
        if not text.strip():
            return ChunkingStrategy.ADAPTIVE
        
        # 检测文本特征
        has_markdown_headers = bool(re.search(r'^#{1,6}\s', text, re.MULTILINE))
        has_numbered_sections = bool(re.search(r'^\d+\.\s', text, re.MULTILINE))
        has_paragraphs = '\n\n' in text
        avg_paragraph_len = np.mean([len(p) for p in text.split('\n\n') if p.strip()]) if '\n\n' in text else 0
        
        # 策略选择逻辑
        if has_markdown_headers or has_numbered_sections:
            return ChunkingStrategy.SEMANTIC
        elif has_paragraphs and avg_paragraph_len < 600:
            return ChunkingStrategy.PARAGRAPH
        else:
            return ChunkingStrategy.ADAPTIVE
