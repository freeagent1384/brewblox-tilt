FROM python:3.9-bullseye as base

ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
ENV PIP_FIND_LINKS=/wheeley

COPY ./dist /app/dist

RUN set -ex \
    && mkdir /wheeley \
    && pip3 install --upgrade pip wheel \
    && pip3 wheel --wheel-dir=/wheeley -r /app/dist/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley /app/dist/*.tar.gz

FROM python:3.9-slim-bullseye
WORKDIR /app

COPY --from=base /wheeley /wheeley

RUN set -ex \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libbluetooth-dev \
        libatlas-base-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-index --find-links=/wheeley brewblox-tilt \
    && pip3 freeze \
    && rm -rf /wheeley

ENTRYPOINT ["python3", "-m", "brewblox_tilt"]
