FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY data/ /app/
COPY service/ /opt/meter/
RUN chmod +x /opt/meter/meterctl && ln -s /opt/meter/meterctl /usr/local/bin/meterctl
