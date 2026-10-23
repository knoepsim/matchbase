"""The Tournament Core listens to its table controllers over MQTT (docs/edge/protocol.md).

Only where MQTT_URL is set (the core at the venue); the cloud never starts it. `handle` is the whole logic and knows
nothing of MQTT, `listen` only carries the messages to it and reconnects when the broker is gone.
"""
import asyncio
import logging
from urllib.parse import urlparse

import aiomqtt
from pydantic import ValidationError

from app.core.database import async_session
from app.schemas.table_state import TableState, device_of
from app.services.sensor_service import SensorService

log = logging.getLogger(__name__)

RECONNECT_SECONDS = 3


async def handle(topic: str, payload: bytes | str, prefix: str) -> bool:
    """One message of the broker; False if it was not a valid state (it is logged and dropped, never raised)."""
    device_id = device_of(topic, prefix)
    if device_id is None:
        return False
    try:
        state = TableState.model_validate_json(payload)
    except ValidationError as error:
        log.warning("invalid table state from %s: %s", device_id, error.errors(include_url=False))
        return False
    try:
        async with async_session() as db:
            await SensorService(db).ingest(device_id, state)
            await db.commit()
    except Exception:  # a broken message or a database hiccup must not end the listener
        log.exception("table state from %s not stored", device_id)
        return False
    return True


async def listen(url: str, prefix: str) -> None:
    """Subscribe to the states of all controllers and hand them over, for as long as the API runs."""
    broker = urlparse(url)
    while True:
        try:
            async with aiomqtt.Client(
                hostname=broker.hostname or "localhost",
                port=broker.port or 1883,
                username=broker.username,
                password=broker.password,
                identifier="tournament-core",
            ) as client:
                await client.subscribe(f"{prefix}/+/state", qos=1)
                log.info("listening to table controllers on %s", broker.hostname)
                async for message in client.messages:
                    payload = message.payload if isinstance(message.payload, bytes | str) else b""
                    await handle(str(message.topic), payload, prefix)
        except NotImplementedError:
            # paho needs add_reader, which the Proactor event loop (Windows default) lacks: run the core on Linux
            log.error("MQTT needs a selector event loop; the table listener is off (run the core in Docker)")
            return
        except aiomqtt.MqttError as error:
            log.warning("MQTT broker not reachable (%s), retrying in %ss", error, RECONNECT_SECONDS)
            await asyncio.sleep(RECONNECT_SECONDS)
