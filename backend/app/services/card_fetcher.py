"""
卡片信息自动抓取器
实现从多个数据源自动抓取最新卡片信息
"""
import logging
import json
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from app.services.data_source_manager import get_data_source_manager, DataSource

logger = logging.getLogger(__name__)


@dataclass
class CardInfo:
    """卡片信息"""
    card_id: str
    name: str
    type: str
    attribute: Optional[str] = None
    level: Optional[int] = None
    pendulum_scale: Optional[int] = None
    link_rating: Optional[int] = None
    atk: Optional[int] = None
    def_: Optional[int] = None
    effect_text: str = ""
    pendulum_text: str = ""
    card_sets: List[Dict[str, str]] = field(default_factory=list)
    banlist_info: Optional[Dict[str, str]] = None
    image_url: Optional[str] = None
    source: str = ""
    last_updated: datetime = field(default_factory=datetime.now)
    checksum: str = ""  # 用于检测变更


@dataclass
class FetchResult:
    """抓取结果"""
    success: bool
    source: str
    cards_fetched: int = 0
    cards_updated: int = 0
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CardFetcher:
    """卡片信息抓取器"""
    
    def __init__(self):
        self.source_manager = get_data_source_manager()
        self.cache: Dict[str, CardInfo] = {}
        logger.info("CardFetcher initialized")
    
    def fetch_all_cards(self, source_id: Optional[str] = None) -> FetchResult:
        """
        抓取所有卡片信息
        
        Args:
            source_id: 指定数据源ID，为None则使用最佳数据源
            
        Returns:
            FetchResult对象
        """
        import time
        start_time = time.time()
        
        result = FetchResult(success=False, source="", duration=0)
        
        try:
            # 获取数据源
            if source_id:
                source = self.source_manager.get_source(source_id)
            else:
                source = self.source_manager.get_best_source()
            
            if not source:
                result.errors.append("No available data source")
                return result
            
            result.source = source.id
            logger.info(f"Fetching cards from {source.name}")
            
            # 根据数据源调用对应的抓取方法
            if 'ygoprodeck' in source.url:
                cards = self._fetch_from_ygoprodeck(source)
            elif 'yugipedia' in source.url:
                cards = self._fetch_from_yugipedia(source)
            else:
                cards = self._fetch_from_generic(source)
            
            # 处理抓取到的卡片
            updated_count = 0
            for card in cards:
                if self._update_card(card):
                    updated_count += 1
            
            result.success = True
            result.cards_fetched = len(cards)
            result.cards_updated = updated_count
            result.duration = time.time() - start_time
            
            logger.info(f"Fetch completed: {len(cards)} cards, {updated_count} updated")
            
        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Fetch failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def _fetch_from_ygoprodeck(self, source: DataSource) -> List[CardInfo]:
        """从YGOPRODeck抓取"""
        import requests
        
        cards = []
        
        try:
            response = requests.get(source.url, timeout=source.timeout)
            response.raise_for_status()
            data = response.json()
            
            # YGOPRODeck返回格式
            card_list = data if isinstance(data, list) else data.get('data', [])
            
            for card_data in card_list:
                card = self._parse_ygoprodeck_card(card_data, source.id)
                if card:
                    cards.append(card)
            
        except Exception as e:
            logger.error(f"YGOPRODeck fetch error: {e}")
        
        return cards
    
    def _fetch_from_yugipedia(self, source: DataSource) -> List[CardInfo]:
        """从Yugipedia抓取"""
        # Yugipedia使用MediaWiki API，简化实现
        cards = []
        
        # 实际需要实现更复杂的API调用
        logger.info("Yugipedia fetch not fully implemented")
        
        return cards
    
    def _fetch_from_generic(self, source: DataSource) -> List[CardInfo]:
        """通用抓取方法"""
        cards = []
        logger.info(f"Generic fetch from {source.url}")
        
        # 这里应该实现通用的HTTP抓取逻辑
        # 为了演示，返回空列表
        
        return cards
    
    def _parse_ygoprodeck_card(self, card_data: Dict, source_id: str) -> Optional[CardInfo]:
        """解析YGOPRODeck卡片数据"""
        try:
            card_id = str(card_data.get('id', ''))
            name = card_data.get('name', '')
            
            if not card_id or not name:
                return None
            
            # 确定卡片类型
            card_type = card_data.get('type', 'Monster')
            
            # 提取基本信息
            card = CardInfo(
                card_id=card_id,
                name=name,
                type=card_type,
                effect_text=card_data.get('desc', ''),
                source=source_id,
                last_updated=datetime.now()
            )
            
            # Monster类型特殊字段
            if 'Monster' in card_type:
                card.attribute = card_data.get('attribute')
                card.level = card_data.get('level')
                card.atk = card_data.get('atk')
                card.def_ = card_data.get('def')
                
                # 链接怪兽
                if 'Link' in card_type:
                    card.link_rating = card_data.get('linkval')
                # 灵摆怪兽
                elif 'Pendulum' in card_type:
                    card.pendulum_scale = card_data.get('scale')
                    card.pendulum_text = card_data.get('pend_desc', '')
            
            # 卡片系列信息
            card_sets = card_data.get('card_sets', [])
            if card_sets:
                card.card_sets = [
                    {
                        'set_name': s.get('set_name', ''),
                        'set_code': s.get('set_code', ''),
                        'set_price': s.get('set_price', '')
                    }
                    for s in card_sets
                ]
            
            # 禁限信息
            banlist = card_data.get('banlist_info', {})
            if banlist:
                card.banlist_info = banlist
            
            # 图片URL
            card.image_url = card_data.get('card_images', [{}])[0].get('image_url')
            
            # 计算校验和
            card.checksum = self._calculate_checksum(card)
            
            return card
            
        except Exception as e:
            logger.error(f"Card parse error: {e}")
            return None
    
    def _calculate_checksum(self, card: CardInfo) -> str:
        """计算卡片校验和"""
        content = f"{card.card_id}|{card.name}|{card.effect_text}|{card.last_updated}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _update_card(self, card: CardInfo) -> bool:
        """
        更新卡片信息
        
        Returns:
            True if card was updated, False if unchanged
        """
        existing = self.cache.get(card.card_id)
        
        if existing:
            # 检查是否有变化
            if existing.checksum == card.checksum:
                return False  # 没有变化
        
        # 更新缓存
        self.cache[card.card_id] = card
        return True
    
    def get_card(self, card_id: str) -> Optional[CardInfo]:
        """获取单个卡片信息"""
        return self.cache.get(card_id)
    
    def get_all_cards(self) -> List[CardInfo]:
        """获取所有卡片"""
        return list(self.cache.values())
    
    def get_cards_count(self) -> int:
        """获取卡片数量"""
        return len(self.cache)
    
    def search_cards(self, keyword: str) -> List[CardInfo]:
        """搜索卡片"""
        keyword = keyword.lower()
        results = []
        
        for card in self.cache.values():
            if (keyword in card.name.lower() or
                keyword in card.effect_text.lower() or
                keyword in card.type.lower()):
                results.append(card)
        
        return results
    
    def get_recently_updated(self, hours: int = 24) -> List[CardInfo]:
        """获取最近更新的卡片"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            card for card in self.cache.values()
            if card.last_updated > cutoff
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取抓取统计"""
        cards = list(self.cache.values())
        
        return {
            'total_cards': len(cards),
            'by_type': self._count_by_type(cards),
            'with_banlist': sum(1 for c in cards if c.banlist_info),
            'recently_updated': len(self.get_recently_updated()),
            'sources_used': list(set(c.source for c in cards))
        }
    
    def _count_by_type(self, cards: List[CardInfo]) -> Dict[str, int]:
        """按类型统计"""
        counts = {}
        for card in cards:
            counts[card.type] = counts.get(card.type, 0) + 1
        return counts


# 全局单例
_card_fetcher = None

def get_card_fetcher() -> CardFetcher:
    """获取卡片抓取器单例"""
    global _card_fetcher
    if _card_fetcher is None:
        _card_fetcher = CardFetcher()
    return _card_fetcher


# 辅助函数：处理时间差
from datetime import timedelta
