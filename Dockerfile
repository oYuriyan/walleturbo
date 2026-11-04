# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY --chown=10001:10001 requirements.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --require-hashes -r requirements.lock && \
    mkdir -p /run/walleturbo-parser && chown 10001:10001 /run/walleturbo-parser
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 web ./web
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]

FROM base AS test
USER root
COPY --chown=10001:10001 requirements-test.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --require-hashes -r requirements-test.lock
COPY --chown=10001:10001 tests ./tests
COPY --chown=10001:10001 pyproject.toml ./
USER 10001:10001
CMD ["pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS parser
CMD ["python", "-m", "app.pdf_worker"]
