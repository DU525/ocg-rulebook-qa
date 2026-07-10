"""
异步数据库模块 - Async Database

功能特性：
1. 使用 aiosqlite 替换 sqlite3，实现真正的异步 SQLite 操作
2. 异步连接池管理
3. 异步会话管理
4. 异步事务支持
5. 与现有模型兼容

使用示例：
```python
from app.services.async_database import AsyncDatabase
from app.db.models import Conversation, Message

# 初始化异步数据库
db = AsyncDatabase('data/app.db')
await db.initialize()

# 异步查询
async with db.get_session() as session:
    result = await session.execute(
        select(Conversation).where(Conversation.id == '123')
    )
    conv = result.scalar_one_or_none()

# 异步事务
async with db.transaction() as session:
    new_conv = Conversation(id='456', title='新对话')
    session.add(new_conv)
    await session.commit()
```
"""
import os
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import select, text
from sqlalchemy.orm import declarative_base

# 重新导入 Base，确保我们使用相同的模型定义
from app.db.models import (
    Base,
    Conversation,
    Message,
    Document,
    PerformanceLog,
    Alert,
    AlertRule,
    Feedback,
)

logger = logging.getLogger(__name__)


class AsyncDatabase:
    """
    异步数据库管理器
    
    使用 aiosqlite + SQLAlchemy 异步支持
    """
    
    def __init__(self, db_path: str):
        """
        初始化异步数据库
        
        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._engine = None
        self._async_session_maker = None
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    async def initialize(self):
        """
        初始化异步数据库引擎和连接池
        
        需要在应用启动时调用
        """
        # 创建异步引擎
        db_url = f"sqlite+aiosqlite:///{self.db_path}"
        
        self._engine = create_async_engine(
            db_url,
            echo=False,  # 生产环境设为 False
            pool_size=5,  # 连接池大小
            max_overflow=10,  # 最大溢出连接数
            pool_pre_ping=True,  # 连接前检测
            pool_recycle=3600,  # 1小时后回收连接
            connect_args={
                "timeout": 30.0,
                "check_same_thread": False,
            }
        )
        
        # 创建异步会话工厂
        self._async_session_maker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # 初始化数据库表和配置
        await self._initialize_database()
        
        logger.info(f"Async database initialized: {self.db_path}")
    
    async def _initialize_database(self):
        """
        初始化数据库表结构和 SQLite 优化配置
        """
        # 创建表
        async with self._engine.begin() as conn:
            # 应用 SQLite 优化配置
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA cache_size=-64000"))
            await conn.execute(text("PRAGMA temp_store=MEMORY"))
            await conn.execute(text("PRAGMA mmap_size=268435456"))
            
            # 创建所有表（如果不存在）
            await conn.run_sync(Base.metadata.create_all)
            
            # 创建索引
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_message_id ON feedbacks(message_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_rating ON feedbacks(rating)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON feedbacks(created_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_is_read ON alerts(is_read)"))
            await conn.commit()
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取异步数据库会话（上下文管理器）
        
        Yields:
            AsyncSession: 异步数据库会话
            
        Example:
            async with db.get_session() as session:
                result = await session.execute(select(...))
        """
        if self._async_session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize() first")
        
        async with self._async_session_maker() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        异步事务上下文管理器
        
        自动处理 commit 和 rollback
        
        Yields:
            AsyncSession: 异步数据库会话
            
        Example:
            async with db.transaction() as session:
                session.add(new_item)
                # 自动 commit，如果异常则 rollback
        """
        async with self.get_session() as session:
            async with session.begin():
                try:
                    yield session
                except Exception as e:
                    logger.error(f"Transaction error: {e}")
                    raise
    
    async def close(self):
        """
        关闭数据库连接池
        
        在应用关闭时调用
        """
        if self._engine:
            await self._engine.dispose()
            logger.info("Async database connection pool closed")
    
    async def optimize(self):
        """
        优化 SQLite 数据库
        """
        async with self._engine.connect() as conn:
            await conn.execute(text("PRAGMA optimize"))
            await conn.commit()
        logger.info("Database optimized")


# 便捷的异步 CRUD 操作类
class AsyncCRUD:
    """
    异步 CRUD 操作基类
    
    提供通用的异步数据库操作
    """
    
    def __init__(self, db: AsyncDatabase):
        self.db = db
    
    async def get_by_id(self, model_class, id_value: str):
        """
        根据 ID 获取单个对象
        
        Args:
            model_class: 模型类
            id_value: ID 值
            
        Returns:
            对象或 None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(model_class).where(model_class.id == id_value)
            )
            return result.scalar_one_or_none()
    
    async def create(self, instance):
        """
        创建新对象
        
        Args:
            instance: 模型实例
            
        Returns:
            创建后的实例
        """
        async with self.db.transaction() as session:
            session.add(instance)
            # 刷新获取数据库生成的字段
            await session.flush()
            await session.refresh(instance)
            return instance
    
    async def update(self, model_class, id_value: str, updates: dict):
        """
        更新对象
        
        Args:
            model_class: 模型类
            id_value: ID 值
            updates: 更新字段字典
            
        Returns:
            更新后的对象或 None
        """
        async with self.db.transaction() as session:
            result = await session.execute(
                select(model_class).where(model_class.id == id_value)
            )
            instance = result.scalar_one_or_none()
            
            if instance:
                for key, value in updates.items():
                    setattr(instance, key, value)
                
                if hasattr(instance, 'updated_at'):
                    instance.updated_at = datetime.utcnow()
                
                await session.commit()
                await session.refresh(instance)
            
            return instance
    
    async def delete(self, model_class, id_value: str) -> bool:
        """
        删除对象
        
        Args:
            model_class: 模型类
            id_value: ID 值
            
        Returns:
            是否成功删除
        """
        async with self.db.transaction() as session:
            result = await session.execute(
                select(model_class).where(model_class.id == id_value)
            )
            instance = result.scalar_one_or_none()
            
            if instance:
                await session.delete(instance)
                await session.commit()
                return True
            
            return False
    
    async def list_all(self, model_class, limit: int = 100, offset: int = 0):
        """
        列出所有对象（分页）
        
        Args:
            model_class: 模型类
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            对象列表
        """
        async with self.db.get_session() as session:
            stmt = select(model_class)
            
            # 尝试按创建时间排序（如果有该字段）
            if hasattr(model_class, 'created_at'):
                stmt = stmt.order_by(model_class.created_at.desc())
            
            stmt = stmt.limit(limit).offset(offset)
            
            result = await session.execute(stmt)
            return list(result.scalars().all())


