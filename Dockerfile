FROM python:3.12-slim AS base
WORKDIR /usr/src/app

# Install and configure poetry
USER root

ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
RUN apt-get update && apt-get install -y curl && apt-get clean
RUN curl -sSL https://install.python-poetry.org | python -

RUN python -m venv /usr/src/app/.venv
ENV PATH="/opt/poetry/bin:/usr/src/app/.venv/bin:$PATH"

# Setup project
RUN mkdir serviceregistry && touch serviceregistry/__init__.py
COPY acapy-plugins/serviceregistry_protocol/pyproject.* ./
RUN poetry install --extras aca-py

RUN pip install textual

USER $user

FROM python:3.12-bullseye
WORKDIR /usr/src/app
COPY --from=base /usr/src/app/.venv /usr/src/app/.venv
ENV PATH="/usr/src/app/.venv/bin:$PATH"

ENV PYTHONUNBUFFERED 1

COPY acapy-plugins/serviceregistry_protocol/serviceregistry/ serviceregistry/
#COPY acapy-plugins/http3_transport/http3/ http3/

COPY agents ./agents

ENTRYPOINT ["python", "-m", "agents.discovery.main"]
