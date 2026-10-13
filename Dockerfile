FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY rally ./rally
COPY adapters ./adapters
COPY workflows ./workflows
RUN pip install --no-cache-dir --no-deps .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RALLY_DB_PATH=/data/rally.db
COPY --from=build /usr/local /usr/local
RUN groupadd --gid 10001 rally && useradd --uid 10001 --gid rally --no-create-home rally && mkdir /data && chown rally:rally /data
WORKDIR /app
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["uvicorn", "rally.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--no-proxy-headers", "--limit-concurrency", "100", "--timeout-keep-alive", "5"]
