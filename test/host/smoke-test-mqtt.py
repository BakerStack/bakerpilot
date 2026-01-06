#!/usr/bin/env python3
import subprocess
import time
import os
import sys
import uuid

DEBUG = os.getenv("DEBUG", "") != ""


# Terminal colors
class colors:
    OKGREEN = "\033[92m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"

CERT_REPO = "../bakerlabs-certs"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEVICE = "testbug-1"
TOPIC = "test/testbug-1/metrics/temp"
TIMEOUT = 15

verdicts = []  # ordered list of (name, bool)


def run(cmd, cwd=None, capture=False):
    if DEBUG:
        print(f"> {cmd}")

    if DEBUG or capture:
        return subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            env=os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    else:
        return subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            env=os.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def wait_for_tls():
    for _ in range(30):
        r = run(
            "openssl s_client -connect localhost:8883 -CAfile ${CERT_ROOT}/ca/ca.pem -servername mosquitto </dev/null",
            capture=True,
        )
        if r.stdout and "Verify return code: 0" in r.stdout:
            return True
        time.sleep(1)
    return False


def run_sink(nonce):
    return subprocess.Popen(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            f"NONCE={nonce}",
            "-e",
            f"SINK_TOPIC={TOPIC}",
            "bakerprobe",
            "python3",
            "/app/device/smoke-test-mqtt-sink.py",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def run_sender(nonce):
    r = run(
        f"docker compose exec -T "
        f"-e NONCE={nonce} "
        f"-e DEVICE={DEVICE} "
        f"-e TOPIC={TOPIC} "
        f"{DEVICE} python3 /app/device/smoke-test-mqtt-send.py",
        cwd=PROJECT_ROOT,
        capture=DEBUG,  # capture so we can print it in DEBUG
    )
    if DEBUG and getattr(r, "stdout", None):
        print(r.stdout)
    return r


def passfail(name, ok):
    verdicts.append((name, ok))


def colorize(ok):
    return (
        f"{colors.OKGREEN}PASS{colors.ENDC}"
        if ok
        else f"{colors.FAIL}FAIL{colors.ENDC}"
    )


def print_results():
    print("\nMQTT PKI Smoke Test Results\n")
    width = max(len(name) for name, _ in verdicts) + 4 if verdicts else 40
    for name, ok in verdicts:
        print(f"{name:<{width}} {colorize(ok)}")
    print()


def main():
    run("docker compose up -d", cwd=PROJECT_ROOT)

    if not wait_for_tls():
        passfail("TLS ready", False)
        print_results()
        sys.exit(1)

    # -----------------------
    # Positive test (CA0)
    # -----------------------
    nonce = uuid.uuid4().hex
    sink = run_sink(nonce)
    time.sleep(1)

    r = run_sender(nonce)

    out = sink.communicate(timeout=TIMEOUT)[0]
    if DEBUG:
        print(out)

    pos_send = r.returncode == 0
    pos_recv = "PASS" in out

    passfail("Sending with correct PKI", pos_send)
    passfail("Receiving with correct PKI", pos_recv)

    # -----------------------
    # Rotate CA (CA1) + rotate service certs so mosquitto cert + trust are CA1
    # Then restart mosquitto + bakerprobe so sink can connect with CA1
    # -----------------------
    run("make dev-ca-rotate", cwd=CERT_REPO)
    run("make dev-service-rotate", cwd=CERT_REPO)

    run("docker compose restart mosquitto", cwd=PROJECT_ROOT)
    run("docker compose restart bakerprobe", cwd=PROJECT_ROOT)
    time.sleep(5)

    # -----------------------
    # Negative test (devices still CA0) must fail to publish
    # -----------------------
    nonce = uuid.uuid4().hex
    sink = run_sink(nonce)
    time.sleep(1)

    r = run_sender(nonce)

    out = sink.communicate(timeout=TIMEOUT)[0]
    if DEBUG:
        print(out)

    neg_send = r.returncode != 0
    neg_recv = "PASS" not in out

    passfail("Cannot send with invalid CA", neg_send)
    passfail("Cannot receive with invalid CA", neg_recv)

    # -----------------------
    # Reprovision devices to CA1, restart device containers, positive again
    # -----------------------
    run("make dev-device-rotate", cwd=CERT_REPO)

    run(f"docker compose restart {DEVICE}", cwd=PROJECT_ROOT)
    time.sleep(5)

    nonce = uuid.uuid4().hex
    sink = run_sink(nonce)
    time.sleep(1)

    r = run_sender(nonce)

    out = sink.communicate(timeout=TIMEOUT)[0]
    if DEBUG:
        print(out)

    pos2_send = r.returncode == 0
    pos2_recv = "PASS" in out

    passfail("Sending with renewed PKI", pos2_send)
    passfail("Receiving with renewed PKI", pos2_recv)

    print_results()

    run("docker compose down", cwd=PROJECT_ROOT)
    time.sleep(2)

    if not all(ok for _, ok in verdicts):
        sys.exit(1)

if __name__ == "__main__":
    main()