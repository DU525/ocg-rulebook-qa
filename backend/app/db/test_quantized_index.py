
"""FAISS 量化索引性能对比测试"""
import os
import sys
import time
import json
import logging
import numpy as np
from typing import Dict, List, Any, Tuple
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.db.faiss_quantized_index import (
    QuantizedIndex,
    QuantizedIndexConfig,
    QuantizedVectorRAG
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IndexPerformanceTester:
    """索引性能对比测试器"""
    
    def __init__(
        self,
        dimension: int = 768,
        num_vectors: int = 120000,
        num_queries: int = 1000,
        top_k: int = 5
    ):
        self.dimension = dimension
        self.num_vectors = num_vectors
        self.num_queries = num_queries
        self.top_k = top_k
        self.ground_truth_indices: np.ndarray = None
        self.embeddings: np.ndarray = None
        self.query_embeddings: np.ndarray = None
    
    def generate_test_data(self, seed: int = 42):
        """生成测试数据
        
        Args:
            seed: 随机种子
        """
        np.random.seed(seed)
        
        logger.info(f"Generating test data: {self.num_vectors} vectors of dimension {self.dimension}...")
        
        # 生成数据库向量
        self.embeddings = np.random.randn(self.num_vectors, self.dimension).astype('float32')
        
        # 生成查询向量
        self.query_embeddings = np.random.randn(self.num_queries, self.dimension).astype('float32')
        
        logger.info(f"Test data generated: {self.embeddings.shape[0]} vectors, {self.query_embeddings.shape[0]} queries")
    
    def compute_ground_truth(self):
        """使用暴力搜索计算 Ground Truth（用于 Recall 计算）"""
        logger.info("Computing ground truth with brute-force search...")
        
        brute_index = QuantizedIndex(index_type=QuantizedIndexConfig.INDEX_TYPE_HNSW, dimension=self.dimension)
        brute_index.build_hnsw_index(self.embeddings)
        
        ground_truth = []
        for i in range(self.num_queries):
            distances, indices = brute_index.search_quantized(self.query_embeddings[i:i+1], self.top_k)
            ground_truth.append(indices[0])
        
        self.ground_truth_indices = np.array(ground_truth)
        logger.info("Ground truth computed")
    
    def test_index(
        self,
        index_type: str,
        nlist: Optional[int] = None,
        nprobe: Optional[int] = None,
        m: Optional[int] = None,
        nbits: Optional[int] = None
    ) -&gt; Dict[str, Any]:
        """测试单个索引类型的性能
        
        Args:
            index_type: 索引类型 (hnsw/ivf/ivfpq)
            nlist: IVF 聚类数
            nprobe: 查询时搜索的聚类数
            m: PQ 分段数
            nbits: PQ 每个分段的位数
        
        Returns:
            性能测试结果
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing {index_type.upper()} index")
        logger.info(f"{'='*60}")
        
        # 创建索引
        index = QuantizedIndex(
            index_type=index_type,
            dimension=self.dimension,
            nlist=nlist,
            nprobe=nprobe,
            m=m,
            nbits=nbits
        )
        
        # 构建索引
        build_start = time.time()
        if index_type == QuantizedIndexConfig.INDEX_TYPE_HNSW:
            index.build_hnsw_index(self.embeddings)
        elif index_type == QuantizedIndexConfig.INDEX_TYPE_IVF:
            index.build_ivf_index(self.embeddings)
        elif index_type == QuantizedIndexConfig.INDEX_TYPE_IVFPQ:
            index.build_ivfpq_index(self.embeddings)
        build_time = time.time() - build_start
        
        # 计算内存使用
        mem_info = index.estimate_memory_usage()
        
        # 测试搜索性能
        search_start = time.time()
        all_results = []
        for i in range(self.num_queries):
            distances, indices = index.search_quantized(self.query_embeddings[i:i+1], self.top_k)
            all_results.append(indices[0])
        search_time = time.time() - search_start
        
        qps = self.num_queries / search_time
        
        # 计算 Recall@k
        recall = self._compute_recall(np.array(all_results))
        
        result = {
            'index_type': index_type,
            'config': {
                'nlist': nlist,
                'nprobe': nprobe,
                'm': m,
                'nbits': nbits
            },
            'build_time_s': build_time,
            'search_time_s': search_time,
            'qps': qps,
            'recall_at_k': recall,
            'memory_usage_mb': mem_info['total_mb'],
            'memory_details': mem_info
        }
        
        logger.info(f"Build time: {build_time:.2f}s")
        logger.info(f"Search time: {search_time:.2f}s ({qps:.1f} QPS)")
        logger.info(f"Recall@{self.top_k}: {recall:.4f}")
        logger.info(f"Memory usage: {mem_info['total_mb']:.2f} MB")
        
        return result
    
    def _compute_recall(self, predicted_indices: np.ndarray) -&gt; float:
        """计算 Recall@k
        
        Args:
            predicted_indices: 预测的索引数组
        
        Returns:
            Recall 值
        """
        if self.ground_truth_indices is None:
            logger.warning("No ground truth available, skipping recall calculation")
            return 1.0
        
        correct = 0
        total = self.num_queries * self.top_k
        
        for i in range(self.num_queries):
            gt_set = set(self.ground_truth_indices[i])
            for pred_idx in predicted_indices[i]:
                if pred_idx in gt_set:
                    correct += 1
        
        return correct / total
    
    def run_full_comparison(self) -&gt; Dict[str, Any]:
        """运行完整的性能对比测试
        
        Returns:
            所有索引类型的测试结果
        """
        logger.info("="*60)
        logger.info("FAISS Quantized Index Performance Comparison")
        logger.info("="*60)
        
        self.generate_test_data()
        self.compute_ground_truth()
        
        results = {}
        
        # 测试 HNSW
        results['hnsw'] = self.test_index(
            index_type=QuantizedIndexConfig.INDEX_TYPE_HNSW
        )
        
        # 测试 IVF
        results['ivf'] = self.test_index(
            index_type=QuantizedIndexConfig.INDEX_TYPE_IVF,
            nlist=QuantizedIndexConfig.IVF_NLIST,
            nprobe=QuantizedIndexConfig.IVF_NPROBE
        )
        
        # 测试 IVFPQ
        results['ivfpq'] = self.test_index(
            index_type=QuantizedIndexConfig.INDEX_TYPE_IVFPQ,
            nlist=QuantizedIndexConfig.IVFPQ_NLIST,
            nprobe=QuantizedIndexConfig.IVFPQ_NPROBE,
            m=QuantizedIndexConfig.IVFPQ_M,
            nbits=QuantizedIndexConfig.IVFPQ_NBITS
        )
        
        # 生成对比报告
        report = self._generate_comparison_report(results)
        
        return {
            'results': results,
            'report': report
        }
    
    def _generate_comparison_report(self, results: Dict[str, Any]) -&gt; str:
        """生成对比报告
        
        Args:
            results: 测试结果
        
        Returns:
            格式化的报告字符串
        """
        hnsw_result = results.get('hnsw', {})
        ivf_result = results.get('ivf', {})
        ivfpq_result = results.get('ivfpq', {})
        
        report_lines = []
        report_lines.append("\n" + "="*80)
        report_lines.append("PERFORMANCE COMPARISON REPORT")
        report_lines.append("="*80)
        
        # 表头
        report_lines.append(f"\n{'Index Type':&lt;10} {'Memory (MB)':&lt;15} {'Recall@5':&lt;12} {'QPS':&lt;10} {'Build Time (s)':&lt;15}")
        report_lines.append("-"*80)
        
        for idx_type in ['hnsw', 'ivf', 'ivfpq']:
            res = results.get(idx_type, {})
            mem = res.get('memory_usage_mb', 0)
            recall = res.get('recall_at_k', 0)
            qps = res.get('qps', 0)
            build_time = res.get('build_time_s', 0)
            report_lines.append(
                f"{idx_type:&lt;10} {mem:&lt;15.2f} {recall:&lt;12.4f} {qps:&lt;10.1f} {build_time:&lt;15.2f}"
            )
        
        # 相对对比（以 HNSW 为基准）
        if hnsw_result and ivfpq_result:
            hnsw_mem = hnsw_result.get('memory_usage_mb', 1)
            hnsw_recall = hnsw_result.get('recall_at_k', 1)
            hnsw_qps = hnsw_result.get('qps', 1)
            
            ivfpq_mem = ivfpq_result.get('memory_usage_mb', 0)
            ivfpq_recall = ivfpq_result.get('recall_at_k', 0)
            ivfpq_qps = ivfpq_result.get('qps', 0)
            
            mem_reduction = (1 - ivfpq_mem / hnsw_mem) * 100
            recall_drop = (1 - ivfpq_recall / hnsw_recall) * 100
            qps_speedup = ivfpq_qps / hnsw_qps
            
            report_lines.append("\n" + "="*80)
            report_lines.append("IVFPQ vs HNSW COMPARISON")
            report_lines.append("="*80)
            report_lines.append(f"Memory Reduction: {mem_reduction:.1f}%")
            report_lines.append(f"Recall Drop: {recall_drop:.2f}%")
            report_lines.append(f"QPS Speedup: {qps_speedup:.1f}x")
            
            # 目标检查
            report_lines.append("\nTARGET CHECK:")
            target_met = True
            if mem_reduction &lt; 70:
                report_lines.append(f"❌ Memory reduction target (-70%): NOT MET ({mem_reduction:.1f}%)")
                target_met = False
            else:
                report_lines.append(f"✅ Memory reduction target (-70%): MET ({mem_reduction:.1f}%)")
            
            if recall_drop &gt; 2:
                report_lines.append(f"❌ Recall drop target (&lt;2%): NOT MET ({recall_drop:.2f}%)")
                target_met = False
            else:
                report_lines.append(f"✅ Recall drop target (&lt;2%): MET ({recall_drop:.2f}%)")
            
            if qps_speedup &lt; 3:
                report_lines.append(f"❌ QPS speedup target (≥3x): NOT MET ({qps_speedup:.1f}x)")
                target_met = False
            else:
                report_lines.append(f"✅ QPS speedup target (≥3x): MET ({qps_speedup:.1f}x)")
            
            if target_met:
                report_lines.append("\n🎉 ALL TARGETS MET!")
            else:
                report_lines.append("\n⚠️ Some targets not met")
        
        report = "\n".join(report_lines)
        logger.info(report)
        
        return report
    
    def save_report(self, output_file: str, comparison_data: Dict[str, Any]):
        """保存报告到文件
        
        Args:
            output_file: 输出文件路径
            comparison_data: 对比数据
        """
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        
        # 保存 JSON 数据
        json_file = output_file.replace('.txt', '.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(comparison_data['results'], f, indent=2, ensure_ascii=False)
        logger.info(f"Results saved to {json_file}")
        
        # 保存文本报告
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(comparison_data['report'])
        logger.info(f"Report saved to {output_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FAISS Quantized Index Performance Tester')
    parser.add_argument('--num-vectors', type=int, default=120000, help='Number of test vectors')
    parser.add_argument('--num-queries', type=int, default=1000, help='Number of test queries')
    parser.add_argument('--dimension', type=int, default=768, help='Vector dimension')
    parser.add_argument('--output', type=str, default='performance_report.txt', help='Output report file')
    
    args = parser.parse_args()
    
    tester = IndexPerformanceTester(
        dimension=args.dimension,
        num_vectors=args.num_vectors,
        num_queries=args.num_queries
    )
    
    comparison_data = tester.run_full_comparison()
    tester.save_report(args.output, comparison_data)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

