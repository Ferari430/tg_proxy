FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY src/ ./src/

COPY migrations/ ./migrations/
COPY alembic.ini .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Sessions mounted at runtime via volume, not baked in
VOLUME ["/app/sessions"]

ENTRYPOINT ["./entrypoint.sh"]
