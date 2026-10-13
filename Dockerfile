FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml /app/
COPY rally /app/rally
COPY web /app/web
RUN pip install --no-cache-dir .
RUN mkdir -p /data
ENV RALLY_DB_PATH=/data/rally.db
EXPOSE 8080
CMD ["uvicorn", "rally.app:app", "--host", "0.0.0.0", "--port", "8080"]
