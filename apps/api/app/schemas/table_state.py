"""The contract between a table controller and the Tournament Core (docs/edge/protocol.md).

A controller publishes on `{prefix}/{device_id}/state`. The topic names the device, the message only what it sees:
how many cups stand on each side. How it found out (RFID, camera, hall sensor) does not matter to the core.
"""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

DEVICE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class TableState(BaseModel):
    """What a table controller sees, version 1. Field names are camelCase on the wire (`leftCups`)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    v: Literal[1] = 1
    left_cups: int = Field(ge=0, le=99)
    right_cups: int = Field(ge=0, le=99)
    # counts up with every message of the controller: a repeated message (MQTT QoS 1) is recognised, gaps show losses
    seq: int | None = Field(default=None, ge=0)
    # the technique behind it ("rfid", "vision", "hall", "sim"): only recorded, for comparing them
    sensor: str | None = Field(default=None, max_length=20)


def device_of(topic: str, prefix: str) -> str | None:
    """The device id of a state topic (`tables/t3-rfid/state` -> `t3-rfid`), None for any other topic."""
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != prefix or parts[2] != "state" or not DEVICE_ID.match(parts[1]):
        return None
    return parts[1]
