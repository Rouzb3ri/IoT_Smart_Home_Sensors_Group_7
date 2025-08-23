├── catalog.json            # JSON-based device registry
├── catalog_cli.py          # CLI tool to manage catalog entries
├── sensor_device.py        # Generates simulated temperature and light values
├── publisher.py            # Publishes sensor data to MQTT topics
├── subscriber.py           # Subscribes to MQTT topics and updates shared memory
├── shared_memory.py        # Stores the most recent sensor data and pending commands
├── MyMQTT.py               # MQTT wrapper using paho.mqtt.client
├── app.py                  # CherryPy-based web dashboard server
├── telegram_bot_N.py       # Telegram bot for monitoring and control
├── main.py                 # Orchestrates all components (webserver, bot, MQTT loop)
