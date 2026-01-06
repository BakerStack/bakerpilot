# ANSI colors
GREEN=\033[1;32m
YELLOW=\033[1;33m
RED=\033[1;31m
NC=\033[0m


# Below should onle be done for rules other than help:
ifndef CERT_ROOT	
$(error CERT_ROOT is not set. Please set CERT_ROOT to the path of your certificates.)
endif
# Make sure ../bakerlabs-certs exists and have certificates
ifneq ("$(wildcard $(CERT_ROOT))","")
else
$(error Directory $(CERT_ROOT)/bakerlabs-certs does not exist. Please make sure the certificates are in place.)
endif

all: help

help:
	@echo ""
	@echo "Available commands:"
	@echo "----------------------------------------"
	@echo "${GREEN}make smoke-test-mqtt${NC}          - Run MQTT smoke test"

smoke-test-mqtt:
	python3 test/host/smoke-test-mqtt.py