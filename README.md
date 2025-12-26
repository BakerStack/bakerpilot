# bakerpilot
Control logic and fermentation models for BakerStack. Turns sensor data into actionable decisions.
This repo contains the configuration for the backe-end of the system such as message brokers, databases, dashboards etc. 
 

# Bootstrapping the system
On your back end system , check out this repo and make sure to first follow the instructions in `settings-template.sh`. 
Follow the `README.md`in the mosquitto folder to set up the certificats and initial users for mosquitto. 

Then you do `docker compose up -d ` to start the remaining system in docker containers. 

The `tests/test-plan.md` contains more detailed instructions on how to test that the system has started correctly.