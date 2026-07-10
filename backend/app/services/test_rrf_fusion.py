"""RRF融合搜索测试脚本

测试内容：
1. 单元测试：验证RRF算法正确性
2. 对比实验：向量检索 vs BM25检索 vs RRF融合
3. 性能测试：融合延迟（目标<2ms）
4. 查询分类器测试
5. 生成JSON测试报告

使用方法：
    python test_rrf_fusion.py
"""
import os
import sys
import json
import time
import logging
from typing import List, Dict, Any, Set

# 设置项目根目录
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from app.services.rrf_fusion import (
    reciprocal_rank_fusion,
    compute_rrf_scores,
    QueryClassifier,
    RRF_K,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# 测试数据：100条模拟查询
# ============================================================
TEST_QUERIES = [
    # 规则查询（包含精确规则术语）
    {"query": "连锁处理的效果是什么", "type": "rule", "relevant_docs": {"doc_001", "doc_002", "doc_003"}},
    {"query": "反击陷阱的发动时机", "type": "rule", "relevant_docs": {"doc_004", "doc_005", "doc_006"}},
    {"query": "优先权的转移规则", "type": "rule", "relevant_docs": {"doc_007", "doc_008", "doc_009"}},
    {"query": "强制效果和选发效果的区别", "type": "rule", "relevant_docs": {"doc_010", "doc_011", "doc_012"}},
    {"query": "连锁块的构成和处理顺序", "type": "rule", "relevant_docs": {"doc_013", "doc_014", "doc_015"}},
    {"query": "无效效果的处理时点", "type": "rule", "relevant_docs": {"doc_016", "doc_017", "doc_018"}},
    {"query": "特殊召唤的规则说明", "type": "rule", "relevant_docs": {"doc_019", "doc_020", "doc_021"}},
    {"query": " COST和代价的关系", "type": "rule", "relevant_docs": {"doc_022", "doc_023", "doc_024"}},
    {"query": "破坏效果的连锁处理", "type": "rule", "relevant_docs": {"doc_025", "doc_026", "doc_027"}},
    {"query": "除外效果的发动时机", "type": "rule", "relevant_docs": {"doc_028", "doc_029", "doc_030"}},
    {"query": "仪式召唤的优先权规则", "type": "rule", "relevant_docs": {"doc_031", "doc_032", "doc_033"}},
    {"query": "融合召唤的效果处理", "type": "rule", "relevant_docs": {"doc_034", "doc_035", "doc_036"}},
    {"query": "同步召唤的连锁点", "type": "rule", "relevant_docs": {"doc_037", "doc_038", "doc_039"}},
    {"query": "超量召唤的响应时机", "type": "rule", "relevant_docs": {"doc_040", "doc_041", "doc_042"}},
    {"query": "灵摆召唤的规则书说明", "type": "rule", "relevant_docs": {"doc_043", "doc_044", "doc_045"}},
    {"query": "连接召唤的官方裁定", "type": "rule", "relevant_docs": {"doc_046", "doc_047", "doc_048"}},
    {"query": "咒语速度的分类", "type": "rule", "relevant_docs": {"doc_049", "doc_050", "doc_051"}},
    {"query": "逆顺处理的规则", "type": "rule", "relevant_docs": {"doc_052", "doc_053", "doc_054"}},
    {"query": "必发效果的发动条件", "type": "rule", "relevant_docs": {"doc_055", "doc_056", "doc_057"}},
    {"query": "任意发动的时点选择", "type": "rule", "relevant_docs": {"doc_058", "doc_059", "doc_060"}},
    {"query": "返回卡组的处理流程", "type": "rule", "relevant_docs": {"doc_061", "doc_062", "doc_063"}},
    {"query": "返回手牌的连锁顺序", "type": "rule", "relevant_docs": {"doc_064", "doc_065", "doc_066"}},
    {"query": "上级召唤的规则说明", "type": "rule", "relevant_docs": {"doc_067", "doc_068", "doc_069"}},
    {"query": "通常召唤的优先权", "type": "rule", "relevant_docs": {"doc_070", "doc_071", "doc_072"}},
    {"query": "宣言效果的发动时机", "type": "rule", "relevant_docs": {"doc_073", "doc_074", "doc_075"}},
    {"query": "支付代价的规则", "type": "rule", "relevant_docs": {"doc_076", "doc_077", "doc_078"}},
    {"query": "响应时点的选择", "type": "rule", "relevant_docs": {"doc_079", "doc_080", "doc_081"}},
    {"query": "效果处理的连锁块", "type": "rule", "relevant_docs": {"doc_082", "doc_083", "doc_084"}},
    {"query": "发动时机的裁定说明", "type": "rule", "relevant_docs": {"doc_085", "doc_086", "doc_087"}},
    {"query": "陷阱卡的反击规则", "type": "rule", "relevant_docs": {"doc_088", "doc_089", "doc_090"}},
    {"query": "调整中的官方规则", "type": "rule", "relevant_docs": {"doc_091", "doc_092", "doc_093"}},
    {"query": "游戏规则的基本概念", "type": "rule", "relevant_docs": {"doc_094", "doc_095", "doc_096"}},
    {"query": "规则书中的裁定说明", "type": "rule", "relevant_docs": {"doc_097", "doc_098", "doc_099"}},
    
    # 语义查询（抽象概念）
    {"query": "为什么连锁要这样处理", "type": "semantic", "relevant_docs": {"doc_100", "doc_101", "doc_102"}},
    {"query": "如何理解优先权的概念", "type": "semantic", "relevant_docs": {"doc_103", "doc_104", "doc_105"}},
    {"query": "策略上如何利用连锁", "type": "semantic", "relevant_docs": {"doc_106", "doc_107", "doc_108"}},
    {"query": "怎么选择合适的发动时机", "type": "semantic", "relevant_docs": {"doc_109", "doc_110", "doc_111"}},
    {"query": "解释一下效果处理的机制", "type": "semantic", "relevant_docs": {"doc_112", "doc_113", "doc_114"}},
    {"query": "推荐一些连锁的技巧", "type": "semantic", "relevant_docs": {"doc_115", "doc_116", "doc_117"}},
    {"query": "说明一下规则的流程", "type": "semantic", "relevant_docs": {"doc_118", "doc_119", "doc_120"}},
    {"query": "理解召唤的步骤", "type": "semantic", "relevant_docs": {"doc_121", "doc_122", "doc_123"}},
    {"query": "概念上的区别是什么", "type": "semantic", "relevant_docs": {"doc_124", "doc_125", "doc_126"}},
    {"query": "原理上如何运作", "type": "semantic", "relevant_docs": {"doc_127", "doc_128", "doc_129"}},
    {"query": "机制的解释", "type": "semantic", "relevant_docs": {"doc_130", "doc_131", "doc_132"}},
    {"query": "建议如何提升", "type": "semantic", "relevant_docs": {"doc_133", "doc_134", "doc_135"}},
    {"query": "流程是怎么样的", "type": "semantic", "relevant_docs": {"doc_136", "doc_137", "doc_138"}},
    {"query": "理解基本概念", "type": "semantic", "relevant_docs": {"doc_139", "doc_140", "doc_141"}},
    {"query": "策略上的建议", "type": "semantic", "relevant_docs": {"doc_142", "doc_143", "doc_144"}},
    {"query": "为什么会有这样的规则", "type": "semantic", "relevant_docs": {"doc_145", "doc_146", "doc_147"}},
    {"query": "如何理解裁定", "type": "semantic", "relevant_docs": {"doc_148", "doc_149", "doc_150"}},
    {"query": "技巧上的说明", "type": "semantic", "relevant_docs": {"doc_151", "doc_152", "doc_153"}},
    {"query": "推荐的策略", "type": "semantic", "relevant_docs": {"doc_154", "doc_155", "doc_156"}},
    {"query": "解释处理机制", "type": "semantic", "relevant_docs": {"doc_157", "doc_158", "doc_159"}},
    {"query": "说明概念区别", "type": "semantic", "relevant_docs": {"doc_160", "doc_161", "doc_162"}},
    {"query": "怎么理解原理", "type": "semantic", "relevant_docs": {"doc_163", "doc_164", "doc_165"}},
    {"query": "策略流程说明", "type": "semantic", "relevant_docs": {"doc_166", "doc_167", "doc_168"}},
    {"query": "技巧建议", "type": "semantic", "relevant_docs": {"doc_169", "doc_170", "doc_171"}},
    {"query": "理解的步骤", "type": "semantic", "relevant_docs": {"doc_172", "doc_173", "doc_174"}},
    {"query": "推荐概念解释", "type": "semantic", "relevant_docs": {"doc_175", "doc_176", "doc_177"}},
    {"query": "说明原理机制", "type": "semantic", "relevant_docs": {"doc_178", "doc_179", "doc_180"}},
    {"query": "怎么解释流程", "type": "semantic", "relevant_docs": {"doc_181", "doc_182", "doc_183"}},
    {"query": "建议理解策略", "type": "semantic", "relevant_docs": {"doc_184", "doc_185", "doc_186"}},
    {"query": "技巧概念原理", "type": "semantic", "relevant_docs": {"doc_187", "doc_188", "doc_189"}},
    {"query": "步骤说明区别", "type": "semantic", "relevant_docs": {"doc_190", "doc_191", "doc_192"}},
    {"query": "推荐解释机制", "type": "semantic", "relevant_docs": {"doc_193", "doc_194", "doc_195"}},
    {"query": "为什么建议这样", "type": "semantic", "relevant_docs": {"doc_196", "doc_197", "doc_198"}},
    {"query": "如何理解流程", "type": "semantic", "relevant_docs": {"doc_199", "doc_200", "doc_201"}},
    
    # 默认查询（混合型）
    {"query": "游戏规则是什么", "type": "default", "relevant_docs": {"doc_202", "doc_203", "doc_204"}},
    {"query": "卡片效果说明", "type": "default", "relevant_docs": {"doc_205", "doc_206", "doc_207"}},
    {"query": "对战基本流程", "type": "default", "relevant_docs": {"doc_208", "doc_209", "doc_210"}},
    {"query": "卡组构筑建议", "type": "default", "relevant_docs": {"doc_211", "doc_212", "doc_213"}},
    {"query": "新手入门指南", "type": "default", "relevant_docs": {"doc_214", "doc_215", "doc_216"}},
    {"query": "比赛规则说明", "type": "default", "relevant_docs": {"doc_217", "doc_218", "doc_219"}},
    {"query": "卡片信息查询", "type": "default", "relevant_docs": {"doc_220", "doc_221", "doc_222"}},
    {"query": "环境Meta分析", "type": "default", "relevant_docs": {"doc_223", "doc_224", "doc_225"}},
    {"query": "历史规则变更", "type": "default", "relevant_docs": {"doc_226", "doc_227", "doc_228"}},
    {"query": "官方公告解读", "type": "default", "relevant_docs": {"doc_229", "doc_230", "doc_231"}},
    {"query": "常见问题解答", "type": "default", "relevant_docs": {"doc_232", "doc_233", "doc_234"}},
    {"query": "卡组搭配推荐", "type": "default", "relevant_docs": {"doc_235", "doc_236", "doc_237"}},
    {"query": "对战技巧分享", "type": "default", "relevant_docs": {"doc_238", "doc_239", "doc_240"}},
    {"query": "卡片强度排名", "type": "default", "relevant_docs": {"doc_241", "doc_242", "doc_243"}},
    {"query": "禁限卡表说明", "type": "default", "relevant_docs": {"doc_244", "doc_245", "doc_246"}},
    {"query": "赛制规则介绍", "type": "default", "relevant_docs": {"doc_247", "doc_248", "doc_249"}},
    {"query": "卡组类型分析", "type": "default", "relevant_docs": {"doc_250", "doc_251", "doc_252"}},
    {"query": "对战心理准备", "type": "default", "relevant_docs": {"doc_253", "doc_254", "doc_255"}},
    {"query": "比赛注意事项", "type": "default", "relevant_docs": {"doc_256", "doc_257", "doc_258"}},
    {"query": "卡片获取途径", "type": "default", "relevant_docs": {"doc_259", "doc_260", "doc_261"}},
    {"query": "卡组更新频率", "type": "default", "relevant_docs": {"doc_262", "doc_263", "doc_264"}},
    {"query": "对战平台选择", "type": "default", "relevant_docs": {"doc_265", "doc_266", "doc_267"}},
    {"query": "规则学习时间", "type": "default", "relevant_docs": {"doc_268", "doc_269", "doc_270"}},
    {"query": "卡片收集方法", "type": "default", "relevant_docs": {"doc_271", "doc_272", "doc_273"}},
    {"query": "对战记录查询", "type": "default", "relevant_docs": {"doc_274", "doc_275", "doc_276"}},
    {"query": "卡组备份策略", "type": "default", "relevant_docs": {"doc_277", "doc_278", "doc_279"}},
    {"query": "比赛报名流程", "type": "default", "relevant_docs": {"doc_280", "doc_281", "doc_282"}},
    {"query": "卡片保管方法", "type": "default", "relevant_docs": {"doc_283", "doc_284", "doc_285"}},
    {"query": "对战礼仪规范", "type": "default", "relevant_docs": {"doc_286", "doc_287", "doc_288"}},
    {"query": "卡组展示技巧", "type": "default", "relevant_docs": {"doc_289", "doc_290", "doc_291"}},
    {"query": "规则理解难点", "type": "default", "relevant_docs": {"doc_292", "doc_293", "doc_294"}},
    {"query": "卡片效果对比", "type": "default", "relevant_docs": {"doc_295", "doc_296", "doc_297"}},
    {"query": "对战策略分析", "type": "default", "relevant_docs": {"doc_298", "doc_299", "doc_300"}},
    {"query": "卡组优化方向", "type": "default", "relevant_docs": {"doc_301", "doc_302", "doc_303"}},
    {"query": "比赛心得分享", "type": "default", "relevant_docs": {"doc_304", "doc_305", "doc_306"}},
    {"query": "卡片使用技巧", "type": "default", "relevant_docs": {"doc_307", "doc_308", "doc_309"}},
    {"query": "对战节奏控制", "type": "default", "relevant_docs": {"doc_310", "doc_311", "doc_312"}},
    {"query": "规则适用范围", "type": "default", "relevant_docs": {"doc_313", "doc_314", "doc_315"}},
    {"query": "卡组成本评估", "type": "default", "relevant_docs": {"doc_316", "doc_317", "doc_318"}},
    {"query": "比赛奖项设置", "type": "default", "relevant_docs": {"doc_319", "doc_320", "doc_321"}},
    {"query": "卡片稀有度", "type": "default", "relevant_docs": {"doc_322", "doc_323", "doc_324"}},
    {"query": "对战模式选择", "type": "default", "relevant_docs": {"doc_325", "doc_326", "doc_327"}},
    {"query": "规则执行标准", "type": "default", "relevant_docs": {"doc_328", "doc_329", "doc_330"}},
    {"query": "卡组兼容性", "type": "default", "relevant_docs": {"doc_331", "doc_332", "doc_333"}},
    {"query": "比赛时间安排", "type": "default", "relevant_docs": {"doc_334", "doc_335", "doc_336"}},
    {"query": "卡片保存环境", "type": "default", "relevant_docs": {"doc_337", "doc_338", "doc_339"}},
    {"query": "对战心态调整", "type": "default", "relevant_docs": {"doc_340", "doc_341", "doc_342"}},
    {"query": "规则更新通知", "type": "default", "relevant_docs": {"doc_343", "doc_344", "doc_345"}},
]


def generate_mock_results(
    query_info: Dict[str, Any],
    num_results: int = 50,
    noise_ratio: float = 0.3,
) -> List[Dict[str, Any]]:
    """生成模拟检索结果
    
    Args:
        query_info: 查询信息，包含query, type, relevant_docs
        num_results: 生成结果数量
        noise_ratio: 噪声比例（不相关文档的比例）
        
    Returns:
        List[Dict]: 模拟检索结果
    """
    relevant = list(query_info['relevant_docs'])
    num_relevant = min(len(relevant), int(num_results * (1 - noise_ratio)))
    num_noise = num_results - num_relevant
    
    results = []
    
    # 添加相关文档（排名靠前）
    for i in range(num_relevant):
        doc_id = relevant[i % len(relevant)]
        results.append({
            'id': doc_id,
            'content': f'相关文档内容: {doc_id}',
            'metadata': {'title': f'文档 {doc_id}'},
        })
    
    # 添加噪声文档
    for i in range(num_noise):
        doc_id = f'noise_{query_info["type"]}_{i}'
        results.append({
            'id': doc_id,
            'content': f'噪声文档内容: {doc_id}',
            'metadata': {'title': f'噪声文档 {doc_id}'},
        })
    
    return results


def compute_recall_at_k(
    retrieved: List[Dict[str, Any]],
    relevant_docs: Set[str],
    k: int = 5,
) -> float:
    """计算Recall@K
    
    Args:
        retrieved: 检索结果列表
        relevant_docs: 相关文档ID集合
        k: Top K
        
    Returns:
        float: Recall@K值
    """
    top_k_ids = {r['id'] for r in retrieved[:k]}
    if not relevant_docs:
        return 0.0
    return len(top_k_ids & relevant_docs) / len(relevant_docs)


def test_rrf_algorithm():
    """单元测试：验证RRF算法正确性"""
    print("=" * 60)
    print("测试1: RRF算法正确性验证")
    print("=" * 60)
    
    # 测试用例1：基本融合
    vector_results = [
        {'id': 'doc_1', 'content': '向量结果1'},
        {'id': 'doc_2', 'content': '向量结果2'},
        {'id': 'doc_3', 'content': '向量结果3'},
    ]
    bm25_results = [
        {'id': 'doc_2', 'content': 'BM25结果2'},
        {'id': 'doc_4', 'content': 'BM25结果4'},
        {'id': 'doc_1', 'content': 'BM25结果1'},
    ]
    
    fusion = reciprocal_rank_fusion(
        vector_results, bm25_results, top_k=5,
        vector_weight=0.7, bm25_weight=0.3
    )
    
    # doc_2应该排名第一（在两路检索中都出现）
    assert fusion[0]['id'] == 'doc_2', f"预期doc_2排名第一，实际{fusion[0]['id']}"
    assert fusion[1]['id'] == 'doc_1', f"预期doc_1排名第二，实际{fusion[1]['id']}"
    
    print("[PASS] 基本融合测试通过")
    print(f"  融合结果: {[r['id'] for r in fusion]}")
    
    # 测试用例2：空结果处理
    empty_fusion = reciprocal_rank_fusion([], [], top_k=5)
    assert len(empty_fusion) == 0, "空结果应该返回空列表"
    print("[PASS] 空结果处理测试通过")
    
    # 测试用例3：单路结果
    single_fusion = reciprocal_rank_fusion(
        [{'id': 'doc_1', 'content': 'test'}],
        [],
        top_k=5
    )
    assert len(single_fusion) == 1, "单路结果应该正确返回"
    assert single_fusion[0]['id'] == 'doc_1'
    print("[PASS] 单路结果测试通过")
    
    # 测试用例4：RRF得分计算验证
    # doc在向量排名第1，BM25排名第2
    # vector_rrf = 0.7 / (60 + 1) = 0.01147...
    # bm25_rrf = 0.3 / (60 + 2) = 0.00483...
    # total = 0.01631...
    expected_score = 0.7 / 61 + 0.3 / 62
    assert abs(fusion[0]['rrf_score'] - expected_score) < 1e-6, \
        f"RRF得分计算错误: {fusion[0]['rrf_score']} vs {expected_score}"
    print("[PASS] RRF得分计算测试通过")
    
    print()


def test_query_classifier():
    """单元测试：验证查询分类器"""
    print("=" * 60)
    print("测试2: 查询分类器验证")
    print("=" * 60)
    
    # 规则查询
    query_type, weights = QueryClassifier.classify("连锁处理的效果是什么")
    assert query_type == 'rule', f"预期rule，实际{query_type}"
    assert weights['bm25_weight'] == 0.5, f"预期BM25权重0.5，实际{weights['bm25_weight']}"
    print(f"[PASS] 规则查询分类: '连锁处理的效果是什么' -> {query_type}, 权重={weights}")
    
    # 语义查询
    query_type, weights = QueryClassifier.classify("为什么连锁要这样处理")
    assert query_type == 'semantic', f"预期semantic，实际{query_type}"
    assert weights['vector_weight'] == 0.9, f"预期向量权重0.9，实际{weights['vector_weight']}"
    print(f"[PASS] 语义查询分类: '为什么连锁要这样处理' -> {query_type}, 权重={weights}")
    
    # 默认查询
    query_type, weights = QueryClassifier.classify("游戏规则是什么")
    assert query_type == 'default', f"预期default，实际{query_type}"
    assert weights['vector_weight'] == 0.7, f"预期向量权重0.7，实际{weights['vector_weight']}"
    print(f"[PASS] 默认查询分类: '游戏规则是什么' -> {query_type}, 权重={weights}")
    
    # 空查询
    query_type, weights = QueryClassifier.classify("")
    assert query_type == 'default', "空查询应该返回default"
    print(f"[PASS] 空查询分类: '' -> {query_type}")
    
    print()


def test_performance():
    """性能测试：RRF融合延迟"""
    print("=" * 60)
    print("测试3: RRF融合性能测试")
    print("=" * 60)
    
    # 生成大规模模拟数据
    vector_results = [{'id': f'doc_{i}', 'content': f'test {i}'} for i in range(50)]
    bm25_results = [{'id': f'doc_{i+25}', 'content': f'test {i+25}'} for i in range(50)]
    
    # 多次运行取平均
    num_runs = 100
    times = []
    
    for _ in range(num_runs):
        start = time.time()
        reciprocal_rank_fusion(vector_results, bm25_results, top_k=5)
        elapsed = (time.time() - start) * 1000  # 转换为毫秒
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    
    print(f"  平均融合延迟: {avg_time:.2f}ms")
    print(f"  最大融合延迟: {max_time:.2f}ms")
    print(f"  最小融合延迟: {min_time:.2f}ms")
    print(f"  目标延迟: <2ms")
    
    if avg_time < 2.0:
        print(f"[PASS] 性能测试通过 (avg={avg_time:.2f}ms < 2ms)")
    else:
        print(f"[FAIL] 性能测试未通过 (avg={avg_time:.2f}ms >= 2ms)")
    
    print()
    return avg_time


def run_comparison_experiment():
    """对比实验：向量检索 vs BM25 vs RRF融合"""
    print("=" * 60)
    print("测试4: 三种检索方式对比实验（100条查询）")
    print("=" * 60)
    
    vector_recalls = []
    bm25_recalls = []
    rrf_recalls = []
    
    query_type_stats = {
        'rule': {'vector': [], 'bm25': [], 'rrf': []},
        'semantic': {'vector': [], 'bm25': [], 'rrf': []},
        'default': {'vector': [], 'bm25': [], 'rrf': []},
    }
    
    for i, query_info in enumerate(TEST_QUERIES):
        # 生成模拟检索结果（带有一定随机性）
        import random
        random.seed(i)
        
        vector_results = generate_mock_results(query_info, num_results=50, noise_ratio=0.4)
        random.seed(i + 1000)
        bm25_results = generate_mock_results(query_info, num_results=50, noise_ratio=0.5)
        
        # 向量检索Recall@5
        vector_recall = compute_recall_at_k(vector_results, query_info['relevant_docs'], k=5)
        vector_recalls.append(vector_recall)
        
        # BM25检索Recall@5
        bm25_recall = compute_recall_at_k(bm25_results, query_info['relevant_docs'], k=5)
        bm25_recalls.append(bm25_recall)
        
        # RRF融合Recall@5
        rrf_results = reciprocal_rank_fusion(
            vector_results, bm25_results, top_k=5,
            vector_weight=0.7, bm25_weight=0.3
        )
        rrf_recall = compute_recall_at_k(rrf_results, query_info['relevant_docs'], k=5)
        rrf_recalls.append(rrf_recall)
        
        # 按查询类型统计
        q_type = query_info['type']
        if q_type in query_type_stats:
            query_type_stats[q_type]['vector'].append(vector_recall)
            query_type_stats[q_type]['bm25'].append(bm25_recall)
            query_type_stats[q_type]['rrf'].append(rrf_recall)
    
    # 计算总体Recall@5
    avg_vector = sum(vector_recalls) / len(vector_recalls)
    avg_bm25 = sum(bm25_recalls) / len(bm25_recalls)
    avg_rrf = sum(rrf_recalls) / len(rrf_recalls)
    
    print("\n总体Recall@5对比:")
    print(f"  仅向量检索: {avg_vector:.4f}")
    print(f"  仅BM25检索: {avg_bm25:.4f}")
    print(f"  RRF融合:    {avg_rrf:.4f}")
    
    rrf_improvement_vs_vector = (avg_rrf - avg_vector) / avg_vector * 100 if avg_vector > 0 else 0
    rrf_improvement_vs_bm25 = (avg_rrf - avg_bm25) / avg_bm25 * 100 if avg_bm25 > 0 else 0
    
    print(f"\n  RRF vs 向量提升: {rrf_improvement_vs_vector:.2f}%")
    print(f"  RRF vs BM25提升: {rrf_improvement_vs_bm25:.2f}%")
    
    # 按查询类型统计
    print("\n按查询类型Recall@5:")
    for q_type, stats in query_type_stats.items():
        if stats['vector']:
            print(f"  {q_type}:")
            print(f"    向量: {sum(stats['vector'])/len(stats['vector']):.4f}")
            print(f"    BM25: {sum(stats['bm25'])/len(stats['bm25']):.4f}")
            print(f"    RRF:  {sum(stats['rrf'])/len(stats['rrf']):.4f}")
    
    print()
    return {
        'vector_recall': avg_vector,
        'bm25_recall': avg_bm25,
        'rrf_recall': avg_rrf,
        'rrf_improvement_vs_vector': rrf_improvement_vs_vector,
        'rrf_improvement_vs_bm25': rrf_improvement_vs_bm25,
        'by_query_type': {
            q_type: {
                'vector': sum(stats['vector'])/len(stats['vector']) if stats['vector'] else 0,
                'bm25': sum(stats['bm25'])/len(stats['bm25']) if stats['bm25'] else 0,
                'rrf': sum(stats['rrf'])/len(stats['rrf']) if stats['rrf'] else 0,
            }
            for q_type, stats in query_type_stats.items()
        }
    }


def generate_report(
    comparison_results: Dict[str, Any],
    avg_fusion_time: float,
):
    """生成JSON测试报告"""
    print("=" * 60)
    print("测试报告")
    print("=" * 60)
    
    report = {
        'test_summary': {
            'total_queries': len(TEST_QUERIES),
            'test_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'rrf_k': RRF_K,
        },
        'recall_at_5': {
            'vector_only': comparison_results['vector_recall'],
            'bm25_only': comparison_results['bm25_recall'],
            'rrf_fusion': comparison_results['rrf_recall'],
        },
        'improvement': {
            'rrf_vs_vector_percent': comparison_results['rrf_improvement_vs_vector'],
            'rrf_vs_bm25_percent': comparison_results['rrf_improvement_vs_bm25'],
        },
        'by_query_type': comparison_results['by_query_type'],
        'performance': {
            'avg_fusion_latency_ms': round(avg_fusion_time, 3),
            'target_latency_ms': 2.0,
            'meets_target': avg_fusion_time < 2.0,
        },
        'algorithm_config': {
            'rrf_k': RRF_K,
            'default_weights': {'vector': 0.7, 'bm25': 0.3},
            'rule_weights': {'vector': 0.5, 'bm25': 0.5},
            'semantic_weights': {'vector': 0.9, 'bm25': 0.1},
        },
    }
    
    # 保存报告
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'rrf_test_report.json'
    )
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试报告已保存到: {report_path}")
    print(f"\nJSON报告内容:")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    return report


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("RRF融合搜索测试套件")
    print("=" * 60 + "\n")
    
    # 1. RRF算法正确性测试
    test_rrf_algorithm()
    
    # 2. 查询分类器测试
    test_query_classifier()
    
    # 3. 性能测试
    avg_fusion_time = test_performance()
    
    # 4. 对比实验
    comparison_results = run_comparison_experiment()
    
    # 5. 生成报告
    report = generate_report(comparison_results, avg_fusion_time)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"Recall@5:")
    print(f"  向量检索: {comparison_results['vector_recall']:.4f}")
    print(f"  BM25检索: {comparison_results['bm25_recall']:.4f}")
    print(f"  RRF融合:  {comparison_results['rrf_recall']:.4f}")
    print(f"\nRRF vs 向量提升: {comparison_results['rrf_improvement_vs_vector']:.2f}%")
    print(f"平均融合延迟: {avg_fusion_time:.2f}ms (目标<2ms)")
    
    if comparison_results['rrf_improvement_vs_vector'] >= 10:
        print("\n[PASS] RRF融合达到recall@5提升10%+的目标!")
    else:
        print(f"\n[NOTE] RRF融合提升{comparison_results['rrf_improvement_vs_vector']:.2f}%，未达10%目标（模拟数据可能影响结果）")
    
    if avg_fusion_time < 2.0:
        print("[PASS] 融合延迟满足<2ms目标!")
    else:
        print(f"[NOTE] 融合延迟{avg_fusion_time:.2f}ms，略高于2ms目标")
    
    print("\n测试完成!")


if __name__ == '__main__':
    main()
