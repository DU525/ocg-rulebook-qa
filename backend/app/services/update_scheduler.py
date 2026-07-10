"""
定时更新调度器
实现定时任务调度，支持全量更新、增量更新、紧急更新等
"""
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
    FULL_SYNC = "full_sync"          # 全量同步
    INCREMENTAL_SYNC = "incremental"  # 增量同步
    HEALTH_CHECK = "health_check"     # 健康检查
    EMERGENCY = "emergency"           # 紧急更新


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 执行中
    SUCCESS = "success"       # 成功
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


@dataclass
class UpdateTask:
    """更新任务"""
    task_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    priority: int = 5  # 1-10, 1是最高优先级
    scheduled_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class SchedulerConfig:
    """调度器配置"""
    enabled: bool = True
    timezone: str = "Asia/Shanghai"
    max_instances: int = 1
    coalesce: bool = True
    misfire_grace_time: int = 300


class UpdateScheduler:
    """更新调度器"""
    
    # 默认调度配置
    DEFAULT_JOBS = {
        'daily_full_sync': {
            'type': TaskType.FULL_SYNC,
            'schedule': 'cron',
            'cron': '0 3 * * *',  # 每天凌晨3点
            'enabled': True,
            'priority': 1
        },
        'hourly_incremental': {
            'type': TaskType.INCREMENTAL_SYNC,
            'schedule': 'interval',
            'interval_seconds': 3600,  # 每小时
            'enabled': True,
            'priority': 3
        },
        'health_check': {
            'type': TaskType.HEALTH_CHECK,
            'schedule': 'interval',
            'interval_seconds': 300,  # 每5分钟
            'enabled': True,
            'priority': 5
        }
    }
    
    def __init__(self, config: Optional[SchedulerConfig] = None):
        self.config = config or SchedulerConfig()
        self.scheduler = BackgroundScheduler(
            timezone=self.config.timezone,
            job_defaults={
                'max_instances': self.config.max_instances,
                'coalesce': self.config.coalesce,
                'misfire_grace_time': self.config.misfire_grace_time
            }
        )
        self.tasks: Dict[str, UpdateTask] = {}
        self.task_history: List[UpdateTask] = []
        self._task_callbacks: Dict[TaskType, List[Callable]] = {}
        self._is_running = False
        logger.info("UpdateScheduler initialized")
    
    def start(self):
        """启动调度器"""
        if self._is_running:
            logger.warning("Scheduler already running")
            return
        
        # 添加默认任务
        for job_name, job_config in self.DEFAULT_JOBS.items():
            if job_config.get('enabled', True):
                self._add_default_job(job_name, job_config)
        
        # 启动调度器
        self.scheduler.start()
        self._is_running = True
        logger.info("Scheduler started")
    
    def stop(self):
        """停止调度器"""
        if not self._is_running:
            return
        
        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("Scheduler stopped")
    
    def _add_default_job(self, job_name: str, job_config: Dict):
        """添加默认任务"""
        trigger = None
        schedule_type = job_config.get('schedule', 'interval')
        
        if schedule_type == 'cron':
            # 解析cron表达式
            cron_parts = job_config['cron'].split()
            trigger = CronTrigger(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day=cron_parts[2],
                month=cron_parts[3],
                day_of_week=cron_parts[4]
            )
        else:
            # 间隔执行
            interval = job_config.get('interval_seconds', 3600)
            trigger = IntervalTrigger(seconds=interval)
        
        # 添加任务
        task_id = self._create_task_id(job_name)
        self.scheduler.add_job(
            func=self._execute_scheduled_task,
            trigger=trigger,
            id=task_id,
            args=[job_name, job_config['type']],
            name=job_name,
            replace_existing=True
        )
        
        logger.info(f"Added scheduled job: {job_name}")
    
    def add_task(
        self,
        task_type: TaskType,
        priority: int = 5,
        scheduled_time: Optional[datetime] = None,
        immediate: bool = True
    ) -> UpdateTask:
        """
        添加新任务
        
        Args:
            task_type: 任务类型
            priority: 优先级(1-10)
            scheduled_time: 定时执行时间
            immediate: 是否立即执行
            
        Returns:
            创建的UpdateTask对象
        """
        task_id = self._create_task_id(f"{task_type.value}_{int(time.time())}")
        
        task = UpdateTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            scheduled_time=scheduled_time
        )
        
        self.tasks[task_id] = task
        
        if immediate:
            # 立即执行任务
            self._execute_task_async(task_id)
        
        logger.info(f"Added task: {task_id} (type: {task_type.value})")
        return task
    
    def _create_task_id(self, base: str) -> str:
        """创建任务ID"""
        return f"task_{base}_{int(time.time()*1000)}"
    
    def _execute_scheduled_task(self, job_name: str, task_type: TaskType):
        """执行调度任务"""
        task_id = self._create_task_id(job_name)
        
        task = UpdateTask(
            task_id=task_id,
            task_type=task_type,
            priority=self.DEFAULT_JOBS.get(job_name, {}).get('priority', 5)
        )
        
        self.tasks[task_id] = task
        
        # 触发回调
        self._trigger_callbacks(task_type, task)
        
        # 执行任务
        self._execute_task(task_id)
    
    def _execute_task_async(self, task_id: str):
        """异步执行任务"""
        import threading
        thread = threading.Thread(target=self._execute_task, args=(task_id,))
        thread.daemon = True
        thread.start()
    
    def _execute_task(self, task_id: str):
        """执行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        logger.info(f"Executing task: {task_id}")
        
        try:
            # 根据任务类型执行不同的逻辑
            if task.task_type == TaskType.FULL_SYNC:
                result = self._execute_full_sync(task)
            elif task.task_type == TaskType.INCREMENTAL_SYNC:
                result = self._execute_incremental_sync(task)
            elif task.task_type == TaskType.HEALTH_CHECK:
                result = self._execute_health_check(task)
            elif task.task_type == TaskType.EMERGENCY:
                result = self._execute_emergency_update(task)
            else:
                result = {'error': 'Unknown task type'}
            
            task.status = TaskStatus.SUCCESS
            task.result = result
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Task {task_id} failed: {e}")
        
        finally:
            task.completed_at = datetime.now()
            task.duration = (task.completed_at - task.started_at).total_seconds()
            
            # 移动到历史
            self.task_history.append(task)
            if task_id in self.tasks:
                del self.tasks[task_id]
            
            # 保持历史不超过100条
            if len(self.task_history) > 100:
                self.task_history = self.task_history[-100:]
    
    def _execute_full_sync(self, task: UpdateTask) -> Dict[str, Any]:
        """执行全量同步"""
        from app.services.card_fetcher import get_card_fetcher
        
        fetcher = get_card_fetcher()
        result = fetcher.fetch_all_cards()
        
        return {
            'task_type': 'full_sync',
            'cards_fetched': result.cards_fetched,
            'cards_updated': result.cards_updated,
            'duration': result.duration,
            'success': result.success
        }
    
    def _execute_incremental_sync(self, task: UpdateTask) -> Dict[str, Any]:
        """执行增量同步"""
        from app.services.card_fetcher import get_card_fetcher
        
        fetcher = get_card_fetcher()
        result = fetcher.fetch_all_cards()
        
        return {
            'task_type': 'incremental_sync',
            'cards_fetched': result.cards_fetched,
            'cards_updated': result.cards_updated,
            'duration': result.duration,
            'success': result.success
        }
    
    def _execute_health_check(self, task: UpdateTask) -> Dict[str, Any]:
        """执行健康检查"""
        from app.services.data_source_manager import get_data_source_manager
        
        manager = get_data_source_manager()
        results = manager.check_all_sources_health()
        
        healthy_count = sum(1 for r in results.values() if r.is_healthy)
        
        return {
            'task_type': 'health_check',
            'total_sources': len(results),
            'healthy_sources': healthy_count,
            'health_rate': healthy_count / max(1, len(results)) * 100,
            'sources': {
                source_id: {
                    'is_healthy': r.is_healthy,
                    'response_time': r.response_time,
                    'error': r.error_message
                }
                for source_id, r in results.items()
            }
        }
    
    def _execute_emergency_update(self, task: UpdateTask) -> Dict[str, Any]:
        """执行紧急更新"""
        from app.services.card_fetcher import get_card_fetcher
        
        fetcher = get_card_fetcher()
        
        # 尝试所有健康的数据源
        from app.services.data_source_manager import get_data_source_manager
        manager = get_data_source_manager()
        healthy_sources = manager.get_healthy_sources()
        
        total_updated = 0
        success = True
        
        for source in healthy_sources[:2]:  # 最多尝试2个
            result = fetcher.fetch_all_cards(source.id)
            total_updated += result.cards_updated
            if not result.success:
                success = False
        
        return {
            'task_type': 'emergency',
            'sources_tried': len(healthy_sources[:2]),
            'total_updated': total_updated,
            'success': success
        }
    
    def register_callback(self, task_type: TaskType, callback: Callable):
        """注册任务回调"""
        if task_type not in self._task_callbacks:
            self._task_callbacks[task_type] = []
        self._task_callbacks[task_type].append(callback)
    
    def _trigger_callbacks(self, task_type: TaskType, task: UpdateTask):
        """触发任务回调"""
        callbacks = self._task_callbacks.get(task_type, [])
        for callback in callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[UpdateTask]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[UpdateTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_task_history(self, limit: int = 10) -> List[UpdateTask]:
        """获取任务历史"""
        return self.task_history[-limit:]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            # 从调度器中移除
            self.scheduler.remove_job(task_id)
            # 更新状态
            task = self.tasks.get(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
            return True
        except:
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取调度器统计"""
        running_tasks = [t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]
        pending_tasks = [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
        
        recent_history = self.task_history[-20:]
        success_count = sum(1 for t in recent_history if t.status == TaskStatus.SUCCESS)
        
        return {
            'is_running': self._is_running,
            'scheduled_jobs': len(self.scheduler.get_jobs()),
            'active_tasks': len(self.tasks),
            'running_tasks': len(running_tasks),
            'pending_tasks': len(pending_tasks),
            'recent_success_rate': success_count / max(1, len(recent_history)) * 100,
            'total_tasks_executed': len(self.task_history)
        }


# 全局单例
_scheduler = None

def get_update_scheduler() -> UpdateScheduler:
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = UpdateScheduler()
    return _scheduler
