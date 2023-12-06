#!/bin/env bash
set -euo pipefail

python3 ./parse_appenv.py "$@" >.appenv

exec uvicorn \
    --uds /run/dummy.sock \
    --factory \
    brewblox_tilt.app_factory:create_app
