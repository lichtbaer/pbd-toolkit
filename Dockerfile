FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

ARG PIP_EXTRAS=""

COPY requirements.txt requirements-dev.txt setup.py README.md ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY . .

RUN if [ -n "$PIP_EXTRAS" ]; then \
        python -m pip install ".[${PIP_EXTRAS}]"; \
    else \
        python -m pip install .; \
    fi

ENTRYPOINT ["pii-toolkit"]
CMD ["--help"]
