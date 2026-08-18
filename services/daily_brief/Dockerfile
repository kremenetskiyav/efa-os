FROM python:3.13-slim

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY services/daily_brief/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services /app/services
COPY config/taxpayer.2026.json /app/config/taxpayer.2026.json

USER nobody
EXPOSE 8080
CMD ["python", "-m", "services.daily_brief.server"]
