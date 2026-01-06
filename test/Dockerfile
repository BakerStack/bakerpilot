FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openssl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    paho-mqtt \
    rich \
    python-dotenv

WORKDIR /app

COPY *.py ./

CMD ["python", "testbug.py"]
