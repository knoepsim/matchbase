from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.database import DbSession
from app.core.security import get_current_user
from app.models.tournament import Tournament
from app.models.tournament_role import TournamentRoleType
from app.models.user import User
from app.schemas.sensor import (
    DeviceBinding,
    DeviceResponse,
    StationSensorResponse,
    SuggestionResponse,
)
from app.services.role_service import RoleService
from app.services.sensor_service import SensorService
from app.services.tournament_service import get_accessible_tournament

router = APIRouter(tags=["Sensors"])


@router.get(
    "/devices",
    response_model=list[DeviceResponse],
    summary="Tisch-Controller auflisten",
    description="Alle Controller, die sich bei diesem Tournament Core gemeldet haben, mit ihrem letzten Stand. "
    "In der Cloud ist die Liste leer.",
)
async def list_devices(_: Annotated[User, Depends(get_current_user)], db: DbSession):
    return await SensorService(db).list_devices()


@router.get(
    "/tournaments/{tournament_id}/sensors",
    response_model=list[StationSensorResponse],
    summary="Sensorstand der Spielstätten",
    description="Was die Controller der Spielstätten gerade zählen, und das Ergebnis, das sich daraus ergibt, "
    "sobald das Spiel vorbei ist (Team A links). Für alle, die das Turnier sehen dürfen.",
)
async def list_station_sensors(tournament: Annotated[Tournament, Depends(get_accessible_tournament)], db: DbSession):
    return [
        StationSensorResponse(
            station_id=s.station_id,
            device_id=s.device.id,
            sensor=s.device.sensor,
            online=s.online,
            left_cups=s.device.left_cups,
            right_cups=s.device.right_cups,
            last_seen_at=s.device.last_seen_at,
            match_id=s.match_id,
            suggestion=SuggestionResponse(**vars(s.suggestion)) if s.suggestion else None,
        )
        for s in await SensorService(db).station_sensors(tournament.id)
    ]


@router.put(
    "/tournaments/{tournament_id}/stations/{station_id}/device",
    status_code=204,
    summary="Controller einer Spielstätte zuordnen",
    description="Der Controller zählt ab jetzt für diese Spielstätte (eine frühere Zuordnung endet). "
    "Nur Admin und Manager.",
)
async def bind_device(
    tournament_id: UUID,
    station_id: UUID,
    body: DeviceBinding,
    current_user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
):
    await RoleService(db).require_role(tournament_id, current_user.id, TournamentRoleType.MANAGER)
    await SensorService(db).bind(tournament_id, station_id, body.device_id)
    return Response(status_code=204)


@router.delete(
    "/tournaments/{tournament_id}/stations/{station_id}/device",
    status_code=204,
    summary="Controller von einer Spielstätte lösen",
    description="Nur Admin und Manager.",
)
async def unbind_device(
    tournament_id: UUID,
    station_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
):
    await RoleService(db).require_role(tournament_id, current_user.id, TournamentRoleType.MANAGER)
    await SensorService(db).bind(tournament_id, station_id, None)
    return Response(status_code=204)
