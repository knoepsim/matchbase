"""The table controllers on the Tournament Core: their messages, their binding to stations, what they say about a match.

A sensor never writes a result. It reports how many cups stand on each side; once the counts end the match (the game
decides, app/games.py) the station offers the result as a suggestion, and a referee takes it over with one tap
(`source="sensor"`). Who stands on which side: team a of the match on the left.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.games import sensed_result
from app.models.match import Match
from app.models.station import Station
from app.models.station_device import SensorReading, StationDevice
from app.models.tournament import Tournament
from app.schemas.table_state import TableState
from app.services.revision import bump


@dataclass(frozen=True)
class Suggestion:
    """The result the counts of the sensor end the match with."""

    match_id: UUID
    winner_team_id: UUID
    score_a: int
    score_b: int


@dataclass(frozen=True)
class StationSensor:
    """A station with a controller: what it counts now and what that means for the match played there."""

    station_id: UUID
    device: StationDevice
    online: bool
    match_id: UUID | None
    suggestion: Suggestion | None


def _aware(value: datetime) -> datetime:
    # SQLite (tests) gives naive datetimes back; they were written in UTC
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class SensorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest(self, device_id: str, state: TableState, now: datetime | None = None) -> SensorReading | None:
        """Take a message of a controller. Returns the reading if the counts changed, None for a repetition (same
        `seq` again) or a heartbeat (same counts): both only show that the controller is alive."""
        now = now or datetime.now(UTC)
        device = await self.db.get(StationDevice, device_id)
        if device is None:
            device = StationDevice(id=device_id)
            self.db.add(device)
            # written before its first reading: there is no relationship that would tell the unit of work the order
            await self.db.flush()
        device.last_seen_at = now
        if state.sensor:
            device.sensor = state.sensor
        if state.seq is not None and state.seq == device.last_seq:
            return None
        device.last_seq = state.seq
        if (device.left_cups, device.right_cups) == (state.left_cups, state.right_cups):
            return None
        device.left_cups, device.right_cups = state.left_cups, state.right_cups

        station = await self.db.get(Station, device.station_id) if device.station_id else None
        match = await self._match_at(station.id) if station else None
        reading = SensorReading(
            device_id=device.id,
            station_id=station.id if station else None,
            match_id=match.id if match else None,
            left_cups=state.left_cups,
            right_cups=state.right_cups,
            seq=state.seq,
            received_at=now,
        )
        self.db.add(reading)
        await self.db.flush()
        if station:
            await bump(self.db, station.tournament_id, "sensors")
        return reading

    async def list_devices(self) -> list[StationDevice]:
        return list((await self.db.execute(select(StationDevice).order_by(StationDevice.id))).scalars().all())

    async def bind(self, tournament_id: UUID, station_id: UUID, device_id: str | None) -> None:
        """Put a controller on a station (it leaves the station it was on), or take the station's controller off."""
        station = await self.db.get(Station, station_id)
        if station is None or station.tournament_id != tournament_id:
            raise NotFoundError("Spielstätte")
        current = (
            await self.db.execute(select(StationDevice).where(StationDevice.station_id == station_id))
        ).scalar_one_or_none()
        if current is not None:
            current.station_id = None
        if device_id is not None:
            device = await self.db.get(StationDevice, device_id)
            if device is None:
                raise NotFoundError("Controller")
            # flushed first: the station of the old binding is free before the new one takes it (unique)
            await self.db.flush()
            device.station_id = station_id
        await self.db.flush()
        await bump(self.db, tournament_id, "sensors")

    async def station_sensors(self, tournament_id: UUID, now: datetime | None = None) -> list[StationSensor]:
        """The stations of the tournament that have a controller, in the order of the stations."""
        now = now or datetime.now(UTC)
        game = (await self.db.execute(select(Tournament.game).where(Tournament.id == tournament_id))).scalar_one()
        rows = await self.db.execute(
            select(Station.id, StationDevice)
            .join(StationDevice, StationDevice.station_id == Station.id)
            .where(Station.tournament_id == tournament_id)
            .order_by(Station.position)
        )
        offline_after = timedelta(seconds=settings.sensor_offline_seconds)
        sensors = []
        for station_id, device in rows.all():
            match = await self._match_at(station_id)
            sensors.append(
                StationSensor(
                    station_id=station_id,
                    device=device,
                    online=now - _aware(device.last_seen_at) <= offline_after,
                    match_id=match.id if match else None,
                    suggestion=self._suggest(game, match, device),
                )
            )
        return sensors

    @staticmethod
    def _suggest(game, match: Match | None, device: StationDevice) -> Suggestion | None:
        if match is None or match.team_a_id is None or match.team_b_id is None or device.left_cups is None:
            return None
        sensed = sensed_result(game, device.left_cups, device.right_cups or 0)
        if sensed is None:
            return None
        winner, score_a, score_b = sensed
        return Suggestion(match.id, match.team_a_id if winner == "a" else match.team_b_id, score_a, score_b)

    async def _match_at(self, station_id: UUID) -> Match | None:
        """The match at the station right now: the station planner put it there and it has no result yet."""
        return (
            await self.db.execute(
                select(Match).where(Match.station_id == station_id, Match.on_station_at.is_not(None))
            )
        ).scalar_one_or_none()
