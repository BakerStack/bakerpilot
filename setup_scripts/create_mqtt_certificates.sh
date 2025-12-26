#!/usr/bin/env bash
set -e

# Check if we're in the repo root
if [ ! -d "mosquitto" ]; then
    echo "Error: mosquitto directory not found."
    echo "Please run this script from the repository root directory."
    exit 1
fi

# Save the starting directory
START_DIR=$(pwd)

CONFIG_DIR="mosquitto/config"
CERT_DIR="$CONFIG_DIR/certs"

mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

SUBJ="/C=SE/ST=Vastmanland/L=Vasteras/O=BakerPilot/OU=IoT/CN=bakerpilot-mqtt"

# CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes \
  -key ca.key \
  -sha256 -days 3650 \
  -subj "$SUBJ CA" \
  -out ca.crt

# Server key + CSR
openssl genrsa -out server.key 4096
openssl req -new \
  -key server.key \
  -subj "$SUBJ" \
  -out server.csr

# Server cert signed by CA
openssl x509 -req \
  -in server.csr \
  -CA ca.crt \
  -CAkey ca.key \
  -CAcreateserial \
  -out server.crt \
  -days 3650 \
  -sha256

# Workaround for permissions issue with Docker volume mounts on macOS
chmod 644 mosquitto/config/certs/*.key
 
