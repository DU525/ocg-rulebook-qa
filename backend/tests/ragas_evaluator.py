"""
RAGAS评估体系 - RAG系统质量量化评估框架
基于4大核心指标：Faithfulness, Answer Relevance, Context Precision, Context Recall
"""
import json
import os
from typing import List, Dict, Optional
from pathlib import Path

try:
    from ragas import EvaluationDataset
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    print("WARNING: ragas not installed. Run: pip install ragas")

from langchain_openai import ChatOpenAI, OpenAIEmbeddings


class RAGASEvaluator:
    """RAGAS评估器"""
    
    METRICS = {
        'faithfulness': {
            'name': '忠实度',
            'description': '评估答案是否忠实于检索到的上下文',
            'metric': None
        },
        'answer_relevancy': {
            'name': '答案相关性',
            'description': '评估答案是否与问题相关',
            'metric': None
        },
        'context_precision': {
            'name': '上下文精确度',
            'description': '评估检索到的上下文是否有助于回答问题',
            'metric': None
        },
        'context_recall': {
            'name': '上下文召回率',
            'description': '评估是否检索到了所有必要的上下文',
            'metric': None
        }
    }
    
    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        llm_api_base: Optional[str] = None,
        llm_model: str = "gpt-3.5-turbo",
        embedding_model: str = "text-embedding-ada-002"
    ):
        """初始化评估器"""
        if not RAGAS_AVAILABLE:
            raise ImportError("ragas not installed")
        
        self.llm_api_key = llm_api_key or os.getenv("OPENAI_API_KEY")
        self.llm_api_base = llm_api_base or os.getenv("OPENAI_API_BASE")
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        
        self.llm = None
        self.embeddings = None
        self._init_models()
    
    def _init_models(self):
        """初始化LLM和Embedding模型"""
        if self.llm_api_key:
            self.llm = LangchainLLMWrapper(
                ChatOpenAI(
                    model=self.llm_model,
                    api_key=self.llm_api_key,
                    base_url=self.llm_api_base
                )
            )
            self.embeddings = LangchainEmbeddingsWrapper(
                OpenAIEmbeddings(
                    model=self.embedding_model,
                    api_key=self.llm_api_key,
                    base_url=self.llm_api_base
                )
            )
            print(f"LLM模型已加载: {self.llm_model}")
            print(f"Embedding模型已加载: {self.embedding_model}")
        else:
            print("WARNING: 未配置API密钥，无法初始化评估模型")
    
    def load_test_dataset(self, dataset_path: str) -> List[Dict]:
        """
        加载测试数据集
        
        Args:
            dataset_path: 测试集JSON文件路径
            
        Returns:
            测试集列表
        """
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
        
        print(f"已加载测试集: {len(dataset)} 条问答对")
        return dataset
    
    def evaluate(
        self,
        dataset: List[Dict],
        metrics: Optional[List[str]] = None,
        batch_size: int = 10
    ) -> Dict:
        """
        执行RAGAS评估
        
        Args:
            dataset: 测试集数据
            metrics: 要评估的指标列表，默认评估全部4项
            batch_size: 批次大小
            
        Returns:
            评估结果字典
        """
        if metrics is None:
            metrics = list(self.METRICS.keys())
        
        # 转换为RAGAS格式
        eval_data = []
        for item in dataset:
            eval_data.append({
                'question': item.get('question', ''),
                'answer': item.get('answer', ''),
                'contexts': item.get('contexts', []),
                'ground_truth': item.get('ground_truth', '')
            })
        
        # 创建评估数据集
        ragas_dataset = EvaluationDataset.from_list(eval_data)
        
        # 构建指标列表
        metrics_to_eval = []
        for metric_name in metrics:
            if metric_name == 'faithfulness':
                metrics_to_eval.append(faithfulness)
            elif metric_name == 'answer_relevancy':
                metrics_to_eval.append(answer_relevancy)
            elif metric_name == 'context_precision':
                metrics_to_eval.append(context_precision)
            elif metric_name == 'context_recall':
                metrics_to_eval.append(context_recall)
        
        # 执行评估
        print(f"开始评估 {len(dataset)} 条数据，使用指标: {', '.join(metrics)}")
        
        results = {}
        try:
            from ragas import evaluate as ragas_evaluate
            
            eval_result = ragas_evaluate(
                dataset=ragas_dataset,
                metrics=metrics_to_eval,
                llm=self.llm,
                embeddings=self.embeddings,
                batch_size=batch_size
            )
            
            # 解析结果
            df = eval_result.to_pandas()
            
            for metric_name in metrics:
                column_name = metric_name
                if column_name in df.columns:
                    mean_score = df[column_name].mean()
                    results[metric_name] = {
                        'mean': mean_score,
                        'std': df[column_name].std(),
                        'min': df[column_name].min(),
                        'max': df[column_name].max(),
                        'count': len(df)
                    }
                    print(f"{self.METRICS[metric_name]['name']}: {mean_score:.4f}")
            
        except Exception as e:
            print(f"评估过程出现错误: {str(e)}")
            results['error'] = str(e)
        
        return results
    
    def generate_report(self, results: Dict, output_path: str):
        """
        生成评估报告
        
        Args:
            results: 评估结果
            output_path: 报告输出路径
        """
        report_lines = [
            "# RAGAS评估报告",
            "",
            "## 评估概览",
            ""
        ]
        
        for metric_name, metric_result in results.items():
            if metric_name == 'error':
                continue
            
            metric_info = self.METRICS.get(metric_name, {})
            report_lines.append(f"### {metric_info.get('name', metric_name)}")
            report_lines.append(f"- **平均分**: {metric_result['mean']:.4f}")
            report_lines.append(f"- **标准差**: {metric_result['std']:.4f}")
            report_lines.append(f"- **最低分**: {metric_result['min']:.4f}")
            report_lines.append(f"- **最高分**: {metric_result['max']:.4f}")
            report_lines.append(f"- **评估数量**: {metric_result['count']}")
            report_lines.append(f"- **说明**: {metric_info.get('description', '')}")
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        # 写入文件
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"评估报告已保存至: {output_path}")
        return report_content


def create_test_dataset_template(output_path: str, size: int = 1000):
    """
    创建测试集模板
    
    Args:
        output_path: 输出文件路径
        size: 测试集大小
    """
    # 这里可以从实际历史对话中抽取
    # 目前先创建一个模板
    dataset = []
    
    for i in range(size):
        dataset.append({
            'question': f'示例问题{i+1}',
            'answer': f'示例答案{i+1}',
            'contexts': [f'示例上下文{i+1}-1', f'示例上下文{i+1}-2'],
            'ground_truth': f'标准答案{i+1}'
        })
    
    # 写入文件
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    
    print(f"测试集模板已生成: {output_path} ({size}条)")


if __name__ == "__main__":
    # 示例用法
    print("=" * 60)
    print("RAGAS评估体系初始化")
    print("=" * 60)
    
    # 创建测试集
    dataset_path = os.path.join(os.path.dirname(__file__), 'test_dataset.json')
    create_test_dataset_template(dataset_path, size=100)
    
    # 初始化评估器
    try:
        evaluator = RAGASEvaluator()
        print("\n评估器初始化成功")
    except Exception as e:
        print(f"\n评估器初始化失败: {e}")
