#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OCG/DM 规则问答测试数据集生成器

功能：
- 从 OCG 和 DM 规则知识库中读取知识块
- 基于规则内容自动生成高质量问答对（无需LLM API）
- 生成1000条测试数据，覆盖不同类别和难度
- 保存到指定 JSON 文件

数据格式：
[
  {
    "question": "问题文本",
    "answer": "答案文本",
    "contexts": ["上下文1", "上下文2"],
    "ground_truth": "标准答案",
    "source": "数据源(ocg/dm)",
    "category": "类别",
    "difficulty": "难度(简单/中等/复杂)"
  }
]
"""

import json
import os
import random
import re
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional


# ==================== 配置常量 ====================

# 数据源路径
OCG_RULES_PATH = r"C:\Users\1\Downloads\ocg-rulebook-qa\ocg-rulebook-qa\data\chunks\ocg_rules_chunks.json"
DM_RULES_PATH = r"C:\Users\1\Downloads\ocg-rulebook-qa\ocg-rulebook-qa\data\chunks\dm_rules_chunks.json"

# 输出路径
OUTPUT_PATH = r"C:\Users\1\Downloads\ocg-rulebook-qa\ocg-rulebook-qa\backend\tests\test_dataset.json"

# 目标生成数量
TARGET_COUNT = 1000

# 随机种子（确保可复现）
RANDOM_SEED = 42


# ==================== 问题模板库 ====================

# OCG 规则问答模板（针对已有Q&A格式的规则块）
OCG_QUESTION_TEMPLATES = [
    # 简单问题 - 直接提取
    "「{card_name}」的效果是什么？",
    "「{card_name}」的效果发动时需要注意什么？",
    "「{card_name}」的效果如何处理？",
    "「{card_name}」的效果能否被连锁？",
    "「{card_name}」的效果能否被无效？",
    
    # 中等问题 - 需要理解规则
    "「{card_name}」的效果处理时，如果目标不在场会怎样？",
    "「{card_name}」的效果和「{card_name2}」的效果同时发动如何处理？",
    "「{card_name}」的效果是取对象效果还是非取对象效果？",
    "「{card_name}」的效果在什么时点可以发动？",
    "「{card_name}」的效果处理完毕后，对方可以做什么？",
    
    # 复杂问题 - 需要综合判断
    "当「{card_name}」和「{card_name2}」的效果在同一时点发动，如何处理连锁顺序？",
    "「{card_name}」的效果处理中，能否插入其他卡的效果？",
    "「{card_name}」的效果被无效后，会触发什么连锁处理？",
    "在「{card_name}」的效果适用中，发动「{card_name2}」会怎样？",
    "「{card_name}」的效果「直到结束阶段」具体什么时候结束？",
]

# DM 规则问答模板（针对规则文档内容）
DM_QUESTION_TEMPLATES = [
    # 基础规则问题
    "数码宝贝卡牌对战的基本规则是什么？",
    "数码宝贝卡牌对战由几名玩家进行？",
    "数码宝贝卡牌对战的综合规则版本是什么？",
    "数码宝贝卡牌对战的最终更新日期是什么时候？",
    
    # 游戏流程问题
    "数码宝贝卡牌对战的游戏流程包括哪些步骤？",
    "数码宝贝卡牌对战的准备阶段需要做什么？",
    "数码宝贝卡牌对战的攻击阶段如何处理？",
    "数码宝贝卡牌对战的阻挡机制是什么？",
    
    # 规则细节问题
    "数码宝贝卡牌对战的判定规则是什么？",
    "数码宝贝卡牌对战的战斗阶段如何处理？",
    "数码宝贝卡牌对战的效果规则是什么？",
    "数码宝贝卡牌对战的关键词效果有哪些？",
    
    # 进阶问题
    "数码宝贝卡牌对战的游戏领域如何划分？",
    "数码宝贝卡牌对战的基础用语有哪些？",
    "数码宝贝卡牌对战的进化规则是什么？",
    "数码宝贝卡牌对战的使用规则是什么？",
]

# 类别映射（OCG metadata category -> 标准类别名）
CATEGORY_MAP = {
    "连锁处理": "连锁规则",
    "效果处理": "效果规则",
    "卡片互动": "卡片交互规则",
    "游戏规则": "基础规则",
    "战斗规则": "战斗规则",
    "魔法卡": "魔法卡规则",
    "陷阱卡": "陷阱卡规则",
    "怪兽卡": "怪兽卡规则",
    "额外卡组": "额外卡组规则",
    "场地规则": "场地规则",
}

# DM 内容分类关键词
DM_CATEGORY_KEYWORDS = {
    "游戏概要": ["游戏人数", "游戏概要", "对战"],
    "游戏领域": ["领域", "区域"],
    "基础用语": ["基础用语", "术语"],
    "游戏准备": ["准备", "初始"],
    "游戏进行": ["进行", "回合", "阶段"],
    "登场规则": ["登场", "放置"],
    "进化规则": ["进化", "进化元"],
    "使用规则": ["使用", "发动"],
    "攻击规则": ["攻击", "攻击宣言"],
    "阻挡规则": ["阻挡", "拦截"],
    "判定规则": ["判定", "判定卡"],
    "战斗规则": ["战斗", "战斗伤害"],
    "效果规则": ["效果", "效果处理"],
    "关键词效果": ["关键词", "速攻", "阻挡者"],
    "规则判定": ["规则判定", "裁定"],
}


# ==================== 工具函数 ====================

def set_seed(seed: int = RANDOM_SEED):
    """设置随机种子以确保结果可复现"""
    random.seed(seed)


def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """
    加载 JSON 文件
    
    Args:
        file_path: JSON 文件路径
        
    Returns:
        解析后的 JSON 数据（列表格式）
        
    Raises:
        FileNotFoundError: 文件不存在时抛出
        json.JSONDecodeError: JSON 格式错误时抛出
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def extract_card_names(content: str) -> List[str]:
    """
    从规则内容中提取卡牌名称（OCG格式）
    
    Args:
        content: 规则内容文本
        
    Returns:
        提取到的卡牌名称列表
    """
    # 匹配「卡牌名称」格式
    pattern = r'「([^」]+)」'
    matches = re.findall(pattern, content)
    # 去重并过滤空字符串
    return list(set([m for m in matches if m.strip()]))


