from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.table_state import DEVICE_ID


class DeviceResponse(BaseModel):
    """A table controller the Tournament Core has heard of."""

    id: str
    sensor: str | None
    station_id: UUID | None
    left_cups: int | None
    right_cups: int | None
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class DeviceBinding(BaseModel):
    """Which controller counts at a station."""

    device_id: str = Field(pattern=DEVICE_ID.pattern)


class SuggestionResponse(BaseModel):
    """The result the counts end the match with; the referee takes it over or corrects it."""

    match_id: UUID
    winner_team_id: UUID
    score_a: int
    score_b: int


class StationSensorResponse(BaseModel):
    """What the controller of a station counts now (team a of the match on the left)."""

    station_id: UUID
    device_id: str
    sensor: str | None
    online: bool
    left_cups: int | None
    right_cups: int | None
    last_seen_at: datetime
    match_id: UUID | None
    suggestion: SuggestionResponse | None


class NodeInfo(BaseModel):
    """Who answers: the cloud or a Tournament Core at the venue (the web app looks for one, docs/edge)."""

    name: str
    role: str
    node: str
    version: str
    api: int
