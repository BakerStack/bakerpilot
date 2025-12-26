# BakerStack Backend Bring-Up Test Plan (A/B)

## 1. Purpose

This document defines a hands-on bring-up and validation procedure for the BakerStack backend telemetry stack:

- Mosquitto (MQTT broker)
- Telegraf (ingestion)
- InfluxDB 1.8 (storage)
- Grafana (visualization)

The plan is split into two variants:

- **Variant A (Backend-host validation)**: You SSH into the backend host and validate the full chain locally, including TLS on MQTT.
- **Variant B (Edge validation)**: You validate only the remote client boundary (ESP32 over MQTT/TLS). Everything behind Mosquitto is assumed correct if Variant A passes.

The intent is fast fault isolation with clear pass/fail criteria and explicit commands.

---

## 2. System under test

### 2.1 Data flow

```
Edge device (ESP32) -> MQTT/TLS (Mosquitto) -> Telegraf -> InfluxDB -> Grafana
```

### 2.2 Repository layout (relevant parts)

Example on the Raspberry Pi:

```
mosquitto/
  config/
    certs/          (NOT in git)
      ca.crt
      ca.key
      server.crt
      server.key
      ...
    mosquitto.conf  (in git)
    passwd          (NOT in git)
  data/             (NOT in git)
  log/              (NOT in git)

telegraf/telegraf.conf         (in git)
grafana/provisioning/...       (in git)
docker-compose.yml             (in git)
setup_scripts/...              (in git; secrets and cert generation described)
```

### 2.3 Security model

- MQTT is intended to be accessed remotely only via TLS (typically port **8883**; some deployments may use a custom TLS port such as **1888**).
- Plain MQTT (1883) may exist for local-only use, but should not be exposed externally.
- Operational access to the host is performed via SSH.

---

## 3. Prerequisites

### 3.1 On the backend host (Developer machine or deployment target§)

- Docker and docker compose installed
- Shell access via SSH
- Tools available on host (recommended):
  - `mosquitto_pub`, `mosquitto_sub` (MQTT client utilities)
  - `curl`

If `mosquitto_pub` is not installed on the host, install it (Debian/Ubuntu example):

```bash
sudo apt-get update
sudo apt-get install -y mosquitto-clients openssl curl
```
or if you run on mac

```bash
brew install mosquitto openssl
```

### 3.2 Environment and secrets

You must have:

- `mosquitto/config/passwd` present (broker auth)
- `mosquitto/config/certs/*` present (TLS CA and server certs)

 These are not committed to git and are created per installation.

---
### 3.3 Python Environment
To run the test scripts in python you need 

```bash
conda env create -f environment.yml
conda activate bakerpilot-test
````

## 4. Common operational commands

### 4.1 Start and check the stack

From the repo root on the backend host:

```bash
docker compose up -d
docker ps
```

Expected: containers are running, no restart loops.
### 3.4 Certificates and initial users
Run the script `bakerpilot/setup_scripts/mqtt_cert_and_user_setup.sh` to prepare mqtt certificates if you are starting from a clean system or setting up a developer machine. 

### 4.2 Logs for fast triage

```bash
docker logs mosquitto --tail 200
docker logs telegraf --tail 200
docker logs influxdb --tail 200
docker logs grafana --tail 200
```

---

## 5. Variant A: Backend-host validation (SSH local), including MQTT/TLS

### 5.1 Goal

Prove, on the backend host, that:

1. Mosquitto is listening on the MQTT/TLS port and presents the expected server certificate
2. A client can publish and subscribe via TLS
3. Telegraf consumes MQTT messages and writes to InfluxDB
4. Data is queryable from InfluxDB
5. Data is visible in Grafana (basic verification)

If Variant A passes, the backend and TLS configuration are correct. Variant B then only needs to validate the edge device connectivity and TLS stack.

---

### 5.2 Identify ports and TLS material paths

Assumptions based on your layout:

- TLS CA: `mosquitto/config/certs/ca.crt`
- Server cert: `mosquitto/config/certs/server.crt`
- Server key: `mosquitto/config/certs/server.key`
- MQTT/TLS port: **8883** (or **1888**, depending on your configuration)

Confirm what port Mosquitto listens on by inspecting `mosquitto.conf`:

```bash
sed -n '1,200p' mosquitto/config/mosquitto.conf
```

Look for directives such as `listener 8883` and `cafile`, `certfile`, `keyfile`, and authentication settings.

---

### 5.3 Step A1: Verify Mosquitto is listening on the TLS port

Option 1 (socket check if you have ss istalled):

```bash
sudo ss -lntp | grep -E ':(8883|1888)\b'
```

Expected: a listener exists on the TLS port.

Option 2 (container port mapping check):

```bash
docker port mosquitto
```

Expected: port mapping includes the TLS port.

---

### 5.4 Step A2: Validate TLS handshake and server certificate presentation

Use OpenSSL from the host:

```bash
openssl s_client -connect localhost:8883 -CAfile mosquitto/config/certs/ca.crt -servername localhost
```

If you use port 1888 instead:

```bash
openssl s_client -connect localhost:1888 -CAfile mosquitto/config/certs/ca.crt -servername localhost
```

Expected:

- Verification is successful (look for `Verify return code: 0 (ok)`).
- The certificate chain corresponds to your CA.

If this fails, stop and fix TLS config before continuing.

---

### 5.5 Step A3: MQTT/TLS subscribe and publish (local loopback)

Open terminal 1 (subscriber):

```bash
mosquitto_sub \
  -h localhost -p 8883 \
  --cafile mosquitto/config/certs/ca.crt \
  -u <mqtt_user> -P <mqtt_password> \
  -t "bringup/#" -d
