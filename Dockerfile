FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN useradd --create-home appuser && mkdir -p /app/uploads && chown -R appuser:appuser /app
USER appuser
# Railway's injected PORT is 8080 for this service. Keep the image metadata in
# sync so Railway's public proxy targets the same port as Uvicorn.
EXPOSE 8080
CMD ["sh", "scripts/start-railway.sh"]
