#!/usr/bin/env bash
 # Add the initial user 
 
docker exec -it mosquitto rm -f /mosquitto/config/passwd
docker run --rm -v "$(pwd)/mosquitto/config:/mosquitto/config" eclipse-mosquitto:1.6 \
  mosquitto_passwd -c -b /mosquitto/config/passwd "$MOSQUITTO_USERNAME" "$MOSQUITTO_PASSWORD"
echo "MQTT user '$MOSQUITTO_USERNAME' created with provided password."