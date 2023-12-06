import time
from functools import lru_cache

from .models import ServiceConfig


@lru_cache
def get_config() -> ServiceConfig:  # pragma: no cover
    return ServiceConfig()


def time_ms():
    return time.time_ns() // 1000000
