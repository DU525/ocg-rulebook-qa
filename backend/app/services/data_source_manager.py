"""
自动数据源管理器 - 核心模块
实现数据源配置、健康检查、优先级管理、失败重试等功能
"""
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class DataSourceStatus(Enum):
    """数据源状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


class DataSourceType(Enum):
    """数据源类型"""
    OFFICIAL = "official"       # 官方数据源
    THIRD_PARTY = "third_party" # 第三方数据源
    COMMUNITY = "community"      # 社区数据源


@dataclass
class DataSource:
    """数据源配置"""
    id: str
    name: str
    source_type: DataSourceType
    url: str
    api_key: Optional[str] = None
    enabled: bool = True
    priority: int = 1
    timeout: int = 30
    retry_count: int = 3
    update_interval: int = 3600  # 秒
    headers: Dict[str, str] = field(default_factory=dict)
    last_check_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    health_score: float = 100.0
    status: DataSourceStatus = DataSourceStatus.HEALTHY
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    source_id: str
    is_healthy: bool
    response_time: float
    status_code: int
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class DataSourceManager:
    """数据源管理器"""
    
    # 官方数据源配置
    DEFAULT_SOURCES = {
        'ocg_official': {
            'name': 'OCG官方数据库',
            'source_type': DataSourceType.OFFICIAL,
            'url': 'https://www.db.yugioh-card.com',
            'priority': 1,
            'update_interval': 3600
        },
        'ygoprodeck': {
            'name': 'YGOPRODeck API',
            'source_type': DataSourceType.THIRD_PARTY,
            'url': 'https://db.ygoprodeck.com/api/v7/cardinfo.php',
            'priority': 2,
            'update_interval': 7200
        },
        'yugipedia': {
            'name': 'Yugipedia',
            'source_type': DataSourceType.COMMUNITY,
            'url': 'https://yugipedia.com/api.php',
            'priority': 3,
            'update_interval': 10800
        }
    }
    
    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self.health_check_history: List[HealthCheckResult] = []
        self._init_default_sources()
        logger.info("DataSourceManager initialized")
    
    def _init_default_sources(self):
        """初始化默认数据源"""
        for source_id, config in self.DEFAULT_SOURCES.items():
            source = DataSource(
                id=source_id,
                name=config['name'],
                source_type=DataSourceType(config['source_type'].value),
                url=config['url'],
                priority=config['priority'],
                update_interval=config['update_interval']
            )
            self.sources[source_id] = source
    
    def add_source(self, source_config: Dict[str, Any]) -> DataSource:
        """
        添加数据源
        
        Args:
            source_config: 数据源配置字典
            
        Returns:
            创建的DataSource对象
        """
        source_id = source_config.get('id', f"custom_{int(time.time())}")
        
        if source_id in self.sources:
            logger.warning(f"DataSource {source_id} already exists, updating...")
        
        source = DataSource(
            id=source_id,
            name=source_config.get('name', source_id),
            source_type=DataSourceType(source_config.get('type', 'third_party')),
            url=source_config['url'],
            api_key=source_config.get('api_key'),
            enabled=source_config.get('enabled', True),
            priority=source_config.get('priority', 10),
            timeout=source_config.get('timeout', 30),
            retry_count=source_config.get('retry_count', 3),
            update_interval=source_config.get('update_interval', 3600),
            headers=source_config.get('headers', {}),
            metadata=source_config.get('metadata', {})
        )
        
        self.sources[source_id] = source
        logger.info(f"Added data source: {source_id}")
        
        return source
    
    def remove_source(self, source_id: str) -> bool:
        """移除数据源"""
        if source_id in self.sources:
            del self.sources[source_id]
            logger.info(f"Removed data source: {source_id}")
            return True
        return False
    
    def get_source(self, source_id: str) -> Optional[DataSource]:
        """获取数据源"""
        return self.sources.get(source_id)
    
    def get_all_sources(self, enabled_only: bool = False) -> List[DataSource]:
        """获取所有数据源"""
        sources = list(self.sources.values())
        if enabled_only:
            sources = [s for s in sources if s.enabled]
        return sorted(sources, key=lambda x: x.priority)
    
    def get_best_source(self) -> Optional[DataSource]:
        """获取最佳数据源（优先级最高+最健康）"""
        enabled = self.get_all_sources(enabled_only=True)
        
        if not enabled:
            return None
        
        # 按健康度和优先级排序
        def source_score(source: DataSource) -> tuple:
            # 优先级越高（数字越小）分数越高
            priority_score = 100 - source.priority
            # 健康度权重
            health_score = source.health_score * 0.5
            # 最近成功更新时间（越新越好）
            freshness_score = 0
            if source.last_success_time:
                hours_since = (datetime.now() - source.last_success_time).total_seconds() / 3600
                freshness_score = max(0, 50 - hours_since)
            
            return (priority_score + health_score + freshness_score)
        
        return max(enabled, key=source_score)
    
    def check_source_health(self, source_id: str) -> HealthCheckResult:
        """
        检查数据源健康状态
        
        Args:
            source_id: 数据源ID
            
        Returns:
            HealthCheckResult对象
        """
        source = self.sources.get(source_id)
        if not source:
            return HealthCheckResult(
                source_id=source_id,
                is_healthy=False,
                response_time=0,
                status_code=0,
                error_message="Source not found"
            )
        
        start_time = time.time()
        
        try:
            # 模拟健康检查（实际需要requests库）
            import requests
            
            response = requests.get(
                source.url,
                timeout=source.timeout,
                headers=source.headers,
                params={'format': 'json'} if 'ygoprodeck' in source.url else None
            )
            
            response_time = time.time() - start_time
            is_healthy = response.status_code == 200
            
            result = HealthCheckResult(
                source_id=source_id,
                is_healthy=is_healthy,
                response_time=response_time,
                status_code=response.status_code,
                error_message=None if is_healthy else f"HTTP {response.status_code}"
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                source_id=source_id,
                is_healthy=False,
                response_time=response_time,
                status_code=0,
                error_message=str(e)
            )
        
        # 更新数据源状态
        self._update_source_health(source, result)
        self.health_check_history.append(result)
        
        # 保持历史记录不超过1000条
        if len(self.health_check_history) > 1000:
            self.health_check_history = self.health_check_history[-1000:]
        
        return result
    
    def _update_source_health(self, source: DataSource, result: HealthCheckResult):
        """更新数据源健康状态"""
        source.last_check_time = result.timestamp
        
        if result.is_healthy:
            source.consecutive_failures = 0
            source.last_success_time = result.timestamp
            # 逐步恢复健康度
            source.health_score = min(100, source.health_score + 5)
            source.status = DataSourceStatus.HEALTHY
        else:
            source.consecutive_failures += 1
            # 逐步降低健康度
            source.health_score = max(0, source.health_score - 15)
            
            # 根据连续失败次数更新状态
            if source.consecutive_failures >= 5:
                source.status = DataSourceStatus.UNHEALTHY
            elif source.consecutive_failures >= 2:
                source.status = DataSourceStatus.DEGRADED
    
    def check_all_sources_health(self) -> Dict[str, HealthCheckResult]:
        """检查所有数据源健康状态"""
        results = {}
        for source_id in self.sources:
            if self.sources[source_id].enabled:
                results[source_id] = self.check_source_health(source_id)
        return results
    
    def get_healthy_sources(self) -> List[DataSource]:
        """获取健康的数据源列表"""
        return [
            s for s in self.get_all_sources(enabled_only=True)
            if s.status in [DataSourceStatus.HEALTHY, DataSourceStatus.DEGRADED]
        ]
    
    def should_update(self, source_id: str) -> bool:
        """检查是否应该更新某个数据源"""
        source = self.sources.get(source_id)
        if not source or not source.enabled:
            return False
        
        if not source.last_success_time:
            return True
        
        elapsed = (datetime.now() - source.last_success_time).total_seconds()
        return elapsed >= source.update_interval
    
    def get_update_candidates(self) -> List[DataSource]:
        """获取需要更新的数据源"""
        candidates = []
        for source in self.get_all_sources(enabled_only=True):
            if self.should_update(source.id):
                candidates.append(source)
        return candidates
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取数据源统计信息"""
        all_sources = self.get_all_sources()
        enabled_sources = self.get_all_sources(enabled_only=True)
        healthy_sources = self.get_healthy_sources()
        
        return {
            'total_sources': len(all_sources),
            'enabled_sources': len(enabled_sources),
            'healthy_sources': len(healthy_sources),
            'health_rate': len(healthy_sources) / max(1, len(enabled_sources)) * 100,
            'sources_by_status': {
                status.value: sum(1 for s in all_sources if s.status == status)
                for status in DataSourceStatus
            },
            'sources_by_type': {
                stype.value: sum(1 for s in all_sources if s.source_type == stype)
                for stype in DataSourceType
            }
        }
    
    def enable_source(self, source_id: str) -> bool:
        """启用数据源"""
        source = self.sources.get(source_id)
        if source:
            source.enabled = True
            source.status = DataSourceStatus.HEALTHY
            logger.info(f"Enabled data source: {source_id}")
            return True
        return False
    
    def disable_source(self, source_id: str, reason: Optional[str] = None) -> bool:
        """禁用数据源"""
        source = self.sources.get(source_id)
        if source:
            source.enabled = False
            source.status = DataSourceStatus.DISABLED
            logger.info(f"Disabled data source: {source_id}. Reason: {reason}")
            return True
        return False


# 全局单例
_source_manager = None

def get_data_source_manager() -> DataSourceManager:
    """获取数据源管理器单例"""
    global _source_manager
    if _source_manager is None:
        _source_manager = DataSourceManager()
    return _source_manager
