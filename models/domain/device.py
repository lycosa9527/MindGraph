"""
Device Model for ESP32 Smart Response Watches
"""

from datetime import UTC, datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from models.domain.auth import Base


class Device(Base):
    """ESP32 Watch Device Model"""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(String, unique=True, index=True, nullable=False)
    mac_address = Column(String, unique=True, nullable=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="unassigned")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_seen = Column(DateTime, nullable=True)

    student = relationship(
        "User",
        foreign_keys=[student_id],
        backref="devices",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Device(watch_id='{self.watch_id}', status='{self.status}')>"
