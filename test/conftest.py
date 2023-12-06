"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import logging
from pathlib import Path
from typing import Generator

import pytest
from fastapi import FastAPI
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from pytest_docker.plugin import Services as DockerServices
from starlette.testclient import TestClient

from brewblox_tilt import app_factory, utils
from brewblox_tilt.models import ServiceConfig

LOGGER = logging.getLogger(__name__)


class TestConfig(ServiceConfig):
    """
    An override for ServiceConfig that only uses
    settings provided to __init__()

    This makes tests independent from env values
    and the content of .appenv
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


@pytest.fixture(autouse=True)
def config(monkeypatch: pytest.MonkeyPatch,
           docker_services: DockerServices,
           ) -> Generator[ServiceConfig, None, None]:
    cfg = TestConfig(
        debug=True,
        mqtt_host='localhost',
        mqtt_port=docker_services.port_for('mqtt', 1883),
    )
    monkeypatch.setattr(utils, 'get_config', lambda: cfg)
    yield cfg


@pytest.fixture(scope='session')
def docker_compose_file():
    return Path('./test/docker-compose.yml').resolve()


@pytest.fixture(autouse=True)
def setup_logging(config):
    app_factory.setup_logging(True)


@pytest.fixture
def app() -> FastAPI:
    """
    Override this in test modules to bootstrap required dependencies.

    IMPORTANT: This must NOT be an async fixture.
    Contextvars assigned in async fixtures are invisible to test functions.
    """
    app = FastAPI()
    return app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url='http://test') as c:
        yield c
