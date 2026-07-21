FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

ARG PIP_EXTRAS=""

COPY requirements.txt requirements-dev.txt pyproject.toml README.md ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY . .

RUN if [ -n "$PIP_EXTRAS" ]; then \
        python -m pip install ".[${PIP_EXTRAS}]"; \
    else \
        python -m pip install .; \
    fi

RUN groupadd --system --gid 1000 toolkit && \
    useradd --system --uid 1000 --gid toolkit --create-home --shell /usr/sbin/nologin toolkit && \
    mkdir -p /output /data /config /cache/hf && \
    chown -R toolkit:toolkit /app /output /data /config /cache/hf

USER toolkit

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pbd-toolkit doctor || exit 1

ENTRYPOINT ["pbd-toolkit"]
CMD ["--help"]