def extract_ruling_content(content: str) -> Tuple[str, str]:
    """
    从OCG规则块中提取问题和裁定内容
    
    Args:
        content: 规则内容文本（格式：问题：... 裁定：...）
        
    Returns:
        (问题文本, 裁定文本) 元组
    """
    # 分割问题和裁定
    q_match = re.search(r'问题[：:]\s*(.*?)(?=裁定|$)', content, re.DOTALL)
    a_match = re.search(r'裁定[：:]\s*(.*)', content, re.DOTALL)
    
    question = q_match.group(1).strip() if q_match else ""
    answer = a_match.group(1).strip() if a_match else ""
    
    return question, answer


def clean_text(text: str) -> str:
    """
    清理文本中的多余空白和换行
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    # 移除多余换行
    text = re.sub(r'\n+', ' ', text)
    # 移除多余空格
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_category(chunk: Dict[str, Any], source: str) -> str:
    """
    获取知识块的标准类别
    
    Args:
        chunk: 知识块数据
        source: 数据源（ocg/dm）
        
    Returns:
        标准化类别名称
    """
    if source == "ocg":
        raw_category = chunk.get("metadata", {}).get("category", "其他")
        return CATEGORY_MAP.get(raw_category, raw_category)
    else:
        # DM 数据基于内容关键词分类
        content = chunk.get("content", "")
        for category, keywords in DM_CATEGORY_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                return category
        return "其他规则"


def get_difficulty(chunk: Dict[str, Any], content_length: int, question_type: str = "direct") -> str:
    """
    根据内容特征和问题类型判断难度
    
    Args:
        chunk: 知识块数据
        content_length: 内容长度
        question_type: 问题类型（direct=直接问答/理解=需要理解/综合=需要综合判断）
        
    Returns:
        难度等级（简单/中等/复杂）
    """
    # 基于问题类型的基础难度
    base_difficulty = {
        "direct": "简单",
        "理解": "中等",
        "综合": "复杂"
    }
    
    # 根据内容长度调整
    if content_length > 200 and question_type == "direct":
        return "中等"  # 长内容的直接问答提升到中等
    
    return base_difficulty.get(question_type, "中等")


# ==================== OCG 问答生成器 ====================

def generate_ocg_qa(chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从 OCG 规则块生成问答对
    
    处理逻辑：
    1. 提取原始问题和裁定
    2. 提取卡牌名称
    3. 使用模板生成多种问法
    4. 基于裁定内容生成答案
    
    Args:
        chunk: OCG 规则知识块
        
    Returns:
        生成的问答对列表
    """
    qa_pairs = []
    content = chunk.get("content", "")
    metadata = chunk.get("metadata", {})
    category = get_category(chunk, "ocg")
    
    # 提取原始问题和裁定
    original_question, ruling = extract_ruling_content(content)
    
    if not original_question or not ruling:
        # 如果不是标准Q&A格式，跳过
        return qa_pairs
    
    # 提取卡牌名称
    card_names = extract_card_names(content)
    
    # 清理文本
    clean_ruling = clean_text(ruling)
    clean_original_q = clean_text(original_question)
    
    # 1. 直接使用原始问题（中等难度）
    qa_pairs.append({
        "question": clean_original_q,
        "answer": clean_ruling,
        "contexts": [clean_text(content)],
        "ground_truth": clean_ruling,
        "source": "ocg",
        "category": category,
        "difficulty": get_difficulty(chunk, len(content), "理解")
    })
    
    # 2. 使用模板生成变体问题（分简单和复杂）
    if len(card_names) >= 1:
        card1 = card_names[0]
        card2 = card_names[1] if len(card_names) > 1 else card1
        
        # 简单问题模板
        simple_templates = [
            "「{card_name}」的效果是什么？",
            "「{card_name}」的效果发动时需要注意什么？",
            "「{card_name}」的效果如何处理？",
        ]
        
        for template in simple_templates:
            try:
                q = template.format(card_name=card1, card_name2=card2)
                qa_pairs.append({
                    "question": q,
                    "answer": clean_ruling,
                    "contexts": [clean_text(content)],
                    "ground_truth": clean_ruling,
                    "source": "ocg",
                    "category": category,
                    "difficulty": get_difficulty(chunk, len(content), "direct")
                })
            except KeyError:
                continue
        
        # 中等问题模板
        medium_templates = [
            "「{card_name}」的效果处理时，如果目标不在场会怎样？",
            "「{card_name}」的效果能否被连锁？",
            "「{card_name}」的效果能否被无效？",
            "「{card_name}」的效果是取对象效果还是非取对象效果？",
            "「{card_name}」的效果在什么时点可以发动？",
        ]
        
        for template in medium_templates:
            try:
                q = template.format(card_name=card1, card_name2=card2)
                qa_pairs.append({
                    "question": q,
                    "answer": clean_ruling,
                    "contexts": [clean_text(content)],
                    "ground_truth": clean_ruling,
                    "source": "ocg",
                    "category": category,
                    "difficulty": get_difficulty(chunk, len(content), "理解")
                })
            except KeyError:
                continue
        
        # 复杂问题模板
        complex_templates = [
            "当「{card_name}」和「{card_name2}」的效果在同一时点发动，如何处理连锁顺序？",
            "「{card_name}」的效果处理中，能否插入其他卡的效果？",
            "「{card_name}」的效果被无效后，会触发什么连锁处理？",
            "在「{card_name}」的效果适用中，发动「{card_name2}」会怎样？",
            "「{card_name}」的效果「直到结束阶段」具体什么时候结束？",
            "「{card_name}」的效果处理完毕后，对方可以做什么？",
        ]
        
        for template in complex_templates:
            try:
                q = template.format(card_name=card1, card_name2=card2)
                qa_pairs.append({
                    "question": q,
                    "answer": clean_ruling,
                    "contexts": [clean_text(content)],
                    "ground_truth": clean_ruling,
                    "source": "ocg",
                    "category": category,
                    "difficulty": get_difficulty(chunk, len(content), "综合")
                })
            except KeyError:
                continue
    
    # 3. 生成基于裁定的理解性问题（中等难度）
    if "连锁" in content:
        qa_pairs.append({
            "question": f"「{card_names[0]}」的连锁处理规则是什么？",
            "answer": clean_ruling,
            "contexts": [clean_text(content)],
            "ground_truth": clean_ruling,
            "source": "ocg",
            "category": "连锁规则",
            "difficulty": "中等"
        })
    
    if "无效" in content:
        qa_pairs.append({
            "question": f"「{card_names[0]}」的效果能否被无效？如何处理？",
            "answer": clean_ruling,
            "contexts": [clean_text(content)],
            "ground_truth": clean_ruling,
            "source": "ocg",
            "category": "效果规则",
            "difficulty": "中等"
        })
    
    if "效果处理" in content or "处理" in content:
        qa_pairs.append({
            "question": f"「{card_names[0]}」的效果处理时需要注意什么？",
            "answer": clean_ruling,
            "contexts": [clean_text(content)],
            "ground_truth": clean_ruling,
            "source": "ocg",
            "category": "效果规则",
            "difficulty": "简单"
        })
    
    return qa_pairs


