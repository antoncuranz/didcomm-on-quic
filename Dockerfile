FROM python:3.12-slim AS base
WORKDIR /usr/src/app

ARG DISABLE_DIDDOC_CACHE=false

# Install and configure poetry
USER root

ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
RUN apt-get update && apt-get install -y curl patch && apt-get clean
RUN curl -sSL https://install.python-poetry.org | python -

RUN python -m venv /usr/src/app/.venv
ENV PATH="/opt/poetry/bin:/usr/src/app/.venv/bin:$PATH"

# Setup project
RUN mkdir serviceregistry && touch serviceregistry/__init__.py
COPY acapy-plugins/pyproject.* ./
RUN poetry install --extras aca-py

RUN pip install textual

# apply stupid patch
COPY disable-connection-cache.patch ./
RUN patch -u .venv/lib/python3.12/site-packages/aries_cloudagent/connections/base_manager.py -i disable-connection-cache.patch

COPY disable-diddoc-cache.patch ./
RUN if [ "$DISABLE_DIDDOC_CACHE" = "true" ]; then \
        patch -u .venv/lib/python3.12/site-packages/aries_cloudagent/resolver/base.py -i disable-diddoc-cache.patch; \
    fi

USER $user

FROM python:3.12-bullseye
WORKDIR /usr/src/app
COPY --from=base /usr/src/app/.venv /usr/src/app/.venv
ENV PATH="/usr/src/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED 1
ENV TERM xterm-256color
ENV DISPLAY host.docker.internal:0

RUN rm /var/lib/dpkg/info/libc-bin.*
RUN apt-get update && apt-get install -y mpv && apt-get clean

COPY acapy-plugins ./acapy-plugins
COPY agents ./agents
COPY wallets /root/.aries_cloudagent/wallet

COPY stream ./stream
COPY certs ./certs
RUN mkdir recvd logs

ENTRYPOINT ["python", "-m"]
