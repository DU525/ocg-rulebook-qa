"""
Services Package

This package contains various service modules for the application.
"""

# Export enhanced memory system
from .enhanced_memory import (
    EnhancedMemorySystem,
    MemoryItem,
    MemoryType,
    ShortTermMemory,
    LongTermMemory,
    WorkingMemory,
    SimHashDeduplicator,
    get_enhanced_memory,
    reset_enhanced_memory,
)

# Export memory retriever
from .memory_retriever import (
    MemoryRetriever,
    RetrievalStrategy,
    RetrievalResult,
    BM25Engine,
    SemanticSearcher,
    Tokenizer,
    get_memory_retriever,
    reset_memory_retriever,
)

# Export chunking strategy system
from .chunking_strategy import (
    ChunkingStrategy,
    ChunkQualityMetrics,
    ChunkResult,
    ChunkingStrategyBase,
    SentenceChunkingStrategy,
    ParagraphChunkingStrategy,
    SemanticBoundaryDetector,
    SemanticChunkingStrategy,
    OverlapOptimizer,
    AdaptiveChunkingStrategy,
    ChunkingStrategySystem,
)

__all__ = [
    # Enhanced memory system
    'EnhancedMemorySystem',
    'MemoryItem',
    'MemoryType',
    'ShortTermMemory',
    'LongTermMemory',
    'WorkingMemory',
    'SimHashDeduplicator',
    'get_enhanced_memory',
    'reset_enhanced_memory',
    
    # Memory retriever
    'MemoryRetriever',
    'RetrievalStrategy',
    'RetrievalResult',
    'BM25Engine',
    'SemanticSearcher',
    'Tokenizer',
    'get_memory_retriever',
    'reset_memory_retriever',
    
    # Chunking strategy system
    'ChunkingStrategy',
    'ChunkQualityMetrics',
    'ChunkResult',
    'ChunkingStrategyBase',
    'SentenceChunkingStrategy',
    'ParagraphChunkingStrategy',
    'SemanticBoundaryDetector',
    'SemanticChunkingStrategy',
    'OverlapOptimizer',
    'AdaptiveChunkingStrategy',
    'ChunkingStrategySystem',
]
