import asyncio
import time
from pathlib import Path

from aiohttp import web
from beacontools import (BeaconScanner, BluetoothAddressType,
                         IBeaconAdvertisement, IBeaconFilter)
from beacontools.scanner import HCIVersion
from brewblox_service import brewblox_logger, features, mqtt, repeater

from brewblox_tilt import parser

LOGGER = brewblox_logger(__name__)

HCI_SCAN_INTERVAL_S = 30


def time_ms():
    return time.time_ns() // 1000000


class Broadcaster(repeater.RepeaterFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)

        config = app['config']
        self.name = config['name']
        self.inactive_scan_interval = max(config['inactive_scan_interval'], 0)
        self.active_scan_interval = max(config['active_scan_interval'], 0)
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'

        self.scanner = None
        self.parser = parser.EventDataParser(app)
        self.interval = 1
        self.prev_num_events = 0
        self.events: dict[str, parser.TiltEventData] = {}

    @property
    def scanner_active(self) -> bool:
        return self.scanner and self.scanner._mon.is_alive()

    async def on_event(self, mac: str, rssi: int, packet: IBeaconAdvertisement, info: dict):
        LOGGER.debug(f'Recv {mac=} {packet.uuid=}, {packet.major=}, {packet.minor=}')
        self.events[packet.uuid] = parser.TiltEventData(mac=mac,
                                                        uuid=packet.uuid,
                                                        major=packet.major,
                                                        minor=packet.minor,
                                                        txpower=packet.tx_power,
                                                        rssi=rssi)

    async def detect_device_id(self) -> int:
        bt_dir = Path('/sys/class/bluetooth')
        device_id: int = None
        LOGGER.info('Looking for Bluetooth adapter...')
        while device_id is None:
            hci_devices = sorted(f.name for f in bt_dir.glob('./hci*'))
            if hci_devices:
                device_id = int(hci_devices[0].removeprefix('hci'))
                LOGGER.info(f'Found Bluetooth adapter hci{device_id}')
            else:
                LOGGER.debug(f'No Bluetooth adapter available. Retrying in {HCI_SCAN_INTERVAL_S}s...')
                await asyncio.sleep(HCI_SCAN_INTERVAL_S)
        return device_id

    def apply_pi4_hack(self):
        # https://github.com/citruz/beacontools/issues/65
        model_file = Path('/sys/firmware/devicetree/base/model')
        if not model_file.exists():
            return
        content = model_file.read_text()
        if 'Pi 4' in content:
            LOGGER.info('Pi 4 detected. Applying Bluetooth version hack.')
            self.scanner._mon.get_hci_version = lambda: HCIVersion.BT_CORE_SPEC_4_2

    async def prepare(self):
        device_id = await self.detect_device_id()
        loop = asyncio.get_running_loop()
        self.scanner = BeaconScanner(
            lambda *args: asyncio.run_coroutine_threadsafe(self.on_event(*args), loop),
            bt_device_id=device_id,
            device_filter=[IBeaconFilter(uuid=uuid) for uuid in parser.TILT_COLOURS.keys()],
            scan_parameters={
                'address_type': BluetoothAddressType.PUBLIC,
            })
        self.apply_pi4_hack()
        self.scanner.start()

    async def shutdown(self, app: web.Application):
        if self.scanner:
            self.scanner.stop()
            self.scanner = None

    async def run(self):
        await asyncio.sleep(self.interval)

        if not self.scanner_active:
            LOGGER.error('Bluetooth scanner exited prematurely')
            raise web.GracefulExit(1)

        message = self.parser.parse(list(self.events.values()))
        self.events.clear()

        curr_num_events = len(message)
        prev_num_events = self.prev_num_events
        self.prev_num_events = curr_num_events

        # Adjust scan interval based on whether devices are detected or not
        if curr_num_events == 0 or curr_num_events < prev_num_events:
            self.interval = self.inactive_scan_interval
        else:
            self.interval = self.active_scan_interval

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
        for (colour, submessage) in message.items():
            await mqtt.publish(self.app,
                               f'{self.state_topic}/{colour}',
                               {
                                   'key': self.name,
                                   'type': 'Tilt.state',
                                   'colour': colour,
                                   'timestamp': timestamp,
                                   'data': submessage,
                               },
                               err=False,
                               retain=True)


def setup(app):
    features.add(app, Broadcaster(app))
