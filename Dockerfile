FROM python:3.11-bookworm as base

ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
ENV PIP_FIND_LINKS=/wheeley

COPY ./dist /app/dist

RUN <<EOF
    set -ex

    mkdir /wheeley
    python3 -m venv .venv
    . .venv/bin/activate
    pip3 install --upgrade pip wheel
    pip3 wheel --wheel-dir=/wheeley -r /app/dist/requirements.txt
    pip3 wheel --wheel-dir=/wheeley /app/dist/*.tar.gz
EOF

FROM python:3.11-slim-bookworm
WORKDIR /app

COPY --from=base /wheeley /wheeley

RUN <<EOF
    set -ex

    apt-get update
    apt-get install -y --no-install-recommends \
        libopenblas-dev
    rm -rf /var/cache/apt/archives /var/lib/apt/lists

    python3 -m venv .venv
    . .venv/bin/activate
    pip3 install --no-index --find-links=/wheeley brewblox-tilt
    pip3 freeze
    rm -rf /wheeley
EOF

ENTRYPOINT . .venv/bin/activate; python3 -m brewblox_tilt
