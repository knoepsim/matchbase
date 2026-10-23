import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StationDevice(Base):
    """A table controller (ESP32 with RFID, Raspberry Pi with camera, ...) known to this Tournament Core.

    It appears with its first message and keeps its last state. Bound to a station, its counts belong to the match
    played there; a physical table serves one tournament after the other, so the binding moves with it.
    """

    __tablename__ = "station_devices"

    # chosen by the controller, the middle part of its topic (tables/{id}/state)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stations.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    sensor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    left_cups: Mapped[int | None] = mapped_column(Integer, nullable=True)
    right_cups: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class SensorReading(Base):
    """Every change a controller reported, with the match it belonged to: the data of the evaluation (detection
    rate, reaction time, losses) and the trace of how a sensor result came about."""

    __tablename__ = "sensor_readings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("station_devices.id"), nullable=False, index=True)
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stations.id", ondelete="SET NULL"), nullable=True
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    left_cups: Mapped[int] = mapped_column(Integer, nullable=False)
    right_cups: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
