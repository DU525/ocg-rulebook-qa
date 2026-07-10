"""数码宝贝数据库管理模块

注意：DM 与 OCG 共享 feedbacks 和 alerts 表（定义在 app/db/models.py 中）。
dm_routes.py 通过 `from app.db.models import Feedback, Alert` 直接使用 OCG 模型，
通过 game_type='dm' 字段区分 DM 反馈。因此 dm_models.py 不单独定义 Feedback/Alert 模型。
"""
from sqlalchemy import create_engine, Column, String, Text, JSON, DateTime, Integer, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class DMConversation(Base):
    """数码宝贝对话模型"""
    __tablename__ = 'dm_conversations'

    id = Column(String(36), primary_key=True)
    title = Column(String(255), default="新对话")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta_data = Column(JSON, default={})


class DMMessage(Base):
    """数码宝贝消息模型"""
    __tablename__ = 'dm_messages'

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36))
    role = Column(String(20))
    content = Column(Text)
    citations = Column(JSON, default=[])
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DMDocument(Base):
    """数码宝贝文档模型"""
    __tablename__ = 'dm_documents'

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    source = Column(String(20))
    file_path = Column(String(512))
    status = Column(String(20))
    chunk_count = Column(Integer, default=0)
    file_size = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DMDatabase:
    """数码宝贝数据库管理器"""

    def __init__(self, db_path: str):
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            connect_args={
                'check_same_thread': False,
                'timeout': 30,
            }
        )
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA cache_size=-64000"))
            conn.execute(text("PRAGMA temp_store=MEMORY"))
            conn.execute(text("PRAGMA mmap_size=268435456"))
            conn.commit()
        Base.metadata.create_all(self.engine)

        with self.engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dm_messages_conversation_id ON dm_messages(conversation_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dm_messages_created_at ON dm_messages(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dm_messages_conv_created ON dm_messages(conversation_id, created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dm_messages_role ON dm_messages(role)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dm_conversations_updated_at ON dm_conversations(updated_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dm_documents_status ON dm_documents(status)"))
            conn.commit()

        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def optimize(self):
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA optimize"))
            conn.commit()