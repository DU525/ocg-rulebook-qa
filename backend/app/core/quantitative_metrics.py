"""
多维量化指标体系 - RAG系统质量量化评估标准

建立完整的量化指标体系，包括：
1. RAG质量指标（4大核心）
2. 性能指标（延迟、吞吐量）
3. 业务指标（用户满意度、准确率）
4. 系统指标（可用性、可靠性）

每个指标定义：
- 名称、描述、计算方法
- 目标值、告警阈值
- 优化建议
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum


class MetricCategory(Enum):
    """指标分类"""
    RAG_QUALITY = "RAG质量指标"      # RAG核心质量
    PERFORMANCE = "性能指标"          # 延迟、吞吐量
    BUSINESS = "业务指标"             # 准确率、满意度
    SYSTEM = "系统指标"              # 可用性、可靠性


class MetricLevel(Enum):
    """指标级别"""
    PRIMARY = "primary"      # 核心指标（必须监控）
    SECONDARY = "secondary"  # 次要指标（建议监控）
    DIAGNOSTIC = "diagnostic"  # 诊断指标（问题排查用）


@dataclass
class MetricDefinition:
    """指标定义"""
    name: str
    display_name: str
    category: MetricCategory
    level: MetricLevel
    description: str
    calculation: str
    unit: str
    current_value: Optional[float] = None
    baseline: Optional[float] = None
    target: float = 0.0
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    weight: float = 1.0  # 权重（用于综合评分）
    optimization_suggestions: List[str] = None

    def __post_init__(self):
        if self.optimization_suggestions is None:
            self.optimization_suggestions = []


class QuantitativeMetricsFramework:
    """
    多维量化指标体系框架
    
    建立标准化的指标定义、计算方法、优化建议
    """

    # RAG质量指标定义（4大核心）
    RAG_QUALITY_METRICS = {
        "faithfulness": MetricDefinition(
            name="faithfulness",
            display_name="答案忠实度",
            category=MetricCategory.RAG_QUALITY,
            level=MetricLevel.PRIMARY,
            description="评估答案是否忠实于检索到的上下文，检测幻觉内容",
            calculation="生成的答案中，从上下文中得到支持的事实数量 / 答案中的事实总数",
            unit="分数 (0-1)",
            target=0.85,
            warning_threshold=0.75,
            critical_threshold=0.60,
            weight=0.30,
            optimization_suggestions=[
                "1. 增强Prompt模板的自我验证引导",
                "2. 添加链式思考（Chain-of-Thought）推理步骤",
                "3. 使用Few-Shot高质量示例",
                "4. 优化检索结果的相关性过滤",
                "5. 添加答案与上下文的对比验证"
            ]
        ),
        "answer_relevancy": MetricDefinition(
            name="answer_relevancy",
            display_name="答案相关性",
            category=MetricCategory.RAG_QUALITY,
            level=MetricLevel.PRIMARY,
            description="评估答案是否直接回答了用户问题",
            calculation="问题与生成答案的语义相似度（使用embedding计算）",
            unit="分数 (0-1)",
            target=0.80,
            warning_threshold=0.70,
            critical_threshold=0.55,
            weight=0.30,
            optimization_suggestions=[
                "1. 优化Query分类准确性",
                "2. 根据问题类型选择最优Prompt模板",
                "3. 增强答案格式的严格性",
                "4. 添加问题-答案对的重排序",
                "5. 实施多轮对话上下文增强"
            ]
        ),
        "context_precision": MetricDefinition(
            name="context_precision",
            display_name="上下文精确度",
            category=MetricCategory.RAG_QUALITY,
            level=MetricLevel.PRIMARY,
            description="评估检索到的上下文块中，与答案相关的内容比例",
            calculation="相关上下文数量 / 总上下文数量（按重要性加权）",
            unit="分数 (0-1)",
            target=0.75,
            warning_threshold=0.65,
            critical_threshold=0.50,
            weight=0.20,
            optimization_suggestions=[
                "1. 优化向量检索的相似度计算",
                "2. 使用Cross-Encoder重排序",
                "3. 实施BM25+向量混合检索",
                "4. 增强Query扩展和改写",
                "5. 添加检索结果去重和多样性控制"
            ]
        ),
        "context_recall": MetricDefinition(
            name="context_recall",
            display_name="上下文召回率",
            category=MetricCategory.RAG_QUALITY,
            level=MetricLevel.PRIMARY,
            description="评估是否检索到了回答问题所需的所有关键信息",
            calculation="检索到的关键信息数 / 问题所需的关键信息总数",
            unit="分数 (0-1)",
            target=0.80,
            warning_threshold=0.70,
            critical_threshold=0.55,
            weight=0.20,
            optimization_suggestions=[
                "1. 扩展Query优化，增加同义词和查询变体",
                "2. 实施复杂问题的Query分解",
                "3. 优化知识库的Chunking策略",
                "4. 增加检索的top_k数量",
                "5. 跨知识库检索增强（OCG+DM）"
            ]
        )
    }

    # 性能指标定义
    PERFORMANCE_METRICS = {
        "ttfb": MetricDefinition(
            name="ttfb",
            display_name="首字节时间",
            category=MetricCategory.PERFORMANCE,
            level=MetricLevel.PRIMARY,
            description="Time To First Byte - 从请求到收到第一个字节的时间",
            calculation="LLM首字节时间 - 请求开始时间",
            unit="毫秒 (ms)",
            target=500,
            warning_threshold=1000,
            critical_threshold=2000,
            weight=0.15,
            optimization_suggestions=[
                "1. 启用流式输出（SSE）",
                "2. 优化模型推理的批量处理",
                "3. 使用更小的模型处理简单查询",
                "4. 添加LLM调用的超时控制",
                "5. 实施预测性预热"
            ]
        ),
        "avg_latency": MetricDefinition(
            name="avg_latency",
            display_name="平均响应延迟",
            category=MetricCategory.PERFORMANCE,
            level=MetricLevel.PRIMARY,
            description="从请求到完整响应的时间",
            calculation="响应完成时间 - 请求开始时间",
            unit="毫秒 (ms)",
            target=3000,
            warning_threshold=5000,
            critical_threshold=10000,
            weight=0.20,
            optimization_suggestions=[
                "1. 添加多级缓存（L1内存 + L2 Redis）",
                "2. 优化向量检索的索引结构",
                "3. 减少不必要的检索步骤",
                "4. 使用量化索引减少计算量",
                "5. 并行化检索和生成步骤"
            ]
        ),
        "p95_latency": MetricDefinition(
            name="p95_latency",
            display_name="P95响应延迟",
            category=MetricCategory.PERFORMANCE,
            level=MetricLevel.SECONDARY,
            description="95%请求的响应时间上限",
            calculation="第95百分位的响应延迟",
            unit="毫秒 (ms)",
            target=5000,
            warning_threshold=8000,
            critical_threshold=15000,
            weight=0.10,
            optimization_suggestions=[
                "1. 分析慢查询日志定位瓶颈",
                "2. 添加请求限流和熔断机制",
                "3. 优化长尾查询的处理策略",
                "4. 使用异步处理非关键路径",
                "5. 添加性能监控告警"
            ]
        ),
        "p99_latency": MetricDefinition(
            name="p99_latency",
            display_name="P99响应延迟",
            category=MetricCategory.PERFORMANCE,
            level=MetricLevel.SECONDARY,
            description="99%请求的响应时间上限",
            calculation="第99百分位的响应延迟",
            unit="毫秒 (ms)",
            target=10000,
            warning_threshold=15000,
            critical_threshold=30000,
            weight=0.05,
            optimization_suggestions=[
                "1. 识别和处理异常慢的请求",
                "2. 添加请求超时和优雅降级",
                "3. 优化冷启动性能",
                "4. 使用连接池复用连接",
                "5. 添加慢查询告警和自动扩容"
            ]
        ),
        "throughput": MetricDefinition(
            name="throughput",
            display_name="系统吞吐量",
            category=MetricCategory.PERFORMANCE,
            level=MetricLevel.SECONDARY,
            description="每秒处理的请求数",
            calculation="总请求数 / 总时间（秒）",
            unit="请求/秒 (QPS)",
            target=50,
            warning_threshold=30,
            critical_threshold=10,
            weight=0.10,
            optimization_suggestions=[
                "1. 水平扩展服务实例",
                "2. 添加负载均衡",
                "3. 优化数据库和缓存访问",
                "4. 使用异步框架处理请求",
                "5. 添加请求合并和批量处理"
            ]
        )
    }

    # 业务指标定义
    BUSINESS_METRICS = {
        "user_satisfaction": MetricDefinition(
            name="user_satisfaction",
            display_name="用户满意度",
            category=MetricCategory.BUSINESS,
            level=MetricLevel.PRIMARY,
            description="用户对回答质量的满意度评分",
            calculation="正面反馈数 / 总反馈数",
            unit="分数 (1-5)",
            target=4.0,
            warning_threshold=3.5,
            critical_threshold=3.0,
            weight=0.25,
            optimization_suggestions=[
                "1. 收集用户反馈并分析原因",
                "2. 针对低满意度场景优化",
                "3. 添加答案的置信度显示",
                "4. 提供追问和建议功能",
                "5. 优化回答的可读性和专业性"
            ]
        ),
        "task_completion_rate": MetricDefinition(
            name="task_completion_rate",
            display_name="任务完成率",
            category=MetricCategory.BUSINESS,
            level=MetricLevel.SECONDARY,
            description="用户问题被成功解决的比例",
            calculation="已解决问题数 / 总问题数",
            unit="百分比 (%)",
            target=85,
            warning_threshold=75,
            critical_threshold=60,
            weight=0.20,
            optimization_suggestions=[
                "1. 分析未解决问题的模式",
                "2. 增强知识库的覆盖范围",
                "3. 添加无法回答时的友好提示",
                "4. 提供转人工客服的选项",
                "5. 优化问题的理解和分类"
            ]
        ),
        "follow_up_rate": MetricDefinition(
            name="follow_up_rate",
            display_name="追问率",
            category=MetricCategory.BUSINESS,
            level=MetricLevel.DIAGNOSTIC,
            description="用户需要追问的比例（过高可能表示回答不够清晰）",
            calculation="追问数 / 总问题数",
            unit="百分比 (%)",
            target=20,
            warning_threshold=30,
            critical_threshold=40,
            weight=0.05,
            optimization_suggestions=[
                "1. 优化答案的完整性和清晰度",
                "2. 添加答案的补充说明",
                "3. 提供相关的延伸问题建议",
                "4. 增强多轮对话的上下文理解",
                "5. 添加答案的结构化展示"
            ]
        )
    }

    # 系统指标定义
    SYSTEM_METRICS = {
        "availability": MetricDefinition(
            name="availability",
            display_name="系统可用性",
            category=MetricCategory.SYSTEM,
            level=MetricLevel.PRIMARY,
            description="系统的可用时间比例",
            calculation="正常运行时间 / 总时间",
            unit="百分比 (%)",
            target=99.9,
            warning_threshold=99.5,
            critical_threshold=99.0,
            weight=0.30,
            optimization_suggestions=[
                "1. 添加多实例部署",
                "2. 实现健康检查和自动恢复",
                "3. 添加熔断和限流机制",
                "4. 优化错误处理和降级策略",
                "5. 建立灾备和快速切换机制"
            ]
        ),
        "cache_hit_rate": MetricDefinition(
            name="cache_hit_rate",
            display_name="缓存命中率",
            category=MetricCategory.SYSTEM,
            level=MetricLevel.SECONDARY,
            description="缓存命中的比例",
            calculation="缓存命中数 / 总请求数",
            unit="百分比 (%)",
            target=70,
            warning_threshold=50,
            critical_threshold=30,
            weight=0.15,
            optimization_suggestions=[
                "1. 优化缓存键的设计",
                "2. 调整缓存的TTL策略",
                "3. 添加多级缓存架构",
                "4. 使用语义缓存减少miss",
                "5. 监控和分析缓存未命中的原因"
            ]
        ),
        "error_rate": MetricDefinition(
            name="error_rate",
            display_name="错误率",
            category=MetricCategory.SYSTEM,
            level=MetricLevel.PRIMARY,
            description="请求失败的比例",
            calculation="错误请求数 / 总请求数",
            unit="百分比 (%)",
            target=0.1,
            warning_threshold=1.0,
            critical_threshold=5.0,
            weight=0.25,
            optimization_suggestions=[
                "1. 添加完善的错误处理",
                "2. 实现重试和降级机制",
                "3. 监控和分析错误模式",
                "4. 添加请求验证和过滤",
                "5. 优化超时和连接管理"
            ]
        ),
        "reliability": MetricDefinition(
            name="reliability",
            display_name="系统可靠性",
            category=MetricCategory.SYSTEM,
            level=MetricLevel.SECONDARY,
            description="系统稳定性和一致性",
            calculation="成功请求 / 总请求（排除超时）",
            unit="百分比 (%)",
            target=99.5,
            warning_threshold=99.0,
            critical_threshold=98.0,
            weight=0.15,
            optimization_suggestions=[
                "1. 添加请求幂等性保证",
                "2. 实现事务和一致性机制",
                "3. 添加数据校验和修复",
                "4. 优化并发控制和锁策略",
                "5. 建立监控和告警体系"
            ]
        )
    }

    # 所有指标汇总
    ALL_METRICS = {
        **RAG_QUALITY_METRICS,
        **PERFORMANCE_METRICS,
        **BUSINESS_METRICS,
        **SYSTEM_METRICS
    }

    @classmethod
    def get_metric_by_name(cls, name: str) -> Optional[MetricDefinition]:
        """根据名称获取指标定义"""
        return cls.ALL_METRICS.get(name)

    @classmethod
    def get_metrics_by_category(cls, category: MetricCategory) -> List[MetricDefinition]:
        """根据分类获取指标列表"""
        return [m for m in cls.ALL_METRICS.values() if m.category == category]

    @classmethod
    def get_metrics_by_level(cls, level: MetricLevel) -> List[MetricDefinition]:
        """根据级别获取指标列表"""
        return [m for m in cls.ALL_METRICS.values() if m.level == level]

    @classmethod
    def get_primary_metrics(cls) -> List[MetricDefinition]:
        """获取核心指标"""
        return cls.get_metrics_by_level(MetricLevel.PRIMARY)

    @classmethod
    def calculate_comprehensive_score(
        cls,
        metrics_values: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """
        计算综合评分
        
        Args:
            metrics_values: 指标名称到值的映射
            
        Returns:
            (综合评分, 各维度评分)
        """
        # 计算各维度评分
        dimension_scores = {}
        
        for category in MetricCategory:
            metrics = cls.get_metrics_by_category(category)
            if not metrics:
                continue
            
            weighted_sum = 0.0
            total_weight = 0.0
            
            for metric in metrics:
                if metric.name in metrics_values:
                    value = metrics_values[metric.name]
                    # 归一化到0-1分数
                    normalized = cls._normalize_metric_value(metric, value)
                    weighted_sum += normalized * metric.weight
                    total_weight += metric.weight
            
            if total_weight > 0:
                dimension_scores[category.value] = weighted_sum / total_weight
        
        # 计算综合评分（加权平均）
        total_score = 0.0
        total_weight = 0.0
        
        for metric in cls.get_primary_metrics():
            if metric.name in metrics_values:
                value = metrics_values[metric.name]
                normalized = cls._normalize_metric_value(metric, value)
                total_score += normalized * metric.weight
                total_weight += metric.weight
        
        comprehensive_score = total_score / total_weight if total_weight > 0 else 0.0
        
        return comprehensive_score, dimension_scores

    @classmethod
    def _normalize_metric_value(
        cls,
        metric: MetricDefinition,
        value: float
    ) -> float:
        """
        归一化指标值到0-1分数
        
        考虑目标值和阈值进行评分
        """
        # 考虑目标值
        target = metric.target
        
        # 对于延迟和错误率，越低越好
        if metric.name in ["ttfb", "avg_latency", "p95_latency", "p99_latency", "error_rate", "follow_up_rate"]:
            # 使用目标值作为基准计算分数
            if value <= metric.critical_threshold:
                return 0.0
            elif value <= metric.warning_threshold:
                return (value - metric.critical_threshold) / (metric.warning_threshold - metric.critical_threshold) * 0.5
            elif value <= target:
                return 0.5 + (value - metric.warning_threshold) / (target - metric.warning_threshold) * 0.25
            else:
                # 超出目标值但还在可接受范围
                return 0.75 + (target / value) * 0.25
        else:
            # 对于质量指标，越高越好
            if value >= metric.target:
                return 1.0
            elif value >= metric.warning_threshold:
                return 0.75 + (value - metric.warning_threshold) / (metric.target - metric.warning_threshold) * 0.25
            elif value >= metric.critical_threshold:
                return 0.5 + (value - metric.critical_threshold) / (metric.warning_threshold - metric.critical_threshold) * 0.25
            else:
                return max(0.0, value / metric.critical_threshold * 0.5)

    @classmethod
    def generate_optimization_report(
        cls,
        metrics_values: Dict[str, float]
    ) -> List[Dict[str, any]]:
        """
        生成优化建议报告
        
        Args:
            metrics_values: 指标名称到值的映射
            
        Returns:
            优化建议列表（按优先级排序）
        """
        suggestions = []
        
        for metric in cls.get_primary_metrics():
            if metric.name not in metrics_values:
                continue
                
            value = metrics_values[metric.name]
            
            # 判断是否需要优化
            need_optimization = False
            priority = "low"
            
            if metric.name in ["ttfb", "avg_latency", "p95_latency", "p99_latency", "error_rate", "follow_up_rate"]:
                if value > metric.warning_threshold:
                    need_optimization = True
                    if value > metric.critical_threshold:
                        priority = "high"
                    else:
                        priority = "medium"
            else:
                if value < metric.warning_threshold:
                    need_optimization = True
                    if value < metric.critical_threshold:
                        priority = "high"
                    else:
                        priority = "medium"
            
            if need_optimization:
                suggestions.append({
                    "metric": metric.name,
                    "display_name": metric.display_name,
                    "current_value": value,
                    "target_value": metric.target,
                    "priority": priority,
                    "suggestions": metric.optimization_suggestions,
                    "weight": metric.weight
                })
        
        # 按优先级和权重排序
        suggestions.sort(key=lambda x: (
            {"high": 0, "medium": 1, "low": 2}[x["priority"]],
            -x["weight"]
        ))
        
        return suggestions


def get_metrics_framework() -> QuantitativeMetricsFramework:
    """获取指标框架实例"""
    return QuantitativeMetricsFramework()
