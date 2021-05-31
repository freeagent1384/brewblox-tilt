import asyncio
import time
from typing import Any, Coroutine, List

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater, strex

from brewblox_tilt import blescan, parser

LOGGER = brewblox_logger(__name__)


def time_ms():
    return time.time_ns() // 1000000


async def _open_socket() -> Coroutine[None, None, Any]:
    try:
        return blescan.open_socket()

    except asyncio.CancelledError:
        raise
    except Exception as e:
        LOGGER.error(f'Error accessing bluetooth device: {strex(e)}')
        await asyncio.sleep(10)  # Avoid lockup caused by service reboots
        raise web.GracefulExit(1)


async def _scan_socket(sock) -> Coroutine[None, None, List[blescan.TiltEventData]]:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(blescan.scan, sock, 10)

    except asyncio.CancelledError:
        raise
    except Exception as e:
        LOGGER.error(
            f'Error accessing bluetooth device whilst scanning: {strex(e)}')
        raise web.GracefulExit(1)


class Broadcaster(repeater.RepeaterFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        self.sock: Any = None
        self.parser = parser.EventDataParser(app)

        config = app['config']
        self.name = config['name']
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'

    async def prepare(self):
        self.sock = await _open_socket()

    async def run(self):
        events = await _scan_socket(self.sock)
        message = self.parser.parse(events)

        if not message:
            return

        LOGGER.debug(message)

        # Publish history
        # Colours can share an event
        await mqtt.publish(self.app,
                           self.history_topic,
                           {
                               'key': self.name,
                               'data': message,
                           },
                           err=False)

        # Publish state
        # Publish individual colours separately
        # This lets us retain last published values for all colours
        timestamp = time_ms()
        for (colour, colour_data) in message.items():
            await mqtt.publish(self.app,
                               self.state_topic + f'/{colour}',
                               {
                                   'key': self.name,
                                   'type': 'Tilt.state',
                                   'colour': colour,
                                   'timestamp': timestamp,
                                   'data': colour_data,
                               },
                               err=False,
                               retain=True)


def setup(app):
    features.add(app, Broadcaster(app))
