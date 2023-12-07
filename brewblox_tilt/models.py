from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.appenv',
        env_prefix='brewblox_',
        case_sensitive=False,
        json_schema_extra='ignore',
    )

    name: str = 'tilt'
    debug: bool = False

    mqtt_protocol: Literal['mqtt', 'mqtts'] = 'mqtt'
    mqtt_host: str = 'eventbus'
    mqtt_port: int = 1883

    lower_bound: float = 0.5
    upper_bound: float = 2
    scan_duration: float = 5
    inactive_scan_interval: float = 5
    active_scan_interval: float = 10
    simulate: list[str] | None = None


class TiltEvent(BaseModel):
    mac: str
    uuid: str
    major: int
    minor: int
    txpower: int
    rssi: int


class TiltTemperatureSync(BaseModel):
    type: str
    service: str
    block: str


class TiltMessage(BaseModel):
    name: str
    mac: str
    color: str
    data: dict
    sync: list[TiltTemperatureSync]
