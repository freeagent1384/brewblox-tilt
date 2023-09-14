FROM python:3.11-bookworm as base

ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
ENV PIP_FIND_LINKS=/wheeley

COPY ./dist /app/dist

RUN set -ex \
    && mkdir /wheeley \
    && pip3 install --upgrade pip wheel \
    && pip3 wheel --wheel-dir=/wheeley -r /app/dist/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley /app/dist/*.tar.gz

FROM python:3.11-slim-bookworm
WORKDIR /app

COPY --from=base /wheeley /wheeley

RUN set -ex \
    && pip3 install --no-index --find-links=/wheeley brewblox-tilt \
    && pip3 freeze \
    && rm -rf /wheeley

ENTRYPOINT ["python3", "-m", "brewblox_tilt"]