# 对话相关的异步操作
class AsyncConversationCRUD(AsyncCRUD):
    """
    对话相关的异步 CRUD 操作
    """
    
    async def get_with_messages(self, conversation_id: str):
        """
        获取对话及其所有消息
        
        Args:
            conversation_id: 对话 ID
            
        Returns:
            (conversation, messages) 元组
        """
        async with self.db.get_session() as session:
            # 获取对话
            conv_result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            
            if not conversation:
                return None, []
            
            # 获取消息
            msg_result = await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
            messages = list(msg_result.scalars().all())
            
            return conversation, messages
    
    async def list_conversations(self, limit: int = 50, offset: int = 0):
        """
        列出对话列表
        
        Args:
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            对话列表
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Conversation)
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())


# 全局数据库实例（可选，方便使用）
_global_async_db: Optional[AsyncDatabase] = None


def init_global_async_db(db_path: str) -> AsyncDatabase:
    """
    初始化全局异步数据库实例
    
    Args:
        db_path: 数据库文件路径
        
    Returns:
        全局异步数据库实例
    """
    global _global_async_db
    _global_async_db = AsyncDatabase(db_path)
    return _global_async_db


def get_global_async_db() -> Optional[AsyncDatabase]:
    """
    获取全局异步数据库实例
    
    Returns:
        全局异步数据库实例或 None
    """
    return _global_async_db
