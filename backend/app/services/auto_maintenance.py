"""
自动维护系统 - 主入口
整合数据源管理、卡片抓取、调度器、知识库同步等功能
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from app.services.data_source_manager import get_data_source_manager
from app.services.card_fetcher import get_card_fetcher
from app.services.update_scheduler import get_update_scheduler, TaskType, UpdateTask
from app.services.knowledge_base_sync import get_knowledge_base_sync


@dataclass
class MaintenanceStatus:
    """维护系统状态"""
    is_running: bool
    scheduler_status: str
    data_source_health: Dict[str, Any]
    last_sync: Optional[Dict[str, Any]]
    active_tasks: int
    cards_in_kb: int
    timestamp: datetime


class AutoMaintenanceSystem:
    """自动维护系统"""
    
    def __init__(self):
        self.data_source_manager = get_data_source_manager()
        self.card_fetcher = get_card_fetcher()
        self.scheduler = get_update_scheduler()
        self.kb_sync = get_knowledge_base_sync()
        self._is_running = False
        logger.info("AutoMaintenanceSystem initialized")
    
    def start(self):
        """启动自动维护系统"""
        if self._is_running:
            logger.warning("System already running")
            return
        
        # 启动调度器
        self.scheduler.start()
        self._is_running = True
        
        # 注册任务回调
        self.scheduler.register_callback(TaskType.FULL_SYNC, self._on_full_sync)
        self.scheduler.register_callback(TaskType.INCREMENTAL_SYNC, self._on_incremental_sync)
        self.scheduler.register_callback(TaskType.HEALTH_CHECK, self._on_health_check)
        
        logger.info("AutoMaintenanceSystem started")
    
    def stop(self):
        """停止自动维护系统"""
        if not self._is_running:
            return
        
        # 停止调度器
        self.scheduler.stop()
        self._is_running = False
        
        logger.info("AutoMaintenanceSystem stopped")
    
    def _on_full_sync(self, task: UpdateTask):
        """全量同步回调"""
        logger.info(f"Full sync task started: {task.task_id}")
        
        # 1. 抓取最新数据
        fetch_result = self.card_fetcher.fetch_all_cards()
        
        # 2. 同步到知识库
        if fetch_result.success:
            sync_result = self.kb_sync.sync_to_knowledge_base()
            logger.info(f"Full sync completed: {sync_result.cards_processed} cards")
        else:
            logger.error(f"Full sync failed: {fetch_result.errors}")
    
    def _on_incremental_sync(self, task: UpdateTask):
        """增量同步回调"""
        logger.info(f"Incremental sync task started: {task.task_id}")
        
        # 增量同步逻辑
        fetch_result = self.card_fetcher.fetch_all_cards()
        
        if fetch_result.success:
            sync_result = self.kb_sync.sync_to_knowledge_base()
            logger.info(f"Incremental sync completed: {sync_result.cards_updated} updated")
    
    def _on_health_check(self, task: UpdateTask):
        """健康检查回调"""
        health_results = self.data_source_manager.check_all_sources_health()
        
        # 检查是否有数据源不健康
        unhealthy = [r for r in health_results.values() if not r.is_healthy]
        
        if unhealthy:
            logger.warning(f"Found {len(unhealthy)} unhealthy data sources")
            # 可以触发告警通知
        
        return health_results
    
    def trigger_full_sync(self) -> UpdateTask:
        """手动触发全量同步"""
        task = self.scheduler.add_task(
            task_type=TaskType.FULL_SYNC,
            priority=1,
            immediate=True
        )
        return task
    
    def trigger_incremental_sync(self) -> UpdateTask:
        """手动触发增量同步"""
        task = self.scheduler.add_task(
            task_type=TaskType.INCREMENTAL_SYNC,
            priority=3,
            immediate=True
        )
        return task
    
    def trigger_emergency_update(self) -> UpdateTask:
        """手动触发紧急更新"""
        task = self.scheduler.add_task(
            task_type=TaskType.EMERGENCY,
            priority=1,
            immediate=True
        )
        return task
    
    def get_status(self) -> MaintenanceStatus:
        """获取系统状态"""
        scheduler_stats = self.scheduler.get_statistics()
        
        last_sync = self.kb_sync.get_latest_version()
        last_sync_info = None
        if last_sync:
            last_sync_info = {
                'version_id': last_sync.version_id,
                'timestamp': last_sync.timestamp.isoformat(),
                'cards_added': last_sync.cards_added,
                'cards_updated': last_sync.cards_updated,
                'status': last_sync.status
            }
        
        return MaintenanceStatus(
            is_running=self._is_running,
            scheduler_status='running' if self._is_running else 'stopped',
            data_source_health=self.data_source_manager.get_statistics(),
            last_sync=last_sync_info,
            active_tasks=len(self.scheduler.get_all_tasks()),
            cards_in_kb=len(self.kb_sync.get_all_cards()),
            timestamp=datetime.now()
        )
    
    def get_data_source_manager(self):
        """获取数据源管理器"""
        return self.data_source_manager
    
    def get_card_fetcher(self):
        """获取卡片抓取器"""
        return self.card_fetcher
    
    def get_scheduler(self):
        """获取调度器"""
        return self.scheduler
    
    def get_kb_sync(self):
        """获取知识库同步器"""
        return self.kb_sync
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        return {
            'system': {
                'is_running': self._is_running,
                'uptime': datetime.now().isoformat()
            },
            'data_sources': self.data_source_manager.get_statistics(),
            'card_fetcher': self.card_fetcher.get_statistics(),
            'scheduler': self.scheduler.get_statistics(),
            'knowledge_base_sync': self.kb_sync.get_sync_statistics()
        }


# 全局单例
_maintenance_system = None

def get_maintenance_system() -> AutoMaintenanceSystem:
    """获取自动维护系统单例"""
    global _maintenance_system
    if _maintenance_system is None:
        _maintenance_system = AutoMaintenanceSystem()
    return _maintenance_system
