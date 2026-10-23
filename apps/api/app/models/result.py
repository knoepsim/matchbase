import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ResultType(str, enum.Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


class ResultSource(str, enum.Enum):
    """Who decided the score: a person, or a person who took over what the table's sensor counted."""

    MANUAL = "manual"
    SENSOR = "sensor"


class Result(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False)
    type: Mapped[ResultType] = mapped_column(Enum(ResultType), nullable=False)
    winner_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    # the score of both teams; what it counts is up to the game (beer pong: cups left, football: goals).
    # None for a deletion
    score_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[ResultSource] = mapped_column(
        Enum(ResultSource), nullable=False, default=ResultSource.MANUAL, server_default=ResultSource.MANUAL.name
    )
    reported_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    reported_by_user = relationship("User", foreign_keys=[reported_by_user_id])

    @property
    def reported_by_username(self) -> str | None:
        return self.reported_by_user.name if self.reported_by_user else None