```

Terminal 2 (publisher):

```bash
mosquitto_pub \
  -h localhost -p 8883 \
  --cafile mosquitto/config/certs/ca.crt \
  -u <mqtt_user> -P <mqtt_password> \
  -t "bringup/test" -m "hello_tls" -d
```

Expected:

- Subscriber receives `hello_tls`.
- No TLS errors.
- No auth errors.

Notes:
- This uses only CA validation (server-auth). If you later enable mTLS (client certs), extend the command with `--cert` and `--key`.

If your deployment uses port 1888, replace `-p 8883` with `-p 1888`.

---

### 5.6 Step A4: Validate Telegraf is connected and ingesting MQTT

#### 5.6.1 Confirm Telegraf config points to Mosquitto and InfluxDB

```bash
sed -n '1,260p' telegraf/telegraf.conf
```

Confirm:

- `[[inputs.mqtt_consumer]]` points to Mosquitto using the correct scheme and port (TLS)
- `[[outputs.influxdb]]` points to InfluxDB at `http://influxdb:8086`



#### Try the non TLS endpoint that is the internal one (never open this port to the outside)


```bash
 mosquitto_pub -h localhost -p 1883 -t "test/device01/metrics/temp" -m '{"value":23.7}'
```

Go to influx db and check if we got anything
```bash
  docker exec -it influxdb influx
  use telemetry
  show measurements 
    Using database telemetry
  > show measurements
  name: measurements
  name
  ----
  cpu
  disk
  diskio
  mem
  net
  system
  uns_metric
  > select * from uns_metric
  name: uns_metric
  time                asset    domain mqtt_topic                 signal subsystem value
  ----                -----    ------ ----------                 ------ --------- -----
  1766765081238480694 device01 test   test/device01/metrics/temp temp   metrics   23.7
```

#### 5.6.2 Publish a deterministic test message for Telegraf to ingest

Choose a topic that Telegraf subscribes to (adjust the topic to match your config). Example:

```bash
mosquitto_pub \
  -h localhost -p 8883 \
  --cafile mosquitto/config/certs/ca.crt \
  -u "$MOSQUITTO_USERNAME" -P "$MOSQUITTO_PASSWORD" \
  -t "test/device01/metrics/temp" -m '{"value":23.7}'"

```

Expected:

- No publish errors
- Telegraf logs show subscription and write activity (optional check):

```bash
docker logs telegraf --tail 200
```

---

### 5.7 Step A5: Verify data landed in InfluxDB

Enter the InfluxDB CLI:

```bash
docker exec -it influxdb influx
```

In the Influx shell:

```sql
SHOW DATABASES
```

Select your database (example: `telemetry`):

```sql
USE telemetry
SHOW MEASUREMENTS
```

Expected: at least one measurement created by Telegraf once messages are ingested.

If you know the measurement name, query recent points. Example:

```sql
SELECT * FROM mqtt_consumer ORDER BY time DESC LIMIT 10
```

If you do not know the measurement name, list measurements and pick the relevant one.

Pass criteria:

- Your test message is represented in the measurement (fields and tags depend on your Telegraf parsing).

---

### 5.8 Step A6: Basic Grafana verification

Open Grafana (locally on the host via browser, or via SSH tunnel):

- URL: `http://<backend-host>:3000` (or `http://localhost:3000` if tunneled)
- Log in with your configured admin user

Verify:

1. InfluxDB data source exists and is healthy.
2. In Explore, a query against the measurement returns recent points.
3. Any provisioned dashboard loads without datasource errors.

Pass criteria:

- Data is queryable and visible.

---

### 5.9 Variant A exit criteria

Variant A is **PASS** if all are true:

- TLS handshake succeeds and validates against `ca.crt`
- MQTT publish/subscribe works on the TLS port with auth
- Telegraf ingests and writes
- InfluxDB contains the ingested data
- Grafana can query the data

