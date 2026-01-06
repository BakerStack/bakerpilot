#!/usr/bin/env python3
import os
import sys
import ssl
import json
import time
import traceback
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
CERT_ROOT = os.getenv("CERT_ROOT", "/etc/ssl/bakerlabs")
DEVICE = os.getenv("DEVICE")
TOPIC = os.getenv("TOPIC")
NONCE = os.getenv("NONCE")

if not DEVICE:
    print("FATAL: DEVICE not set")
    sys.exit(2)

if not TOPIC:
    print("FATAL: TOPIC not set")
    sys.exit(2)

if not NONCE:
    print("FATAL: NONCE not set")
    sys.exit(2)

CA_FILE = f"{CERT_ROOT}/ca/ca.pem"
CERT_FILE = f"{CERT_ROOT}/device/{DEVICE}.pem"
KEY_FILE = f"{CERT_ROOT}/device/{DEVICE}.key"

payload = {
    "device": DEVICE,
    "nonce": NONCE,
    "ts": int(time.time()),
    "value": 42.0
}

published = False

def fail(msg, code=1):
    print(f"FAIL: {msg}")
    sys.exit(code)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        fail(f"MQTT connect failed rc={rc}")
    print(f"Connected to {MQTT_HOST}:{MQTT_PORT}")
    client.publish(TOPIC, json.dumps(payload), qos=1)

def on_publish(client, userdata, mid):
    global published
    print("Publish acknowledged by broker")
    published = True
    client.disconnect()
import subprocess

def cert_info(path):
    try:
        out = subprocess.check_output(
            ["openssl", "x509", "-in", path, "-noout", "-subject", "-issuer", "-dates", "-serial"],
            text=True
        )
        return out.strip()
    except Exception as e:
        return f"<unable to read cert: {e}>"

def key_fingerprint(path):
    try:
        out = subprocess.check_output(
            ["openssl", "pkey", "-in", path, "-pubout"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        fp = subprocess.check_output(
            ["openssl", "sha256"],
            input=out,
            text=True
        )
        return fp.strip()
    except Exception:
        return "<unable to read key>"

def main():
    print("MQTT Smoke Test Sender")
    print("---------------------")
    print(f"Device : {DEVICE}")
    print(f"Broker : {MQTT_HOST}:{MQTT_PORT}")
    print(f"Topic  : {TOPIC}")
    print(f"Nonce  : {NONCE}")
    print("")

    print("Device certificate")
    print("------------------")
    print(cert_info(CERT_FILE))
    print(f"Key fingerprint: {key_fingerprint(KEY_FILE)}")
    print("")

    print("CA certificate")
    print("--------------")
    print(cert_info(CA_FILE))
    print("")


    try:
        client = mqtt.Client(protocol=mqtt.MQTTv5)
        client.on_connect = on_connect
        client.on_publish = on_publish

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
        while time.time() - start < 10:
            if published:
                print("PASS: Message published successfully")
                sys.exit(0)
            time.sleep(0.1)

        fail("Publish not acknowledged by broker", 3)

    except ssl.SSLError as e:
        fail(f"TLS error: {e}", 1)

    except ConnectionRefusedError:
        fail("Connection refused by broker", 2)

    except Exception:
        print("FAIL: Unexpected error")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
