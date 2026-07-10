from sqlalchemy import create_engine, Column, String, Text, JSON, DateTime, Integer, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Conversation(Base):
    """对话模型"""
    __tablename__ = 'conversations'

    id = Column(String(36), primary_key=True)
    title = Column(String(255), default="新对话")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta_data = Column(JSON, default={})  # Renamed from 'metadata' to avoid SQLAlchemy conflict

class Message(Base):
    """消息模型"""
    __tablename__ = 'messages'

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36))
    role = Column(String(20))
    content = Column(Text)
    citations = Column(JSON, default=[])
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    """文档模型"""
    __tablename__ = 'documents'

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    source = Column(String(20))
    file_path = Column(String(512))
    status = Column(String(20))
    chunk_count = Column(Integer, default=0)
    file_size = Column(Integer, default=0)  # 文件大小（字节）
    # 上传进度跟踪字段
    upload_progress = Column(String(20), default='pending')  # pending/processing/completed/failed
    uploaded_bytes = Column(Integer, default=0)             # 已上传字节数
    total_bytes = Column(Integer, default=0)               # 总字节数
    error_message = Column(Text, nullable=True)           # 错误信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class PerformanceLog(Base):
    """性能日志模型"""
    __tablename__ = 'performance_logs'

    id = Column(String(36), primary_key=True)
    endpoint = Column(String(100))
    method = Column(String(10))
    response_time_ms = Column(Integer)
    status_code = Column(Integer)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Alert(Base):
    """告警模型"""
    __tablename__ = 'alerts'

    id = Column(String(36), primary_key=True)
    rule_type = Column(String(50))  # 告警规则类型: low_knowledge_base, no_conversations, etc.
    message = Column(Text)          # 告警消息内容
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Integer, default=0)  # 0=未读, 1=已读

class AlertRule(Base):
    """告警规则配置模型"""
    __tablename__ = 'alert_rules'

    id = Column(String(36), primary_key=True)
    rule_type = Column(String(50), unique=True)  # 规则类型唯一
    threshold = Column(Integer, default=0)      # 阈值
    enabled = Column(Integer, default=1)        # 是否启用
    description = Column(String(255))           # 规则描述
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Feedback(Base):
    """用户反馈模型"""
    __tablename__ = 'feedbacks'

    id = Column(String(36), primary_key=True)
    message_id = Column(String(36), nullable=False)
    conversation_id = Column(String(36))
    rating = Column(String(10), nullable=False)
    reason = Column(Text, nullable=True)
    game_type = Column(String(10), default='ocg')
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class NegativeSample(Base):
    """负样本模型 - 存储被标记为低质量的问答对"""
    __tablename__ = 'negative_samples'

    id = Column(String(36), primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    reason = Column(String(50), nullable=False)
    feedback_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ExperimentLog(Base):
    """A/B 实验日志模型"""
    __tablename__ = 'experiment_logs'

    id = Column(String(36), primary_key=True)
    experiment_name = Column(String(100), nullable=False)
    variant = Column(String(50), nullable=False)  # control/treatment
    user_id = Column(String(100))
    question = Column(Text)
    answer = Column(Text)
    latency_ms = Column(Integer)
    rating = Column(String(10))  # like/dislike/skip
    created_at = Column(DateTime, default=datetime.utcnow)


class Experiment(Base):
    """A/B 实验配置模型（experiment_routes.py 使用）

    与 ExperimentLog 的关系：
    - Experiment 是实验元数据（name / 状态 / 流量分配 / 目标指标）
    - ExperimentLog 是单条曝光/反馈日志（按 experiment_name 关联）
    - /stats 端点会按 experiment.name 聚合对应 ExperimentLog
    """
    __tablename__ = 'experiments'

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # 与 ExperimentLog.experiment_name 对齐
    description = Column(Text, nullable=True)
    status = Column(String(20), default='draft')  # draft/running/paused/completed/archived
    experiment_type = Column(String(30), default='a_b_test')  # a_b_test/multi_armed_bandit/feature_flag
    # config 字段约定（JSON）：
    # {
    #   "variants": [{"name": "control", "weight": 0.5}, {"name": "treatment", "weight": 0.5}],
    #   "target_metric": "positive_rate",   # /stats 要看的目标指标
    #   "traffic_allocation": 1.0,          # 0~1
    #   "notes": "..."
    # }
    config = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

class QualityLog(Base):
    """质量评估日志模型 - 存储RAGAS自动化评估结果"""
    __tablename__ = 'quality_logs'

    id = Column(String(36), primary_key=True)
    eval_date = Column(DateTime, default=datetime.utcnow)
    sample_size = Column(Integer)
    faithfulness_score = Column(Integer)  # score * 10000
    answer_relevancy_score = Column(Integer)
    context_precision_score = Column(Integer)
    context_recall_score = Column(Integer)
    overall_score = Column(Integer)
    report_path = Column(String(512))
    anomaly_detected = Column(Integer, default=0)

class Database:
    """数据库管理器"""

    def __init__(self, db_path: str):
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            connect_args={
                'check_same_thread': False,
                'timeout': 30,  # wait up to 30s for locks
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
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_message_id ON feedbacks(message_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_rating ON feedbacks(rating)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON feedbacks(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_is_read ON alerts(is_read)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_negative_samples_feedback_id ON negative_samples(feedback_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_negative_samples_reason ON negative_samples(reason)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_negative_samples_created_at ON negative_samples(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_experiment_logs_name ON experiment_logs(experiment_name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_experiment_logs_variant ON experiment_logs(variant)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_experiment_logs_created_at ON experiment_logs(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_experiments_name ON experiments(name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_experiments_created_at ON experiments(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quality_logs_eval_date ON quality_logs(eval_date)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quality_logs_anomaly ON quality_logs(anomaly_detected)"))
            conn.commit()

        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def optimize(self):
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA optimize"))
            conn.commit()