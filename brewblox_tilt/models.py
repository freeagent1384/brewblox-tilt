from typing import Optional

from brewblox_service.models import BaseServiceConfig


class ServiceConfig(BaseServiceConfig):
    lower_bound: float
    upper_bound: float
    active_scan_interval: float
    inactive_scan_interval: float
    simulate: Optional[list[str]]
