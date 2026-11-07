import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers import (
    admin,
    auth,
    events,
    invitations,
    invites,
    matches,
    results,
    roles,
    sensors,
    stations,
    teams,
    tournaments,
    users,
)
from app.schemas.sensor import NodeInfo
from app.services.table_listener import listen


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """On a Tournament Core (MQTT_URL set) the API listens to the table controllers while it runs."""
    listener = asyncio.create_task(listen(settings.mqtt_url, settings.mqtt_topic_prefix)) if settings.mqtt_url else None
    yield
    if listener:
        listener.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener


app = FastAPI(
    title="MatchBase API",
    description="Backend API für die Bierpong-Turnier-App",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    # development: also local IPs (phone in the same network); production: only the configured origins
    allow_origin_regex=None if settings.environment == "production" else "https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handler for consistent error responses
register_exception_handlers(app)

# Register routers
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(tournaments.router)
app.include_router(stations.router)
app.include_router(events.router)
app.include_router(roles.router)
app.include_router(invites.router)
app.include_router(invitations.router)
app.include_router(results.router)
app.include_router(matches.router)
app.include_router(sensors.router)


@app.get("/status", tags=["System"], summary="System Status")
def get_status():
    """Health-check endpoint."""
    return {"status": "online", "version": settings.app_version}


@app.get("/info", tags=["System"], summary="Wer antwortet", response_model=NodeInfo)
def get_info():
    """Cloud or MatchBase Edge: the web app asks this to find the edge at the venue (docs/edge)."""
    return NodeInfo(name="MatchBase", role=settings.node_role, node=settings.node_name, version=settings.app_version, api=1)
