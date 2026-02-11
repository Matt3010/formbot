from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    target_url = Column(Text, nullable=False)
    schedule_type = Column(String(10), default='once')
    schedule_cron = Column(String(100), nullable=True)
    schedule_at = Column(DateTime, nullable=True)
    status = Column(String(20), default='draft')
    is_dry_run = Column(Boolean, default=False)
    max_retries = Column(Integer, default=3)
    max_parallel = Column(Integer, default=1)
    stealth_enabled = Column(Boolean, default=True)
    custom_user_agent = Column(Text, nullable=True)
    action_delay_ms = Column(Integer, default=500)
    cloned_from = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