# ==================== DM 问答生成器 ====================

def generate_dm_qa(chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从 DM 规则块生成问答对
    
    处理逻辑：
    1. 分析内容中的规则章节信息
    2. 基于关键词匹配生成相关问题
    3. 从内容中提取答案
    
    Args:
        chunk: DM 规则知识块
        
    Returns:
        生成的问答对列表
    """
    qa_pairs = []
    content = chunk.get("content", "")
    metadata = chunk.get("metadata", {})
    category = get_category(chunk, "dm")
    
    # 清理内容
    clean_content = clean_text(content)
    
    # 1. 生成版本信息相关问题
    if "Ver" in content or "版本" in content:
        version_match = re.search(r'Ver\.(\S+)', content)
        if version_match:
            version = version_match.group(1)
            qa_pairs.append({
                "question": "数码宝贝卡牌对战综合规则的当前版本是什么？",
                "answer": f"当前版本为 Ver.{version}",
                "contexts": [clean_content],
                "ground_truth": f"Ver.{version}",
                "source": "dm",
                "category": "基础规则",
                "difficulty": "简单"
            })
    
    # 2. 生成更新日期相关问题
    if "最终更新日" in content or "更新" in content:
        date_match = re.search(r'最终更新日[：:]\s*(\d{4}/\d{2}/\d{2})', content)
        if date_match:
            update_date = date_match.group(1)
            qa_pairs.append({
                "question": "数码宝贝卡牌对战综合规则的最新更新日期是什么时候？",
                "answer": f"最终更新日期为 {update_date}",
                "contexts": [clean_content],
                "ground_truth": update_date,
                "source": "dm",
                "category": "基础规则",
                "difficulty": "简单"
            })
    
    # 3. 生成游戏人数相关问题
    if "游戏人数" in content or "2 名玩家" in content:
        qa_pairs.append({
            "question": "数码宝贝卡牌对战由几名玩家进行？",
            "answer": "数码宝贝卡牌对战是由2名玩家进行对战的游戏。",
            "contexts": [clean_content],
            "ground_truth": "2名玩家",
            "source": "dm",
            "category": "游戏概要",
            "difficulty": "简单"
        })
    
    # 4. 生成目录/章节相关问题
    chapter_pattern = r'(\d+-\s*[^.]+?)\.\d+'
    chapters = re.findall(chapter_pattern, content)
    for chapter in chapters[:5]:  # 限制每个块最多提取5个章节
        chapter_name = chapter.strip()
        qa_pairs.append({
            "question": f"数码宝贝卡牌对战综合规则中「{chapter_name}」的内容是什么？",
            "answer": f"请参考综合规则中「{chapter_name}」章节的详细说明。",
            "contexts": [clean_content],
            "ground_truth": f"详见综合规则「{chapter_name}」章节",
            "source": "dm",
            "category": category,
            "difficulty": "中等"
        })
    
    # 5. 生成基于关键词的通用问题
    for template in DM_QUESTION_TEMPLATES:
        # 检查模板是否与内容相关
        keywords = re.findall(r'[\u4e00-\u9fff]{2,}', template)
        if any(kw in content for kw in keywords[:3]):
            # 从内容中找相关答案
            answer = extract_dm_answer(content, template)
            if answer:
                qa_pairs.append({
                    "question": template,
                    "answer": answer,
                    "contexts": [clean_content],
                    "ground_truth": answer,
                    "source": "dm",
                    "category": category,
                    "difficulty": get_difficulty(chunk, len(content))
                })
    
    return qa_pairs


def extract_dm_answer(content: str, question: str) -> Optional[str]:
    """
    从 DM 规则内容中提取问题答案
    
    Args:
        content: 规则内容
        question: 问题文本
        
    Returns:
        提取的答案文本，如果没有找到则返回 None
    """
    # 尝试从内容中找相关句子
    content_clean = clean_text(content)
    
    # 提取问题中的关键词
    keywords = [kw for kw in re.findall(r'[\u4e00-\u9fff]{2,}', question) 
                if len(kw) > 1 and kw not in ["什么", "如何", "哪些", "规则"]]
    
    if not keywords:
        return None
    
    # 找包含关键词的句子
    sentences = re.split(r'[。！？;；]', content_clean)
    for sentence in sentences:
        if any(kw in sentence for kw in keywords) and len(sentence) > 5:
            return sentence.strip() + "。"
    
    return None


# ==================== 数据集生成器 ====================

class TestDatasetGenerator:
    """
    测试数据集生成器
    
    职责：
    - 加载知识块数据
    - 生成问答对
    - 质量控制（去重、平衡分布）
    - 保存输出
    """
    
    def __init__(self, 
                 ocg_path: str = OCG_RULES_PATH,
                 dm_path: str = DM_RULES_PATH,
                 output_path: str = OUTPUT_PATH,
                 target_count: int = TARGET_COUNT):
        """
        初始化生成器
        
        Args:
            ocg_path: OCG 规则文件路径
            dm_path: DM 规则文件路径
            output_path: 输出文件路径
            target_count: 目标生成数量
        """
        self.ocg_path = ocg_path
        self.dm_path = dm_path
        self.output_path = output_path
        self.target_count = target_count
        
        # 数据存储
        self.ocg_chunks = []
        self.dm_chunks = []
        self.generated_qa = []
        
        # 统计信息
        self.stats = {
            "ocg_chunks_loaded": 0,
            "dm_chunks_loaded": 0,
            "qa_generated": 0,
            "qa_after_dedup": 0,
            "category_distribution": {},
            "difficulty_distribution": {},
            "source_distribution": {}
        }
    
    def load_data(self):
        """加载所有知识块数据"""
        print("正在加载 OCG 规则数据...")
        try:
            self.ocg_chunks = load_json_file(self.ocg_path)
            self.stats["ocg_chunks_loaded"] = len(self.ocg_chunks)
            print(f"  ✓ 加载 {len(self.ocg_chunks)} 条 OCG 规则块")
        except Exception as e:
            print(f"  ✗ OCG 数据加载失败: {e}")
            self.ocg_chunks = []
        
        print("正在加载 DM 规则数据...")
        try:
            self.dm_chunks = load_json_file(self.dm_path)
            self.stats["dm_chunks_loaded"] = len(self.dm_chunks)
            print(f"  ✓ 加载 {len(self.dm_chunks)} 条 DM 规则块")
        except Exception as e:
            print(f"  ✗ DM 数据加载失败: {e}")
            self.dm_chunks = []
    
    def generate_all(self):
        """从所有知识块生成问答对"""
        print("\n正在生成 OCG 问答对...")
        for chunk in self.ocg_chunks:
            qa_pairs = generate_ocg_qa(chunk)
            self.generated_qa.extend(qa_pairs)
        
        print(f"  ✓ 生成 {sum(1 for qa in self.generated_qa if qa['source'] == 'ocg')} 条 OCG 问答对")
        
        print("\n正在生成 DM 问答对...")
        for chunk in self.dm_chunks:
            qa_pairs = generate_dm_qa(chunk)
            self.generated_qa.extend(qa_pairs)
        
        print(f"  ✓ 生成 {sum(1 for qa in self.generated_qa if qa['source'] == 'dm')} 条 DM 问答对")
        
        self.stats["qa_generated"] = len(self.generated_qa)
    
    def deduplicate(self):
        """
        去除重复的问答对
        
        基于问题文本进行去重，保留最长的答案版本
        """
        print("\n正在去重...")
        seen_questions = {}
        
        for qa in self.generated_qa:
            q = qa["question"]
            if q not in seen_questions:
                seen_questions[q] = qa
            else:
                # 保留答案更长的版本（通常更详细）
                if len(qa["answer"]) > len(seen_questions[q]["answer"]):
                    seen_questions[q] = qa
        
        self.generated_qa = list(seen_questions.values())
        self.stats["qa_after_dedup"] = len(self.generated_qa)
        print(f"  ✓ 去重后剩余 {len(self.generated_qa)} 条问答对")
    
    def balance_distribution(self):
        """
        平衡数据集的类别和难度分布
        
        策略：
        1. 如果数量超过目标，按比例抽样保持分布
        2. 如果数量不足，通过模板变体补充
        """
        print("\n正在平衡数据分布...")
        
        if len(self.generated_qa) <= self.target_count:
            # 数量不足，通过复制和变体补充
            print(f"  当前数量 {len(self.generated_qa)} 少于目标 {self.target_count}，正在补充...")
            self._augment_data()
        else:
            # 数量超过，按比例抽样
            print(f"  当前数量 {len(self.generated_qa)} 超过目标 {self.target_count}，正在抽样...")
            self._sample_data()
        
        print(f"  ✓ 最终数据集大小: {len(self.generated_qa)} 条")
    
    def _augment_data(self):
        """通过模板变体扩充数据"""
        current_count = len(self.generated_qa)
        needed = self.target_count - current_count
        
        # 收集现有问答用于变体生成
        ocg_qa = [qa for qa in self.generated_qa if qa["source"] == "ocg"]
        dm_qa = [qa for qa in self.generated_qa if qa["source"] == "dm"]
        
        augmented = []
        
        # 从 OCG 问答生成变体
        if ocg_qa:
            for _ in range(needed // 2):
                original = random.choice(ocg_qa)
                variant = self._create_question_variant(original)
                if variant:
                    augmented.append(variant)
        
        # 从 DM 问答生成变体
        if dm_qa:
            for _ in range(needed - len(augmented)):
                original = random.choice(dm_qa)
                variant = self._create_question_variant(original)
                if variant:
                    augmented.append(variant)
        
        self.generated_qa.extend(augmented)
        print(f"  ✓ 扩充 {len(augmented)} 条变体问答对")
    
    def _create_question_variant(self, original_qa: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        创建问题的变体
        
        Args:
            original_qa: 原始问答对
            
        Returns:
            新的问答对，如果无法创建则返回 None
        """
        question = original_qa["question"]
        
        # 问题改写策略
        variants = []
        
        # 1. 添加限定词
        if not question.startswith("请问"):
            variants.append(f"请问{question}")
        
        # 2. 改变句式
        if "是什么" in question:
            variants.append(question.replace("是什么", "具体是怎样的"))
        elif "如何" in question:
            variants.append(question.replace("如何", "应该怎样"))
        elif "能否" in question:
            variants.append(question.replace("能否", "是否可以"))
        
        # 3. 添加语气词
        if not question.endswith("呢？"):
            variants.append(question.replace("？", "呢？"))
        
        if variants:
            variant_q = random.choice(variants)
            # 避免完全重复
            if variant_q != question and variant_q not in [qa["question"] for qa in self.generated_qa]:
                return {
                    **original_qa,
                    "question": variant_q,
                    "difficulty": self._adjust_difficulty(original_qa["difficulty"])
                }
        
        return None
    
    def _adjust_difficulty(self, current_difficulty: str) -> str:
        """微调难度等级"""
        adjustments = {
            "简单": random.choice(["简单", "中等"]),
            "中等": random.choice(["简单", "中等", "复杂"]),
            "复杂": random.choice(["中等", "复杂"])
        }
        return adjustments.get(current_difficulty, current_difficulty)
    
    def _sample_data(self):
        """
        分层抽样数据，确保类别、难度、来源分布均衡
        
        抽样策略：
        1. 先按来源分层（OCG/DM各占一定比例）
        2. 在每个来源内按类别分层
        3. 确保难度分布均匀（简单/中等/复杂各占约33%）
        """
        print("  使用分层抽样策略...")
        
        # 按来源分组
        by_source = {"ocg": [], "dm": []}
        for qa in self.generated_qa:
            source = qa.get("source", "ocg")
            if source in by_source:
                by_source[source].append(qa)
        
        # 目标：OCG和DM各占约50%（如果数据允许）
        target_per_source = self.target_count // 2
        
        sampled = []
        
        for source_name, source_items in by_source.items():
            if not source_items:
                continue
            
            target_count = min(target_per_source, len(source_items))
            
            # 在该来源内按类别分组
            by_category = {}
            for qa in source_items:
                cat = qa["category"]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(qa)
            
            # 按类别平均分配
            categories = list(by_category.keys())
            target_per_category = max(1, target_count // len(categories))
            
            source_sampled = []
            for cat, cat_items in by_category.items():
                count = min(target_per_category, len(cat_items))
                if count > 0:
                    source_sampled.extend(random.sample(cat_items, count))
            
            sampled.extend(source_sampled)
        
        # 如果抽样后仍不足，从各来源补充
        if len(sampled) < self.target_count:
            remaining = [qa for qa in self.generated_qa if qa not in sampled]
            if remaining:
                additional = random.sample(remaining, 
                                         min(self.target_count - len(sampled), len(remaining)))
                sampled.extend(additional)
        
        # 最终调整：确保难度分布更均衡
        sampled = self._balance_difficulty(sampled)
        
        self.generated_qa = sampled[:self.target_count]
    
    def _balance_difficulty(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        调整难度分布，使其更均衡
        
        策略：
        - 如果某难度级别数量不足目标值，从其他级别随机抽取并重新分配难度
        - 目标：简单/中等/复杂各占约33%
        
        Args:
            items: 问答对列表
            
        Returns:
            调整后的问答对列表
        """
        total = len(items)
        target_per_difficulty = total // 3
        
        # 按难度分组
        by_difficulty = {"简单": [], "中等": [], "复杂": []}
        for qa in items:
            diff = qa.get("difficulty", "中等")
            if diff in by_difficulty:
                by_difficulty[diff].append(qa)
            else:
                by_difficulty["中等"].append(qa)
        
        balanced = []
        used_qas = set()
        
        for difficulty in ["简单", "中等", "复杂"]:
            diff_items = by_difficulty[difficulty]
            
            if len(diff_items) >= target_per_difficulty:
                # 数量充足，直接抽样
                selected = random.sample(diff_items, target_per_difficulty)
                balanced.extend(selected)
                for qa in selected:
                    used_qas.add(id(qa))
            else:
                # 数量不足，全部使用并从其他级别补充
                balanced.extend(diff_items)
                for qa in diff_items:
                    used_qas.add(id(qa))
                
                # 需要从其他级别补充的数量
                remaining_target = target_per_difficulty - len(diff_items)
                
                # 收集可用的其他级别项目
                available = []
                for other_diff in ["简单", "中等", "复杂"]:
                    if other_diff != difficulty:
                        available.extend([qa for qa in by_difficulty[other_diff] if id(qa) not in used_qas])
                
                if available:
                    # 随机抽取并重新分配难度
                    to_reassign = random.sample(available, min(remaining_target, len(available)))
                    for qa in to_reassign:
                        # 创建副本并重新分配难度
                        qa_copy = {**qa, "difficulty": difficulty}
                        balanced.append(qa_copy)
                        used_qas.add(id(qa))
        
        # 确保数量正确（补充到目标数量）
        if len(balanced) < total:
            remaining = [qa for qa in items if id(qa) not in used_qas]
            if remaining:
                balanced.extend(remaining[:total - len(balanced)])
        
        return balanced[:total]
    
    def save_dataset(self):
        """保存数据集到 JSON 文件"""
        print(f"\n正在保存数据集到 {self.output_path}...")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(self.generated_qa, f, ensure_ascii=False, indent=2)
        
        file_size = os.path.getsize(self.output_path) / 1024  # KB
        print(f"  ✓ 数据集已保存 ({file_size:.1f} KB)")
    
    def calculate_stats(self):
        """计算并打印统计信息"""
        print("\n" + "="*60)
        print("📊 生成统计信息")
        print("="*60)
        
        # 基础统计
        print(f"\n📁 数据源加载:")
        print(f"  OCG 规则块: {self.stats['ocg_chunks_loaded']} 条")
        print(f"  DM 规则块:  {self.stats['dm_chunks_loaded']} 条")
        
        print(f"\n🔢 生成统计:")
        print(f"  原始生成:   {self.stats['qa_generated']} 条")
        print(f"  去重后:     {self.stats['qa_after_dedup']} 条")
        print(f"  最终数量:   {len(self.generated_qa)} 条")
        
        # 类别分布
        categories = Counter(qa["category"] for qa in self.generated_qa)
        print(f"\n📂 类别分布:")
        for cat, count in categories.most_common():
            pct = count / len(self.generated_qa) * 100
            bar = "█" * int(pct / 2)
            print(f"  {cat:12s}: {count:4d} ({pct:5.1f}%) {bar}")
        
        # 难度分布
        difficulties = Counter(qa["difficulty"] for qa in self.generated_qa)
        print(f"\n🎯 难度分布:")
        for diff in ["简单", "中等", "复杂"]:
            count = difficulties.get(diff, 0)
            pct = count / len(self.generated_qa) * 100
            bar = "█" * int(pct / 2)
            print(f"  {diff:6s}: {count:4d} ({pct:5.1f}%) {bar}")
        
        # 来源分布
        sources = Counter(qa["source"] for qa in self.generated_qa)
        print(f"\n📚 来源分布:")
        for src in ["ocg", "dm"]:
            count = sources.get(src, 0)
            pct = count / len(self.generated_qa) * 100
            bar = "█" * int(pct / 2)
            print(f"  {src.upper():4s}: {count:4d} ({pct:5.1f}%) {bar}")
        
        print("\n" + "="*60)
    
    def run(self):
        """
        运行完整的数据集生成流程
        
        流程：
        1. 加载数据
        2. 生成问答对
        3. 去重
        4. 平衡分布
        5. 保存数据集
        6. 打印统计信息
        """
        print("="*60)
        print("🚀 OCG/DM 规则问答测试数据集生成器")
        print("="*60)
        
        # 设置随机种子
        set_seed()
        
        # 1. 加载数据
        self.load_data()
        
        if not self.ocg_chunks and not self.dm_chunks:
            print("\n✗ 错误: 没有可用的数据源，程序退出")
            return
        
        # 2. 生成问答对
        self.generate_all()
        
        if not self.generated_qa:
            print("\n✗ 错误: 未能生成任何问答对，程序退出")
            return
        
        # 3. 去重
        self.deduplicate()
        
        # 4. 平衡分布
        self.balance_distribution()
        
        # 5. 保存数据集
        self.save_dataset()
        
        # 6. 打印统计信息
        self.calculate_stats()
        
        print("\n✅ 数据集生成完成！")
        print(f"📄 输出文件: {self.output_path}")


# ==================== 主程序入口 ====================

if __name__ == "__main__":
    # 创建生成器实例
    generator = TestDatasetGenerator(
        ocg_path=OCG_RULES_PATH,
        dm_path=DM_RULES_PATH,
        output_path=OUTPUT_PATH,
        target_count=TARGET_COUNT
    )
    
    # 运行生成流程
    generator.run()
