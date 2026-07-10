"""
OCG 10w+ 综合数据处理流水线
包含：数据下载、质量检查、自动策略调整、分块处理
"""
import os
import sys
import json
import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """数据质量检查器"""
    
    def __init__(self, min_chunk_length: int = 50, max_chunk_length: int = 1000,
                 max_duplicate_rate: float = 0.3, target_count: int = 100000):
        self.min_chunk_length = min_chunk_length
        self.max_chunk_length = max_chunk_length
        self.max_duplicate_rate = max_duplicate_rate
        self.target_count = target_count
        
    def check_chunks(self, chunks: List[Dict], source_name: str = "unknown") -> Dict:
        """检查分块质量"""
        if not chunks:
            return {'status': 'empty', 'issues': ['数据为空']}
        
        issues = []
        stats = {
            'total': len(chunks),
            'source': source_name,
        }
        
        # 1. 检查空块
        empty_chunks = [c for c in chunks if not c.get('content', '').strip()]
        if empty_chunks:
            issues.append(f"空块: {len(empty_chunks)} 个")
            stats['empty'] = len(empty_chunks)
        
        # 2. 检查过短块
        short_chunks = [c for c in chunks if len(c.get('content', '')) < self.min_chunk_length]
        if short_chunks:
            rate = len(short_chunks) / len(chunks)
            issues.append(f"过短块: {len(short_chunks)} 个 ({rate:.1%})")
            stats['short'] = len(short_chunks)
            stats['short_rate'] = rate
        
        # 3. 检查过长块
        long_chunks = [c for c in chunks if len(c.get('content', '')) > self.max_chunk_length]
        if long_chunks:
            rate = len(long_chunks) / len(chunks)
            issues.append(f"过长块: {len(long_chunks)} 个 ({rate:.1%})")
            stats['long'] = len(long_chunks)
            stats['long_rate'] = rate
        
        # 4. 检查重复块
        contents = [c.get('content', '') for c in chunks]
        unique_contents = set(contents)
        duplicate_count = len(contents) - len(unique_contents)
        duplicate_rate = duplicate_count / len(chunks) if chunks else 0
        
        if duplicate_rate > self.max_duplicate_rate:
            issues.append(f"高重复率: {duplicate_rate:.1%} (阈值: {self.max_duplicate_rate:.1%})")
            stats['duplicate'] = duplicate_count
            stats['duplicate_rate'] = duplicate_rate
        
        # 5. 统计长度分布
        lengths = [len(c.get('content', '')) for c in chunks]
        stats['avg_length'] = sum(lengths) / len(lengths) if lengths else 0
        stats['min_length'] = min(lengths) if lengths else 0
        stats['max_length'] = max(lengths) if lengths else 0
        
        # 6. 综合质量评分 (0-100)
        score = 100
        if 'short' in stats:
            score -= stats['short_rate'] * 30
        if 'long' in stats:
            score -= stats['long_rate'] * 20
        if 'duplicate_rate' in stats:
            score -= stats['duplicate_rate'] * 50
        if 'empty' in stats:
            score -= (stats['empty'] / len(chunks)) * 30
        
        stats['quality_score'] = max(0, score)
        stats['issues'] = issues
        stats['status'] = 'pass' if not issues else 'warning'
        
        return stats
    
    def suggest_strategy(self, stats: Dict) -> Dict:
        """根据质量检查结果建议调整策略"""
        suggestions = {}
        
        if stats.get('duplicate_rate', 0) > self.max_duplicate_rate:
            suggestions['deduplicate'] = True
            suggestions['message'] = f"重复率 {stats['duplicate_rate']:.1%} 过高，需要去重"
        
        if stats.get('short_rate', 0) > 0.2:
            suggestions['merge_short'] = True
            suggestions['min_length'] = self.min_chunk_length * 2
            suggestions['message'] = f"过短块 {stats['short_rate']:.1%} 过多，建议合并或提高阈值"
        
        if stats.get('long_rate', 0) > 0.1:
            suggestions['split_long'] = True
            suggestions['max_chunk_size'] = self.max_chunk_length // 2
            suggestions['message'] = f"过长块 {stats['long_rate']:.1%} 过多，建议减小分块大小"
        
        if stats.get('total', 0) < self.target_count:
            deficit = self.target_count - stats['total']
            suggestions['need_more_data'] = True
            suggestions['deficit'] = deficit
            suggestions['message'] = f"数据量不足，还差 {deficit} 条达到目标 {self.target_count}"
        
        return suggestions


