from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid


class FormDefinition(Base):
    __tablename__ = 'form_definitions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey('tasks.id'), nullable=False)
    step_order = Column(Integer, nullable=False, default=1)
    page_url = Column(Text, nullable=False)
    form_type = Column(String(50), nullable=True)
    form_selector = Column(Text, nullable=False)
    submit_selector = Column(Text, nullable=True)
    ai_confidence = Column(Numeric(3, 2), nullable=True)
    captcha_detected = Column(Boolean, default=False)
    two_factor_expected = Column(Boolean, default=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
