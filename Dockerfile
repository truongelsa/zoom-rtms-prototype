FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/
COPY src /app/src

RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

RUN mkdir -p /app/recordings /app/logs

EXPOSE 8000

CMD ["python", "-m", "zoom_rtms_local"]
