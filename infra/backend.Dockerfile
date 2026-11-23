FROM python:3.14-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
