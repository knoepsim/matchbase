"""A table controller without hardware: plays beer pong games and publishes the cups like a real one (docs/edge).

Usage (from apps/api, with a broker running, e.g. `docker compose -f docker-compose.dev.yml up mqtt`):
    uv run python -m scripts.simulate_table --device sim-1
    uv run python -m scripts.simulate_table --device sim-2 --cups 6 --interval 1 --flicker 0.1 --games 3

--flicker sends now and then a wrong count that is corrected with the next message: how a real sensor misreads,
for trying out what the core and the web app do with it.
"""
import argparse
import asyncio
import random
import sys
from urllib.parse import urlparse

import aiomqtt

from app.schemas.table_state import DEVICE_ID, TableState


class Controller:
    def __init__(self, client: aiomqtt.Client, topic: str):
        self.client, self.topic, self.seq = client, topic, 0

    async def publish(self, left: int, right: int) -> None:
        self.seq += 1
        state = TableState(left_cups=left, right_cups=right, seq=self.seq, sensor="sim")
        await self.client.publish(self.topic, state.model_dump_json(by_alias=True), qos=1, retain=True)
        print(f"{self.topic} #{self.seq}: {left} : {right}")


async def play(controller: Controller, cups: int, interval: float, flicker: float) -> None:
    left = right = cups
    await controller.publish(left, right)
    while left and right:
        await asyncio.sleep(interval * random.uniform(0.5, 1.5))  # NOSONAR: a simulation, no secret
        if random.random() < flicker:  # NOSONAR
            await controller.publish(max(left - 1, 0), right)  # a misread, corrected right away
            await asyncio.sleep(interval / 4)
            await controller.publish(left, right)
            continue
        if random.random() < 0.5:  # NOSONAR
            left -= 1
        else:
            right -= 1
        await controller.publish(left, right)


async def main(args: argparse.Namespace) -> None:
    broker = urlparse(args.broker)
    async with aiomqtt.Client(hostname=broker.hostname or "localhost", port=broker.port or 1883) as client:
        controller = Controller(client, f"{args.prefix}/{args.device}/state")
        for game in range(args.games):
            print(f"game {game + 1} of {args.games}")
            await play(controller, args.cups, args.interval, args.flicker)
            await asyncio.sleep(args.pause)


def device(value: str) -> str:
    if not DEVICE_ID.match(value):
        raise argparse.ArgumentTypeError("letters, digits, '-' and '_', at most 64")
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--device", type=device, default="sim-1")
    parser.add_argument("--broker", default="mqtt://localhost:1883")
    parser.add_argument("--prefix", default="tables")
    parser.add_argument("--cups", type=int, default=10)
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between two throws that hit")
    parser.add_argument("--flicker", type=float, default=0.0, help="probability of a misread per step")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--pause", type=float, default=10.0, help="seconds between two games")
    if sys.platform == "win32":  # paho needs add_reader, which only the selector loop has
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
    asyncio.run(main(parser.parse_args()))