If Variant A passes, treat the backend stack (including TLS) as correct.

---

## 6. Variant B: Edge validation (ESP32 over MQTT/TLS)

### 6.1 Goal

Validate only the remote boundary:

```
ESP32 -> MQTT/TLS (remote port 8883 or 1888) -> Mosquitto
```

Everything beyond Mosquitto has already been validated by Variant A.

---

### 6.2 Pre-checks on the backend host

Confirm the TLS port is reachable from the network. From a second machine on the same network (or from the ESP32 perspective, if feasible), run an OpenSSL check:

```bash
openssl s_client -connect <backend-ip>:8883 -CAfile ca.crt -servername <backend-hostname>
```

Expected: verification ok.

Also confirm firewall rules allow the TLS port inbound.

---

### 6.3 Step B1: Confirm ESP32 has the correct trust material

Minimum requirement:

- ESP32 must trust the same CA that signed `server.crt` (your `ca.crt`).
- ESP32 must connect to the broker via MQTT/TLS on the exposed TLS port.

If you later enforce mTLS:

- ESP32 must also have a client certificate and key signed by that CA.

---

### 6.4 Step B2: Publish a deterministic ESP32 bring-up message

From the ESP32 firmware, publish a known payload to a known topic. Example:

- Topic: `bringup/esp32/<device_id>`
- Payload: JSON or plain value, depending on your Telegraf parsing

Example payload (JSON):

```json
{"value": 1, "source": "esp32", "ts": 0}
```

Pass criteria:

- ESP32 reports successful MQTT connection over TLS.
- Message is published without errors.

---

### 6.5 Step B3: Verify arrival (backend-host side)

On the backend host, subscribe via TLS and confirm you see the ESP message:

```bash
mosquitto_sub \
  -h localhost -p 8883 \
  --cafile mosquitto/config/certs/ca.crt \
  -u <mqtt_user> -P <mqtt_password> \
  -t "bringup/#"
```

Expected: ESP32 message appears.

If it appears here but not in InfluxDB, the issue is parsing or Telegraf subscription coverage. Re-check Telegraf topics and parsing.

---

### 6.6 Step B4: Verify arrival in InfluxDB

As in Variant A, query the latest points and ensure the ESP32 publish is represented.

Pass criteria:

- A corresponding point exists in InfluxDB.

---

### 6.7 Variant B exit criteria

Variant B is **PASS** if:

- ESP32 connects over TLS to the exposed broker port
- A publish from ESP32 is observable via a local TLS subscription on the backend host
- Data is present in InfluxDB (and optionally visible in Grafana)

If Variant A passed but Variant B fails, the fault domain is limited to:

- ESP32 TLS configuration or memory constraints
- ESP32 WiFi and DNS routing
- Firewall or port exposure
- Incorrect broker hostname used by ESP32 (SNI, certificate CN/SAN mismatch)

---

## 7. Troubleshooting quick map

### 7.1 TLS handshake fails (Variant A)

Likely causes:

- Wrong CA file
- Mosquitto TLS listener not configured or not enabled
- Certificate path mismatch in `mosquitto.conf`
- Key permissions or unreadable key file

Checks:

```bash
docker logs mosquitto --tail 200
ls -l mosquitto/config/certs
```

### 7.2 MQTT auth fails

Likely causes:

- `passwd` file missing or wrong permissions
- Username/password mismatch
- ACL rules deny publish/subscribe

Checks:

- Inspect mosquitto.conf for `password_file` and `acl_file`
- Use `-d` on mosquitto_pub/sub to show details

### 7.3 MQTT works but no data in InfluxDB

Likely causes:

- Telegraf not subscribing to the topic
- Parsing mismatch (data format not as expected)
- Telegraf output not reaching InfluxDB

Checks:

```bash
docker logs telegraf --tail 200
docker exec -it influxdb influx -execute 'SHOW DATABASES'
```

### 7.4 Data in InfluxDB but not in Grafana

Likely causes:

- Grafana datasource misconfigured
- Wrong database name or retention policy
- Dashboard query mismatch

Checks:

- Grafana Explore query against the measurement
- Datasource health status

---

## 8. Maintenance notes (recommended)

- Keep TLS enabled in both Variant A and Variant B. Only the client location changes.
- Do not expose InfluxDB (8086) externally.
- Prefer SSH tunneling or VPN for Grafana access if needed.
- Regenerate certs per installation and rotate if the host is compromised.

---

## 9. Record of execution

When running this plan, record:

- Date, host, git commit
- TLS port used (8883 or 1888)
- Topic used for bring-up
- Measurement and query used for verification
- Pass/fail and any remediation actions
