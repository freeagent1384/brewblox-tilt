import asyncio
import json
import time
from uuid import UUID

from aiohttp import web
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from brewblox_service import brewblox_logger, features, mqtt, repeater
from construct import Array, Byte, Const, Int8sl, Int16ub, Struct
from construct.core import ConstError

from brewblox_tilt import const, parser
from brewblox_tilt.models import ServiceConfig

APPLE_VID = 0x004C
BEACON_STRUCT = Struct(
    'type_length' / Const(b'\x02\x15'),
    'uuid' / Array(16, Byte),
    'major' / Int16ub,
    'minor' / Int16ub,
    'tx_power' / Int8sl,
)


LOGGER = brewblox_logger(__name__)


def time_ms():
    return time.time_ns() // 1000000


class Broadcaster(repeater.RepeaterFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)

        config: ServiceConfig = app['config']
        self.name = config.name
        self.scan_duration = max(config.scan_duration, 1)
        self.inactive_scan_interval = max(config.inactive_scan_interval, 0)
        self.active_scan_interval = max(config.active_scan_interval, 0)
        self.state_topic = f'{config.state_topic}/{self.name}'
        self.history_topic = f'{config.history_topic}/{self.name}'
        self.names_topic = f'brewcast/tilt/{self.name}/names'

        self.scanner = BleakScanner(self.device_callback)
        self.parser = parser.EventDataParser(app)
        self.scan_interval = 1
        self.prev_num_messages = 0
        self.events: dict[str, parser.TiltEvent] = {}

    def device_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        try:
            mac = device.address
            apple_data = advertisement_data.manufacturer_data[APPLE_VID]
            packet = BEACON_STRUCT.parse(apple_data)
            uuid = str(UUID(bytes=bytes(packet.uuid)))

            if uuid not in const.TILT_UUID_COLORS.keys():
                return

            LOGGER.debug(f'Recv {mac=} {uuid=}, {packet.major=}, {packet.minor=}')
            self.events[mac] = parser.TiltEvent(mac=mac,
                                                uuid=uuid,
                                                major=packet.major,
                                                minor=packet.minor,
                                                txpower=packet.tx_power,
                                                rssi=advertisement_data.rssi)

        except KeyError:
            pass  # Apple vendor ID not found
        except ConstError:
            pass  # Not an iBeacon

    async def on_names_change(self, topic: str, payload: str):
        self.parser.apply_custom_names(json.loads(payload))

    async def prepare(self):
        await mqtt.listen(self.app, self.names_topic, self.on_names_change)
        await mqtt.subscribe(self.app, self.names_topic)

    async def shutdown(self, app: web.Application):
        await mqtt.unsubscribe(app, self.names_topic)
        await mqtt.unlisten(app, self.names_topic, self.on_names_change)

    async def run(self):
        await asyncio.sleep(self.scan_interval)

        async with self.scanner:
            await asyncio.sleep(self.scan_duration)

        messages = self.parser.parse(list(self.events.values()))
        self.events.clear()

        curr_num_messages = len(messages)
        prev_num_messages = self.prev_num_messages
        self.prev_num_messages = curr_num_messages

        # Adjust scan interval based on whether devices are detected or not
        if curr_num_messages == 0 or curr_num_messages < prev_num_messages:
            self.scan_interval = self.inactive_scan_interval
        else:
            self.scan_interval = self.active_scan_interval

        # Always broadcast a presence message
        # This will make the service show up in the UI even without active Tilts
        await mqtt.publish(self.app,
                           self.state_topic,
                           json.dumps({
                               'key': self.name,
                               'type': 'Tilt.state.service',
                               'timestamp': time_ms(),
                           }),
                           err=False,
                           retain=True)

        if not messages:
            return

        LOGGER.debug(messages)

        # Publish history
        # Devices can share an event
        await mqtt.publish(self.app,
                           self.history_topic,
                           json.dumps({
                               'key': self.name,
                               'data': {
                                   msg.name: msg.data
                                   for msg in messages
                               },
                           }),
                           err=False)

        # Publish state
        # Publish individual devices separately
        # This lets us retain last published value if a device stops publishing
        timestamp = time_ms()
        for msg in messages:
            await mqtt.publish(self.app,
                               f'{self.state_topic}/{msg.color}/{msg.mac}',
                               json.dumps({
                                   'key': self.name,
                                   'type': 'Tilt.state',
                                   'timestamp': timestamp,
                                   'color': msg.color,
                                   'mac': msg.mac,
                                   'name': msg.name,
                                   'data': msg.data,
                               }),
                               err=False,
                               retain=True)

            for sync in msg.sync:
                if sync.type == 'TempSensorExternal':
                    await mqtt.publish(self.app,
                                       'brewcast/spark/blocks/patch',
                                       json.dumps({
                                           'id': sync.block,
                                           'serviceId': sync.service,
                                           'type': 'TempSensorExternal',
                                           'data': {
                                               'setting[degC]': msg.data['temperature[degC]'],
                                           },
                                       }),
                                       err=False)


def setup(app):
    features.add(app, Broadcaster(app))
