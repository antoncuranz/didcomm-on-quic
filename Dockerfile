FROM ghcr.io/antoncuranz/aries-cloudagent-python:py3.12-latest

ENV ENABLE_PTVSD 0
ENV ENABLE_PYDEVD_PYCHARM 0
ENV PYDEVD_PYCHARM_HOST "host.docker.internal"
ENV ACAPY_DEBUG_WEBHOOKS 1

RUN pip install --no-cache-dir textual

ADD agents ./agents

ENTRYPOINT ["python", "-m", "agents.discovery.main"]