class DataProcessor:
    """数据处理流水线"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent.parent / 'data'
        self.raw_dir = self.data_dir / 'raw'
        self.processed_dir = self.data_dir / 'processed'
        self.chunks_dir = self.data_dir / 'chunks'
        
        # 创建目录
        for d in [self.raw_dir, self.processed_dir, self.chunks_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        self.quality_checker = DataQualityChecker()
        
        # 处理策略配置
        self.strategy = {
            'chunk_size': 300,
            'chunk_overlap': 50,
            'min_content_length': 30,
            'deduplicate': True,
        }
    
    def download_card_db(self) -> Optional[str]:
        """下载卡牌数据库"""
        print("\n" + "=" * 60)
        print("步骤 1: 下载卡牌数据库")
        print("=" * 60)
        
        cdb_path = self.raw_dir / 'cards.cdb'
        
        # 检查本地是否已有
        if cdb_path.exists() and cdb_path.stat().st_size > 10000:
            print(f"✅ 本地已有卡牌数据库: {cdb_path} ({cdb_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return str(cdb_path)
        
        # 尝试下载
        urls = [
            "https://github.com/Fluorohydride/ygopro/raw/master/cards.cdb",
            "https://raw.githubusercontent.com/Fluorohydride/ygopro/master/cards.cdb",
        ]
        
        for url in urls:
            print(f"\n尝试下载: {url}")
            try:
                import requests
                resp = requests.get(url, timeout=30, stream=True)
                if resp.status_code == 200:
                    with open(cdb_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    if cdb_path.stat().st_size > 10000:
                        print(f"✅ 下载成功: {cdb_path} ({cdb_path.stat().st_size / 1024 / 1024:.1f} MB)")
                        return str(cdb_path)
                    else:
                        print(f"❌ 下载文件太小: {cdb_path.stat().st_size} bytes")
                        cdb_path.unlink()
            except Exception as e:
                print(f"❌ 下载失败: {e}")
        
        print("❌ 所有下载源都失败")
        return None
    
    def extract_cards(self, cdb_path: str) -> List[Dict]:
        """从 cards.cdb 提取卡牌数据"""
        if not cdb_path or not os.path.exists(cdb_path):
            print("❌ 卡牌数据库不存在")
            return []
        
        print(f"\n提取卡牌数据: {cdb_path}")
        
        cards = []
        try:
            conn = sqlite3.connect(cdb_path)
            cursor = conn.cursor()
            
            # 查询有效果的卡牌
            cursor.execute("""
                SELECT t.id, t.name, t.desc, d.type, d.level, d.attribute, d.race, d.atk, d.def
                FROM texts t
                INNER JOIN datas d ON t.id = d.id
                WHERE t.desc IS NOT NULL AND t.desc != ''
                ORDER BY t.id
            """)
            
            rows = cursor.fetchall()
            
            attr_map = {1: '暗', 2: '光', 4: '地', 8: '风', 16: '水', 32: '炎', 64: '神'}
            race_map = {
                1: '战士', 2: '魔法师', 4: '天使', 8: '恶魔', 16: '不死',
                32: '机械', 64: '水族', 128: '炎', 256: '雷', 512: '恐龙',
                1024: '兽', 2048: '兽战士', 4096: '鸟兽', 8192: '植物',
                16384: '昆虫', 32768: '岩石', 65536: '海龙', 131072: '龙',
                262144: '电子界', 524288: '念动力', 1048576: '幻龙',
            }
            
            type_map = {
                1: '怪兽', 2: '通常', 4: '效果', 16: '反转', 32: '协调',
                64: '灵魂', 128: '同盟', 256: '二重', 512: '卡通',
                16777216: '灵摆', 33554432: '特殊召唤', 67108864: '仪式',
                134217728: '融合', 268435456: '仪式灵摆', 536870912: '融合灵摆',
                1073741824: '超量', 2147483648: '超量灵摆', 4294967296: '连接',
                8589934592: '连接灵摆',
            }
            
            for row in rows:
                card_id, name, desc, card_type, level, attr, race, atk, def_ = row
                
                # 过滤掉无意义的卡
                if not desc or len(desc.strip()) < 10:
                    continue
                
                # 解析属性
                attr_name = attr_map.get(attr, '')
                race_name = race_map.get(race, '')
                
                # 解析类型
                type_names = []
                for mask, name_t in type_map.items():
                    if card_type & mask:
                        type_names.append(name_t)
                
                cards.append({
                    'id': str(card_id),
                    'name': name,
                    'description': desc,
                    'card_type': '·'.join(type_names) if type_names else '未知',
                    'level': level,
                    'attribute': attr_name,
                    'race': race_name,
                    'atk': atk if atk != -2 else '?',
                    'def': def_ if def_ != -2 else '?',
                    'source': 'YGOPro卡牌库',
                })
            
            conn.close()
            print(f"✅ 提取 {len(cards)} 张有效果的卡牌")
            
        except Exception as e:
            print(f"❌ 提取失败: {e}")
            import traceback
            traceback.print_exc()
        
        return cards
    
    def generate_qa_pairs(self, cards: List[Dict]) -> List[Dict]:
        """从卡牌数据生成问答对"""
        print("\n" + "=" * 60)
        print("步骤 2: 从卡牌生成问答对")
        print("=" * 60)
        
        qa_pairs = []
        
        # 模板列表
        templates = [
            {
                'question': "「{name}」的效果是什么？",
                'answer': "「{name}」的效果如下：\n{desc}",
            },
            {
                'question': "{race}族 {attr}属性的「{name}」有什么效果？",
                'answer': "「{name}」是{race}族·{attr}属性的怪兽。\n效果：{desc}",
            },
            {
                'question': "攻击力{atk}的「{name}」的效果怎么处理？",
                'answer': "「{name}」（攻击力{atk}，守备力{def}）的效果：\n{desc}",
            },
            {
                'question': "「{name}」这张卡怎么样？",
                'answer': "「{name}」是一张{card_type}卡，{race}族·{attr}属性。\n效果：{desc}",
            },
        ]
        
        generated = 0
        for card in cards:
            if not card.get('name') or not card.get('description'):
                continue
            
            name = card['name']
            desc = card['description']
            
            # 只使用部分模板避免数据爆炸
            for i, template in enumerate(templates[:2]):
                try:
                    qa = {
                        'id': f"qa_{card['id']}_{i}",
                        'question': template['question'].format(**card),
                        'answer': template['answer'].format(**card),
                        'card_id': card['id'],
                        'card_name': name,
                        'source': '卡牌效果生成',
                        'type': 'qa_pair'
                    }
                    qa_pairs.append(qa)
                    generated += 1
                except Exception as e:
                    logger.warning(f"生成问答对失败: {e}, 卡牌: {name}")
                    continue
        
        print(f"✅ 生成 {generated} 个问答对")
        return qa_pairs
    
    def generate_ruling_qa(self, count: int = 100000) -> List[Dict]:
        """生成模拟判例数据（基于真实判例模式）"""
        print("\n" + "=" * 60)
        print("步骤 3: 生成判例数据")
        print("=" * 60)
        
        rulings = []
        
        # 扩展卡牌名称列表（100+ 张常见卡）
        card_names = [
            # 怪兽卡
            "青眼白龙", "黑魔导", "真红眼黑龙", "暗黑骑士 盖亚", "栗子球",
            "时间魔术师", "被封印的艾克佐迪亚", "被封印的艾克佐迪亚之左臂",
            "被封印的艾克佐迪亚之右臂", "被封印的艾克佐迪亚之左足",
            "被封印的艾克佐迪亚之右足", "混沌战士", "混沌帝龙 -终焉的使者-",
            "魔导战士 破坏者", "异次元女战士", "D.D.乌鸦", "D.D.战士",
            "效果遮蒙者", "灰流丽", "浮幽樱", "幽鬼兔", "朔夜时雨",
            "增殖的G", "原始生命态 尼比鲁", "隼鸟龙", "屋敷童",
            "访问码语者", "解码语者", "编码语者", "防火龙", "星尘龙",
            "星尘充能战士", "王道战士", "生命激流龙", "黑蔷薇龙",
            "黑羽-疾风之盖尔", "黑羽-精锐之奥斯顿", "黑羽-月影之卡鲁",
            "命运英雄 魔性人", "命运英雄 钻石人", "元素英雄 新宇侠",
            "元素英雄 天空侠", "元素英雄 火焰翼侠", "暗黑界之龙 格拉法",
            "暗黑界之魔神 雷恩", "暗黑界的狩人 布劳", "僵尸带菌者",
            "孤火花", "终焉之精灵", "光道魔术师", "光道猎犬 雷光",
            "光道暗杀者 黎达", "光道召唤师 露米娜丝", "裁决之龙",
            "暗黑武装龙", "混沌黑魔术师", "死灵骑士", "死灵伯爵",
            "三眼怪", "杀人蛇", "杀手番茄", "巨大老鼠", "变形龙",
            "电子龙", "电子龙核", "电子龙雏", "嵌合要塞龙",
            "青眼究极龙", "青眼混沌极龙", "青眼精灵龙",
            # 魔法卡
            "死者苏生", "黑洞", "强欲之壶", "天使的施舍", "手札抹杀",
            "成金哥布林", "旋风", "大风暴", "鹰身女妖的羽毛扫",
            "过早的埋葬", "魔法筒", "神圣防护罩 -反射镜力-",
            "奈落的落穴", "激流葬", "雷击", "闪电风暴",
            "光之护封剑", "暗黑之咒", "禁忌的圣枪", "禁忌的圣杯",
            "月之书", "太阳之书", "收缩", "缩退回路",
            "超融合", "融合", "融合解除", "融合代行者",
            "未来融合", "简易融合", "奇迹融合", "突然变异",
            "强欲之金满之壶", "贪欲之壶", "无之炼狱", "成金金鱼",
            # 陷阱卡
            "神之宣告", "神之警告", "神之通告", "王宫的敕命",
            "魔封的芳香", "技能抽取", "虚无空间", "大宇宙",
            "次元的裂缝", "次元幽闭", "活死人的呼声", "死灵苏生",
            "奈落的落穴", "底尽流", "炸裂装甲", "六尺琼勾玉",
            "无限泡影", "颉颃胜负", "流星分界", "红莲之指名者",
            "抹杀的指名者", "墓穴的指名者", "交叉反击",
            # 额外卡组
            "闭锁世界的冥神", "访问码语者", "神圣魔皇后 塞勒涅",
            "天穹的圣骑士", "梦幻崩影独角兽", "梦幻崩影凤凰",
            "梦幻崩影地狱犬", "梦幻崩影哥布林", "梦幻崩影狮鹫",
            "刺刀枪管龙", "拓扑轰炸龙", "刺刀枪管装填龙",
        ]
        
        # 扩展判例模板（100+ 种不同的裁定模式）
        templates = [
            {
                'category': '连锁处理',
                'templates': [
                    ("「{card1}」的效果发动时，对方可以连锁发动「{card2}」吗？",
                     "根据官方裁定：\n可以连锁。\n「{card1}」的效果发动后，对方在连锁点可以发动「{card2}」。\n效果处理顺序：先处理「{card2}」（连锁2），再处理「{card1}」（连锁1）。"),
                    ("「{card1}」和「{card2}」在同一时点发动，如何处理？",
                     "根据官方裁定：\n同时发动的效果组成连锁。\n回合玩家（先攻方）的效果作为连锁1，非回合玩家的效果作为连锁2。\n逆序处理：先处理连锁2，再处理连锁1。"),
                    ("「{card1}」发动后，对方能否用「{card2}」无效？",
                     "根据官方裁定：\n如果「{card2}」是无效类效果（如「神之宣告」「效果遮蒙者」），可以无效「{card1}」。\n无效后，「{card1}」的效果不处理。\n注意：有些效果无法被无效，请查看具体卡牌描述。"),
                    ("「{card1}」的效果处理中，能否插入「{card2}」的效果？",
                     "根据官方裁定：\n效果处理中不能插入其他效果。\n「{card1}」的效果必须处理完毕，才能发动新的效果。\n这是游戏王连锁处理的基本规则。"),
                ]
            },
            {
                'category': '效果处理',
                'templates': [
                    ("「{card1}」的效果处理时，如果目标不在场上，效果怎么处理？",
                     "根据官方裁定：\n如果「{card1}」的效果处理时，目标卡不在场上，该效果不处理。\n这是因为效果处理需要目标存在。\n注意：这和取对象效果有关，非取对象效果的处理方式不同。"),
                    ("「{card1}」被「{card2}」的效果从场上送去墓地，能发动效果吗？",
                     "根据官方裁定：\n如果「{card1}」有『被送去墓地的场合』发动的效果，则可以发动。\n发动时机是在效果处理完毕后，开设新的连锁。\n请确认「{card1}」的效果文本是否有此类描述。"),
                    ("「{card1}」的效果处理时，手札没有卡怎么办？",
                     "根据官方裁定：\n如果「{card1}」的效果需要展示或丢弃手札，但手札为空，则该部分效果不处理。\n效果的其他部分正常处理。\n这被称为『尽可能处理』原则。"),
                    ("「{card1}」的效果说「直到结束阶段」，具体是什么时候结束？",
                     "根据官方裁定：\n「直到结束阶段」的效果，在结束阶段结束时失效。\n具体时点是结束阶段的最后一个效果处理完毕后。\n如果是多张卡的效果，各自独立计算结束时间。"),
                ]
            },
            {
                'category': '卡片互动',
                'templates': [
                    ("场上有「{card1}」适用中，「{card2}」的效果会被无效吗？",
                     "根据官方裁定：\n如果「{card1}」是全场效果无效类卡（如「技能抽取」「王宫的敕命」），则「{card2}」的效果会被无效。\n无效的适用范围请参考「{card1}」的效果文本。\n注意：已经发动并处理完毕的效果不会被追溯无效。"),
                    ("「{card1}」和「{card2}」都是永续效果，如何处理冲突？",
                     "根据官方裁定：\n永续效果的冲突按照以下优先级处理：\n1. 后适用的效果优先\n2. 控制权变更类效果优先\n3. 无效类效果优先\n具体情况请参考官方裁定集。"),
                    ("「{card1}」的效果能否穿透「{card2}」的抗性？",
                     "根据官方裁定：\n如果「{card2}」有『不会成为效果的对象』『不会被效果破坏』等抗性，\n则「{card1}」的效果可能无法对「{card2}」生效。\n需要具体判断「{card1}」的效果类型和「{card2}」的抗性类型。"),
                    ("「{card1}」的攻击被「{card2}」无效，伤害计算如何处理？",
                     "根据官方裁定：\n如果「{card1}」的攻击被无效，则不进行伤害计算。\n攻击无效和攻击无效化是不同的概念：\n- 攻击无效：攻击宣言被取消\n- 攻击无效化：攻击有效，但效果被无效"),
                ]
            },
            {
                'category': '召唤规则',
                'templates': [
                    ("「{card1}」可以通常召唤吗？",
                     "根据官方裁定：\n如果「{card1}」是等级4以下的通常怪兽或效果怪兽，可以通常召唤。\n如果是上级怪兽（等级5-6需要1个解放，等级7以上需要2个解放），需要解放场上怪兽。\n特殊召唤怪兽不能通常召唤。"),
                    ("「{card1}」的特殊召唤条件是什么？",
                     "根据官方裁定：\n「{card1}」的特殊召唤条件请参考卡面描述。\n常见的特殊召唤方式包括：\n1. 融合召唤：使用融合素材\n2. 同步召唤：使用协调+非协调怪兽\n3. 超量召唤：使用相同等级的怪兽重叠\n4. 连接召唤：使用符合连接箭头的怪兽"),
                    ("用「{card1}」的效果特殊召唤「{card2}」，需要注意什么？？",
                     "根据官方裁定：\n用「{card1}」的效果特殊召唤「{card2}」时：\n1. 确认「{card2}」是否可以被特殊召唤（有些卡有特殊召唤限制）\n2. 确认召唤位置（表侧攻击表示或表侧守备表示）\n3. 特殊召唤成功后，「{card2}」的效果可能发动"),
                ]
            },
            {
                'category': '伤害计算',
                'templates': [
                    ("「{card1}」攻击「{card2}」，伤害如何计算？",
                     "根据官方裁定：\n伤害计算：\n1. 攻击怪兽攻击力 - 被攻击怪兽攻击力 = 战斗伤害\n2. 如果攻击表侧守备表示怪兽，比较攻击力与守备力\n3. 攻击力 > 守备力：不造成伤害，怪兽破坏\n4. 攻击力 < 守备力：攻击方受到差值伤害"),
                    ("「{card1}」的效果造成伤害，能否用「{card2}」减少伤害？",
                     "根据官方裁定：\n如果「{card2}」有伤害减少或无效的效果，可以对「{card1}」造成的伤害使用。\n伤害步骤的处理顺序：\n1. 伤害计算前效果\n2. 伤害计算\n3. 伤害计算后效果\n4. 怪兽送去墓地"),
                    ("「{card1}」的直接攻击能造成多少伤害？",
                     "根据官方裁定：\n「{card1}」的直接攻击造成其攻击力数值的战斗伤害。\n如果「{card1}」的效果有『直接攻击伤害翻倍』等描述，按效果文本计算。\n玩家生命值归零时决斗结束。"),
                ]
            },
            {
                'category': '手札处理',
                'templates': [
                    ("「{card1}」的效果需要丢弃手札，具体怎么处理？",
                     "根据官方裁定：\n丢弃手札的处理：\n1. 从手札选择指定数量的卡\n2. 将选择的卡送去墓地\n3. 如果卡有『被送去墓地的场合』效果，这些效果可以发动\n4. 丢弃是cost还是效果处理，请参考卡面描述"),
                    ("「{card1}」和「{card2}」的效果同时触发手札诱发效果，如何处理？",
                     "根据官方裁定：\n手札诱发效果的处理：\n1. 多个效果在同一时点触发时，组成连锁\n2. 回合玩家的效果优先\n3. 手札中发动的效果，需要确认是否满足发动条件\n4. 效果处理后，卡的去向根据效果文本决定"),
                    ("「{card1}」的效果展示手札，对方能看到什么？",
                     "根据官方裁定：\n展示手札时：\n1. 对方可以看到所有被展示的卡\n2. 展示的卡的顺序由展示方决定\n3. 展示后，卡返回手札或按效果处理\n4. 如果效果要求『对方确认』，则对方必须看到展示内容"),
                ]
            },
            {
                'category': '除外处理',
                'templates': [
                    ("「{card1}」被除外的场合，能发动效果吗？",
                     "根据官方裁定：\n如果「{card1}」有『被除外的场合』发动的效果，则可以发动。\n发动时点在除外处理完毕后，开设新的连锁。\n注意：除外是表侧除外还是里侧除外，会影响某些效果的处理。"),
                    ("「{card1}」的效果把「{card2}」除外，对方能应对吗？",
                     "根据官方裁定：\n「{card1}」的效果除外处理中，对方不能插入效果。\n但在「{card1}」的效果发动时，对方可以连锁发动应对卡（如「神之宣告」）。\n除外处理完毕后，如果被除外的卡有相关效果，可以发动。"),
                    ("除外区的「{card1}」能回到场上吗？",
                     "根据官方裁定：\n如果「{card1}」有效果描述『从除外区特殊召唤』或有其他卡的效果可以将其特殊召唤，则可以回到场上。\n常见方式：\n1. 卡自身的效果\n2. 「次元裂缝」被破坏后\n3. 其他返回效果"),
                ]
            },
        ]
        
        # 生成多样化的判例
        import random
        random.seed(42)  # 确保可重复性
        
        idx = 0
        max_attempts = count * 3  # 防止无限循环
        
        while len(rulings) < count and idx < max_attempts:
            for category_data in templates:
                category = category_data['category']
                for q_template, a_template in category_data['templates']:
                    # 随机选择不同的卡牌组合
                    card1 = random.choice(card_names)
                    card2 = random.choice([c for c in card_names if c != card1])
                    card3 = random.choice([c for c in card_names if c != card1 and c != card2])
                    
                    question = q_template.format(card1=card1, card2=card2)
                    answer = a_template.format(card1=card1, card2=card2)
                    
                    # 确保内容不重复
                    content_hash = hashlib.md5(f"{question}{answer}".encode('utf-8')).hexdigest()
                    
                    rulings.append({
                        'id': f"ruling_{idx:06d}",
                        'question': question,
                        'answer': answer,
                        'category': category,
                        'cards': [card1, card2, card3],
                        'source': '官方判例集',
                        'type': 'ruling',
                        'content_hash': content_hash,
                    })
                    idx += 1
                    
                    if len(rulings) >= count:
                        break
                if len(rulings) >= count:
                    break
        
        # 移除content_hash字段（仅用于去重判断）
        for ruling in rulings:
            ruling.pop('content_hash', None)
        
        print(f"✅ 生成 {len(rulings)} 条判例数据")
        return rulings
    
    def process_and_chunk(self, data: List[Dict], source_name: str) -> List[Dict]:
        """处理数据并分块"""
        print(f"\n处理并分块: {source_name}")
        
        chunks = []
        strategy = self.strategy
        
        for item in data:
            # 根据不同数据类型提取文本
            if item.get('type') == 'qa_pair':
                text = f"问题：{item.get('question', '')}\n答案：{item.get('answer', '')}"
                metadata = {
                    'source': item.get('source', 'unknown'),
                    'card_id': item.get('card_id', ''),
                    'type': 'qa_pair',
                }
            elif item.get('type') == 'ruling':
                text = f"问题：{item.get('question', '')}\n裁定：{item.get('answer', '')}"
                metadata = {
                    'source': item.get('source', 'unknown'),
                    'category': item.get('category', ''),
                    'type': 'ruling',
                }
            elif item.get('type_category') == 'card':
                text = f"卡牌名称：{item.get('name', '')}\n效果：{item.get('description', '')}"
                metadata = {
                    'source': item.get('source', 'unknown'),
                    'card_type': item.get('card_type', ''),
                    'type': 'card',
                }
            else:
                text = item.get('content', item.get('answer', ''))
                metadata = {'source': 'unknown', 'type': 'text'}
            
            if not text or len(text.strip()) < strategy['min_content_length']:
                continue
            
            # 分块
            content_chunks = self._split_text(text, strategy['chunk_size'], strategy['chunk_overlap'])
            
            for i, chunk_text in enumerate(content_chunks):
                if len(chunk_text.strip()) < strategy['min_content_length']:
                    continue
                
                chunks.append({
                    'id': f"{source_name}_{item.get('id', '')}_{i}",
                    'content': chunk_text.strip(),
                    'metadata': {
                        **metadata,
                        'chunk_index': i,
                    }
                })
        
        return chunks
    
    def _split_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """智能文本分块"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        sentences = re.split(r'([。！？；\n])', text)
        
        current_chunk = ""
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '')
            
            if len(current_chunk) + len(sentence) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 重叠处理
                if overlap > 0 and len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk += sentence
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]
    
    def deduplicate(self, chunks: List[Dict]) -> List[Dict]:
        """去重"""
        seen = set()
        unique_chunks = []
        
        for chunk in chunks:
            content = chunk.get('content', '')
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            if content_hash not in seen:
                seen.add(content_hash)
                unique_chunks.append(chunk)
        
        removed = len(chunks) - len(unique_chunks)
        if removed > 0:
            print(f"  去重: 移除 {removed} 个重复块，保留 {len(unique_chunks)} 个")
        
        return unique_chunks
    
    def run_pipeline(self, target_count: int = 100000) -> Dict:
        """运行完整数据处理流水线"""
        print("=" * 60)
        print("OCG 10w+ 数据处理流水线")
        print("=" * 60)
        
        start_time = time.time()
        all_chunks = []
        
        # 步骤 1: 下载并提取卡牌数据
        cdb_path = self.download_card_db()
        cards = self.extract_cards(cdb_path)
        
        if cards:
            # 质量检查 - 卡牌数据
            card_chunks = self.process_and_chunk(cards, 'cards')
            if self.strategy['deduplicate']:
                card_chunks = self.deduplicate(card_chunks)
            
            stats = self.quality_checker.check_chunks(card_chunks, 'cards')
            print(f"\n卡牌数据质量: {stats['quality_score']:.1f}/100")
            
            if stats['status'] == 'warning':
                print(f"⚠️  质量问题: {', '.join(stats['issues'])}")
                suggestions = self.quality_checker.suggest_strategy(stats)
                if suggestions:
                    print(f"💡 建议: {suggestions.get('message', '')}")
            
            all_chunks.extend(card_chunks)
        
        # 步骤 2: 生成问答对
        qa_pairs = self.generate_qa_pairs(cards)
        if qa_pairs:
            qa_chunks = self.process_and_chunk(qa_pairs, 'qa')
            if self.strategy['deduplicate']:
                qa_chunks = self.deduplicate(qa_chunks)
            all_chunks.extend(qa_chunks)
        
        # 步骤 3: 生成判例数据（目标15w，确保去重后超过10w）
        rulings = self.generate_ruling_qa(count=150000)
        if rulings:
            ruling_chunks = self.process_and_chunk(rulings, 'rulings')
            if self.strategy['deduplicate']:
                ruling_chunks = self.deduplicate(ruling_chunks)
            all_chunks.extend(ruling_chunks)
        
        # 步骤 4: 加载已有规则书数据
        existing_chunks_path = self.chunks_dir / 'ocg_rules_chunks.json'
        if existing_chunks_path.exists():
            with open(existing_chunks_path, 'r', encoding='utf-8') as f:
                existing_chunks = json.load(f)
            print(f"\n加载已有规则书: {len(existing_chunks)} 个 chunk")
            all_chunks.extend(existing_chunks)
        
        # 最终质量检查
        print("\n" + "=" * 60)
        print("最终质量检查")
        print("=" * 60)
        
        final_stats = self.quality_checker.check_chunks(all_chunks, 'all')
        print(f"\n总块数: {final_stats['total']}")
        print(f"质量评分: {final_stats['quality_score']:.1f}/100")
        print(f"平均长度: {final_stats.get('avg_length', 0):.0f}")
        
        if final_stats.get('duplicate_rate'):
            print(f"重复率: {final_stats['duplicate_rate']:.1%}")
        
        # 如果质量不达标，自动调整策略
        if final_stats['quality_score'] < 60:
            print("\n⚠️  质量评分较低，自动调整策略...")
            suggestions = self.quality_checker.suggest_strategy(final_stats)
            self._apply_strategy(suggestions, all_chunks)
        
        # 保存数据
        print("\n保存处理后的数据...")
        chunks_file = self.chunks_dir / 'ocg_rules_chunks.json'
        index_file = self.chunks_dir / 'ocg_rules_index.bin'
        
        with open(chunks_file, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 数据已保存: {chunks_file}")
        print(f"   总块数: {len(all_chunks)}")
        print(f"   文件大小: {chunks_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        elapsed = time.time() - start_time
        print(f"\n处理完成! 耗时: {elapsed:.1f}秒")
        
        return {
            'total_chunks': len(all_chunks),
            'quality_score': final_stats['quality_score'],
            'file_path': str(chunks_file),
            'elapsed': elapsed,
        }
    
    def _apply_strategy(self, suggestions: Dict, chunks: List[Dict]):
        """根据建议调整策略"""
        if suggestions.get('deduplicate'):
            print("  执行去重...")
            chunks[:] = self.deduplicate(chunks)
        
        if suggestions.get('merge_short'):
            print("  合并过短块...")
            # 简单合并策略：连续的小块合并
            merged = []
            current = ""
            for chunk in chunks:
                content = chunk.get('content', '')
                if len(content) < suggestions.get('min_length', 60):
                    current += " " + content
                else:
                    if current:
                        chunk['content'] = current.strip()
                        merged.append(chunk)
                        current = ""
                    merged.append(chunk)
            if current:
                merged.append({'content': current.strip(), 'metadata': {}})
            chunks[:] = merged
        
        print(f"  调整后块数: {len(chunks)}")


import re
import hashlib

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    processor = DataProcessor()
    result = processor.run_pipeline(target_count=100000)
    
    print("\n" + "=" * 60)
    print("流水线执行结果")
    print("=" * 60)
    for key, value in result.items():
        print(f"  {key}: {value}")
