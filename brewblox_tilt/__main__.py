from brewblox_service import mqtt, scheduler, service

from brewblox_tilt import broadcaster, broadcaster_sim
from brewblox_tilt.models import ServiceConfig


def create_parser():
    parser = service.create_parser('tilt')

    parser.add_argument('--lower-bound',
                        help='Lower bound of acceptable SG values. '
                        'Out-of-bounds measurement values will be discarded. [%(default)s]',
                        type=float,
                        default=0.5)
    parser.add_argument('--upper-bound',
                        help='Upper bound of acceptable SG values. '
                        'Out-of-bounds measurement values will be discarded. [%(default)s]',
                        type=float,
                        default=2)
    parser.add_argument('--inactive-scan-interval',
                        help='Interval (in seconds) between broadcasts while searching for devices. [%(default)s]',
                        type=float,
                        default=5)
    parser.add_argument('--active-scan-interval',
                        help='Interval (in seconds) between broadcasts when devices are active. [%(default)s]',
                        type=float,
                        default=10)
    parser.add_argument('--simulate',
                        nargs='*',
                        help='Start in simulation mode. '
                        'This will not attempt to read Bluetooth devices, but will publish random values.'
                        'The values for this argument will be used as color',
                        default=None)

    # Assumes a default configuration of running with --net=host
    parser.set_defaults(mqtt_protocol='wss', mqtt_host='172.17.0.1')
    return parser


def main():
    parser = create_parser()
    config = service.create_config(parser, model=ServiceConfig)
    app = service.create_app(config)

    async def setup():
        scheduler.setup(app)
        mqtt.setup(app)

        if config.simulate is not None:
            broadcaster_sim.setup(app)
        else:
            broadcaster.setup(app)

    # We have no meaningful REST API, so we set listen_http to False
    service.run_app(app, setup(), listen_http=False)


if __name__ == '__main__':
    main()
