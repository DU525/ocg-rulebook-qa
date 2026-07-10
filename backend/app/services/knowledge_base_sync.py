"""
知识库自动同步器
实现知识库的自动同步、版本管理、冲突解决等功能
"""
import logging
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from app.services.card_fetcher import get_card_fetcher, CardInfo
from app.services.update_scheduler import TaskType

logger = logging.getLogger(__name__)


@dataclass
class SyncVersion:
    """同步版本记录"""
    version_id: str
    timestamp: datetime
    cards_added: int = 0
    cards_updated: int = 0
    cards_removed: int = 0
    checksum: str = ""
    status: str = "completed"  # completed, failed, partial
    error: Optional[str] = None


@dataclass
class SyncConflict:
    """同步冲突"""
    card_id: str
    conflict_type: str  # duplicate, version_mismatch, deleted
    local_version: Optional[Dict] = None
    remote_version: Optional[Dict] = None
    resolution: Optional[str] = None  # use_local, use_remote, manual


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    version_id: str
    cards_processed: int = 0
    cards_added: int = 0
    cards_updated: int = 0
    cards_unchanged: int = 0
    conflicts: List[SyncConflict] = field(default_factory=list)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeBaseSync:
    """知识库同步器"""
    
    def __init__(self):
        self.card_fetcher = get_card_fetcher()
        self.versions: List[SyncVersion] = []
        self.current_cards: Dict[str, Dict] = {}  # card_id -> card_data
        self.version_counter = 0
        logger.info("KnowledgeBaseSync initialized")
    
    def sync_to_knowledge_base(self) -> SyncResult:
        """
        将抓取的卡片同步到知识库
        
        Returns:
            SyncResult对象
        """
        import time
        start_time = time.time()
        
        result = SyncResult(
            success=False,
            version_id=self._generate_version_id()
        )
        
        try:
            # 获取所有抓取的卡片
            fetched_cards = self.card_fetcher.get_all_cards()
            
            # 构建卡片数据字典
            fetched_data = {}
            for card in fetched_cards:
                fetched_data[card.card_id] = self._card_to_dict(card)
            
            # 检测变更
            added, updated, unchanged = self._detect_changes(fetched_data)
            
            # 处理冲突
            conflicts = self._detect_conflicts(fetched_data)
            
            # 应用同步（这里应该写入实际的知识库）
            # 简化实现：更新本地缓存
            for card_id, card_data in fetched_data.items():
                self.current_cards[card_id] = card_data
            
            # 创建版本记录
            version = SyncVersion(
                version_id=result.version_id,
                timestamp=datetime.now(),
                cards_added=len(added),
                cards_updated=len(updated),
                checksum=self._calculate_checksum(fetched_data)
            )
            self.versions.append(version)
            
            # 更新结果
            result.success = True
            result.cards_processed = len(fetched_data)
            result.cards_added = len(added)
            result.cards_updated = len(updated)
            result.cards_unchanged = len(unchanged)
            result.conflicts = conflicts
            
            # 保持版本历史不超过50条
            if len(self.versions) > 50:
                self.versions = self.versions[-50:]
            
            logger.info(f"Sync completed: {result.cards_processed} cards, "
                        f"+{result.cards_added} -{result.cards_updated} ~{result.cards_unchanged}")
            
        except Exception as e:
            result.success = False
            logger.error(f"Sync failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    def _card_to_dict(self, card: CardInfo) -> Dict[str, Any]:
        """将CardInfo转换为字典"""
        return {
            'card_id': card.card_id,
            'name': card.name,
            'type': card.type,
            'attribute': card.attribute,
            'level': card.level,
            'atk': card.atk,
            'def': card.def_,
            'effect_text': card.effect_text,
            'pendulum_text': card.pendulum_text,
            'pendulum_scale': card.pendulum_scale,
            'link_rating': card.link_rating,
            'card_sets': card.card_sets,
            'banlist_info': card.banlist_info,
            'image_url': card.image_url,
            'source': card.source,
            'last_updated': card.last_updated.isoformat() if card.last_updated else None,
            'checksum': card.checksum
        }
    
    def _detect_changes(self, new_data: Dict[str, Dict]) -> Tuple[List[str], List[str], List[str]]:
        """检测变更"""
        added = []
        updated = []
        unchanged = []
        
        for card_id, card_data in new_data.items():
            if card_id not in self.current_cards:
                added.append(card_id)
            else:
                old_checksum = self.current_cards[card_id].get('checksum', '')
                new_checksum = card_data.get('checksum', '')
                
                if old_checksum != new_checksum:
                    updated.append(card_id)
                else:
                    unchanged.append(card_id)
        
        return added, updated, unchanged
    
    def _detect_conflicts(self, new_data: Dict[str, Dict]) -> List[SyncConflict]:
        """检测冲突"""
        conflicts = []
        
        # 检测版本冲突（如果有多个数据源可能返回不同版本）
        # 简化实现：检测同名卡片
        name_map = defaultdict(list)
        
        for card_id, card_data in new_data.items():
            name = card_data.get('name', '')
            name_map[name].append(card_id)
        
        for name, card_ids in name_map.items():
            if len(card_ids) > 1:
                # 检测到同名卡片，可能需要手动合并
                for card_id in card_ids[1:]:
                    conflicts.append(SyncConflict(
                        card_id=card_id,
                        conflict_type='duplicate',
                        local_version=self.current_cards.get(card_id),
                        remote_version=new_data[card_id]
                    ))
        
        return conflicts
    
    def resolve_conflict(self, conflict: SyncConflict, resolution: str) -> bool:
        """
        解决冲突
        
        Args:
            conflict: 冲突对象
            resolution: 解决方案 ('use_local', 'use_remote', 'manual')
            
        Returns:
            是否成功解决
        """
        try:
            if resolution == 'use_local':
                # 使用本地版本
                pass  # 已经保留在current_cards中
            elif resolution == 'use_remote':
                # 使用远程版本
                if conflict.remote_version:
                    self.current_cards[conflict.card_id] = conflict.remote_version
            elif resolution == 'manual':
                # 标记为需要手动处理
                conflict.resolution = 'manual'
                return False
            
            conflict.resolution = resolution
            return True
            
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            return False
    
    def _generate_version_id(self) -> str:
        """生成版本ID"""
        self.version_counter += 1
        return f"v{self.version_counter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _calculate_checksum(self, data: Dict[str, Dict]) -> str:
        """计算数据校验和"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_latest_version(self) -> Optional[SyncVersion]:
        """获取最新版本"""
        return self.versions[-1] if self.versions else None
    
    def get_version_history(self, limit: int = 10) -> List[SyncVersion]:
        """获取版本历史"""
        return self.versions[-limit:]
    
    def rollback_to_version(self, version_id: str) -> bool:
        """
        回滚到指定版本
        
        Args:
            version_id: 版本ID
            
        Returns:
            是否成功回滚
        """
        # 简化实现：实际应该从备份中恢复
        for version in self.versions:
            if version.version_id == version_id:
                logger.info(f"Rolling back to version {version_id}")
                # TODO: 实现实际的回滚逻辑
                return True
        return False
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """获取同步统计"""
        if not self.versions:
            return {
                'total_syncs': 0,
                'last_sync': None,
                'current_cards': 0,
                'total_cards_synced': 0
            }
        
        latest = self.versions[-1]
        successful_syncs = sum(1 for v in self.versions if v.status == 'completed')
        
        return {
            'total_syncs': len(self.versions),
            'successful_syncs': successful_syncs,
            'success_rate': successful_syncs / len(self.versions) * 100,
            'last_sync': {
                'version_id': latest.version_id,
                'timestamp': latest.timestamp.isoformat(),
                'cards_added': latest.cards_added,
                'cards_updated': latest.cards_updated,
                'status': latest.status
            },
            'current_cards': len(self.current_cards),
            'total_cards_synced': sum(v.cards_added + v.cards_updated for v in self.versions)
        }
    
    def get_card(self, card_id: str) -> Optional[Dict]:
        """获取单个卡片"""
        return self.current_cards.get(card_id)
    
    def get_all_cards(self) -> List[Dict]:
        """获取所有卡片"""
        return list(self.current_cards.values())
    
    def search_cards(self, keyword: str) -> List[Dict]:
        """搜索卡片"""
        keyword = keyword.lower()
        results = []
        
        for card in self.current_cards.values():
            name = card.get('name', '').lower()
            effect = card.get('effect_text', '').lower()
            
            if keyword in name or keyword in effect:
                results.append(card)
        
        return results


# 全局单例
_kb_sync = None

def get_knowledge_base_sync() -> KnowledgeBaseSync:
    """获取知识库同步器单例"""
    global _kb_sync
    if _kb_sync is None:
        _kb_sync = KnowledgeBaseSync()
    return _kb_sync
