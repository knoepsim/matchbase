"""Table controllers on a Tournament Core: their messages, the binding to stations and the suggested result."""
import json
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select

from app.games import sensed_result
from app.models.station_device import SensorReading
from app.models.tournament import Game
from app.schemas.table_state import device_of
from app.services import table_listener
from tests.test_match_stations import Ctx, _tournament


@pytest.fixture(autouse=True)
def test_database(session_factory):
    """The listener opens its own sessions: on the test database."""
    with patch.object(table_listener, "async_session", session_factory):
        yield


async def send(device: str, **state) -> bool:
    """A message of a controller as it arrives from the broker."""
    payload = json.dumps({"leftCups": 6, "rightCups": 6, **state})
    return await table_listener.handle(f"tables/{device}/state", payload, "tables")


@pytest_asyncio.fixture
async def ctx(async_client: AsyncClient) -> Ctx:
    return await _tournament(async_client, 4, 2)


async def bind(ctx: Ctx, station: int, device: str, headers: dict | None = None):
    station_id = (await ctx.stations())[station]["id"]
    return await ctx.client.put(
        f"/tournaments/{ctx.tid}/stations/{station_id}/device", json={"device_id": device}, headers=headers or ctx.admin
    )


async def sensors(ctx: Ctx) -> list[dict]:
    return (await ctx.client.get(f"/tournaments/{ctx.tid}/sensors", headers=ctx.admin)).json()


def test_the_topic_names_the_device():
    assert device_of("tables/t3-rfid/state", "tables") == "t3-rfid"
    assert device_of("tables/t3/health", "tables") is None
    assert device_of("other/t3/state", "tables") is None
    assert device_of("tables/a b/state", "tables") is None


def test_beer_pong_ends_when_one_side_has_no_cups_left_and_football_never_by_sensor():
    assert sensed_result(Game.BEERPONG, 3, 0) == ("a", 3, 0)
    assert sensed_result(Game.BEERPONG, 0, 2) == ("b", 0, 2)
    assert sensed_result(Game.BEERPONG, 2, 1) is None  # still running
    assert sensed_result(Game.BEERPONG, 0, 0) is None  # nothing on the table
    assert sensed_result(Game.BEERPONG, 12, 0) is None  # more cups than the game has
    assert sensed_result(Game.FOOTBALL, 3, 0) is None


@pytest.mark.asyncio
async def test_a_controller_appears_with_its_first_message(ctx: Ctx):
    assert await send("t1-rfid", sensor="rfid")

    devices = (await ctx.client.get("/devices", headers=ctx.admin)).json()
    assert [(d["id"], d["sensor"], d["station_id"], d["left_cups"]) for d in devices] == [("t1-rfid", "rfid", None, 6)]
    assert await sensors(ctx) == []  # not bound: it counts for no station


@pytest.mark.asyncio
async def test_invalid_messages_are_dropped(ctx: Ctx):
    assert not await table_listener.handle("tables/t1/state", b"not json", "tables")
    assert not await table_listener.handle("tables/t1/state", b'{"leftCups": -1, "rightCups": 2}', "tables")
    assert not await table_listener.handle("tables/t1/config", b'{"leftCups": 1, "rightCups": 2}', "tables")
    assert (await ctx.client.get("/devices", headers=ctx.admin)).json() == []


@pytest.mark.asyncio
async def test_a_bound_controller_counts_for_the_match_at_its_station_and_suggests_the_result(ctx: Ctx):
    await send("t1")
    assert (await bind(ctx, 0, "t1")).status_code == 204
    match = next(m for m in await ctx.round(1) if m["station_name"] == "Tisch 1")

    await send("t1", leftCups=4, rightCups=2)
    [running] = await sensors(ctx)
    assert (running["device_id"], running["online"], running["match_id"]) == ("t1", True, match["id"])
    assert (running["left_cups"], running["right_cups"], running["suggestion"]) == (4, 2, None)

    await send("t1", leftCups=3, rightCups=0)
    [ended] = await sensors(ctx)
    assert ended["suggestion"] == {
        "match_id": match["id"], "winner_team_id": match["team_a_id"], "score_a": 3, "score_b": 0,
    }

    # the referee takes it over: a result like any other, marked as coming from the sensor
    resp = await ctx.client.post(
        f"/matches/{match['id']}/results",
        json={**{k: ended["suggestion"][k] for k in ("winner_team_id", "score_a", "score_b")}, "source": "sensor"},
        headers=ctx.admin,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["source"] == "sensor"
    # the next match comes to the station: the old counts suggest nothing for it
    [after] = await sensors(ctx)
    assert after["match_id"] != match["id"]
    assert after["suggestion"] is None


@pytest.mark.asyncio
async def test_repetitions_and_heartbeats_are_no_new_readings(ctx: Ctx, session_factory):
    await send("t1", seq=1)
    await send("t1", seq=1, leftCups=5)  # the same message again (QoS 1): dropped
    await send("t1", seq=2)  # heartbeat, same counts
    await send("t1", seq=3, leftCups=5)

    async with session_factory() as db:
        assert (await db.execute(select(func.count()).select_from(SensorReading))).scalar_one() == 2


@pytest.mark.asyncio
async def test_a_controller_moves_to_the_station_it_is_bound_to_last(ctx: Ctx):
    await send("t1")
    await bind(ctx, 0, "t1")
    await bind(ctx, 1, "t1")

    [moved] = await sensors(ctx)
    assert moved["station_id"] == (await ctx.stations())[1]["id"]

    station_id = moved["station_id"]
    resp = await ctx.client.delete(f"/tournaments/{ctx.tid}/stations/{station_id}/device", headers=ctx.admin)
    assert resp.status_code == 204
    assert await sensors(ctx) == []


@pytest.mark.asyncio
async def test_only_organizers_bind_and_only_known_controllers(ctx: Ctx):
    await send("t1")
    with patch("app.services.auth_service.generate_sms_code", return_value="123456"):
        phone = "+4915200000099"
        await ctx.client.post("/auth/request-code", json={"phone_number": phone})
        token = (await ctx.client.post("/auth/verify", json={"phone_number": phone, "code": "123456"})).json()
    stranger = {"Authorization": f"Bearer {token['access_token']}"}

    assert (await bind(ctx, 0, "t1", stranger)).status_code == 403
    assert (await bind(ctx, 0, "unknown")).status_code == 404
    assert (await bind(ctx, 0, "no spaces")).status_code == 422


@pytest.mark.asyncio
async def test_info_says_who_answers(async_client: AsyncClient):
    info = (await async_client.get("/info")).json()
    assert (info["name"], info["role"], info["api"]) == ("MatchBase", "cloud", 1)
