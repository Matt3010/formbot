from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
import uuid


class ExecutionLog(Base):
    __tablename__ = 'execution_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey('tasks.id'), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default='pending')
    is_dry_run = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(Text, nullable=True)
    steps_log = Column(JSONB, nullable=True)
    vnc_session_id = Column(String(100), nullable=True)
    created_at = Column(DateTime)
