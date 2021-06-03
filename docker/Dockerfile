FROM python:3.7 as base

COPY ./dist /app/dist
COPY ./requirements.txt /app/requirements.txt

ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
ENV PIP_FIND_LINKS=/wheeley

RUN set -ex \
    && apt-get update \
    && apt-get install -yq \
        libbluetooth-dev \
    && mkdir /wheeley \
    && pip3 install --upgrade pip wheel \
    && pip3 wheel --wheel-dir=/wheeley -r /app/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley /app/dist/*

FROM python:3.7-slim
WORKDIR /app

ARG service_info=UNKNOWN
ENV SERVICE_INFO=${service_info}
ENV PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH}"

COPY --from=base /wheeley /wheeley

RUN set -ex \
    && apt-get update \
    && apt-get install -yq \
        libbluetooth-dev \
        libatlas-base-dev \
    && pip3 install --no-index --find-links=/wheeley brewblox-tilt \
    && rm -rf /wheeley \
    && pip3 freeze

ENTRYPOINT ["python3", "-m", "brewblox_tilt"]
