"""
Token Usage Tracking Models
Stores LLM token usage and costs for analytics.
Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from models.domain.auth import Base


class TokenUsage(Base):
    """Track token usage and costs for all LLM calls"""
    __tablename__ = 'token_usage'

    id = Column(Integer, primary_key=True, index=True)

    # Request metadata - CAN TRACK PER USER!
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=True, index=True)
    api_key_id = Column(Integer, ForeignKey('api_keys.id'), nullable=True, index=True)  # Track which API key was used
    session_id = Column(String(100), index=True)  # For grouping multi-LLM requests (e.g., node palette batch)
    conversation_id = Column(String(100), index=True)  # For multi-turn conversations (e.g., mindmate)

    # LLM details
    model_provider = Column(String(50), index=True)  # 'dashscope', 'tencent'
    model_name = Column(String(100), index=True)  # 'qwen-plus', 'deepseek-v3.1', etc.
    model_alias = Column(String(50), index=True)  # 'qwen', 'deepseek', 'kimi', 'hunyuan'

    # Token counts (ACTUAL from API)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # Cost (in CNY)
    input_cost = Column(Float, default=0.0)
    output_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)

    # Request details
    request_type = Column(String(50), index=True)  # Feature type: 'diagram_generation', 'node_palette', 'mindmate', 'autocomplete'
    diagram_type = Column(String(50))  # 'mind_map', 'concept_map', etc.
    endpoint_path = Column(String(200))  # API endpoint used: '/api/generate_graph', '/thinking_mode/node_palette/start', etc.
    success = Column(Boolean, default=True)

    # Timing
    response_time = Column(Float)  # seconds
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    api_key = relationship("APIKey", foreign_keys=[api_key_id])  # APIKey is defined in models.auth

    # Indexes for fast queries
    __table_args__ = (
        Index('idx_token_usage_user_date', 'user_id', 'created_at'),
        Index('idx_token_usage_org_date', 'organization_id', 'created_at'),
        Index('idx_token_usage_api_key_date', 'api_key_id', 'created_at'),
        Index('idx_token_usage_date', 'created_at'),
    )

    def __repr__(self):
        return f"<TokenUsage(user_id={self.user_id}, model={self.model_alias}, tokens={self.total_tokens})>"

