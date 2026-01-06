#!/usr/bin/env python3
import os
import sys
import ssl
import json
import time
import uuid
import traceback
import paho.mqtt.client as mqtt

TIMEOUT = int(os.getenv("SINK_TIMEOUT", "10"))
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
CERT_ROOT = os.getenv("CERT_ROOT", "/etc/ssl/bakerlabs")

CA_FILE = f"{CERT_ROOT}/ca/ca.pem"
CERT_FILE = f"{CERT_ROOT}/service/bakerprobe.pem"
KEY_FILE = f"{CERT_ROOT}/service/bakerprobe.key"

TOPIC = os.getenv("SINK_TOPIC", "test/+/metrics/#")
EXPECTED_NONCE = os.getenv("NONCE")

if not EXPECTED_NONCE:
    print("FATAL: NONCE not set. Sink cannot verify message identity.")
    sys.exit(2)

received = False
error = None


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        fail(f"MQTT connect failed with rc={rc}")
    print(f"Connected to broker at {MQTT_HOST}:{MQTT_PORT}")
    print(f"Subscribing to {TOPIC}")
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    global received
    try:
        payload = msg.payload.decode("utf-8")
        print(f"RX topic={msg.topic} payload={payload}")

        data = json.loads(payload)

        if "nonce" not in data:
            print("Ignoring message: no nonce")
            return

        if data["nonce"] != EXPECTED_NONCE:
            print(f"Ignoring message: nonce mismatch ({data['nonce']})")
            return

        print("PASS: Valid message received from device")
        received = True

    except Exception as e:
        print("FAIL: Error while parsing message")
        traceback.print_exc()
        client.disconnect()
        sys.exit(1)


def main():
    global error

    print("MQTT Smoke Test Sink")
    print("--------------------")
    print(f"Broker : {MQTT_HOST}:{MQTT_PORT}")
    print(f"CA     : {CA_FILE}")
    print(f"Cert   : {CERT_FILE}")
    print(f"Key    : {KEY_FILE}")
    print(f"Topic  : {TOPIC}")
    print(f"Nonce  : {EXPECTED_NONCE}")
    print(f"Timeout: {TIMEOUT}s")
    print("")

    try:
        client = mqtt.Client(protocol=mqtt.MQTTv5)
        client.on_connect = on_connect
        client.on_message = on_message

        client.tls_set(
            ca_certs=CA_FILE,
            certfile=CERT_FILE,
            keyfile=KEY_FILE,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )
        client.tls_insecure_set(False)

        client.connect(MQTT_HOST, MQTT_PORT)
        client.loop_start()

        start = time.time()
        while time.time() - start < TIMEOUT:
            if received:
                client.disconnect()
                print("PASS: Smoke test sink complete")
                sys.exit(0)
            time.sleep(0.1)

        fail("Timeout waiting for valid MQTT message")

    except ssl.SSLError as e:
        fail(f"TLS error: {e}")

    except ConnectionRefusedError:
        fail("Connection refused by broker")

    except Exception as e:
        print("FAIL: Unexpected error")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
