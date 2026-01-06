FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    openssl \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    paho-mqtt \
    rich \
    requests

WORKDIR /app
COPY probe/ ./probe/

CMD ["python", "-c", "import time; print('BakerProbe ready'); time.sleep(10**9)"]
