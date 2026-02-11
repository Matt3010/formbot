from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid


class FormField(Base):
    __tablename__ = 'form_fields'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_definition_id = Column(UUID(as_uuid=True), ForeignKey('form_definitions.id'), nullable=False)
    field_name = Column(String(255), nullable=False)
    field_type = Column(String(50), nullable=False)
    field_selector = Column(Text, nullable=False)
    field_purpose = Column(String(100), nullable=True)
    preset_value = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False)
    is_file_upload = Column(Boolean, default=False)
    is_required = Column(Boolean, default=False)
    options = Column(JSON, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
