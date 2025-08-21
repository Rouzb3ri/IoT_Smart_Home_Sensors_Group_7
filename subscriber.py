import json
import time
from shared_memory import shared_data, add_data
class DynamicSubscriber:
    def __init__(self, mqtt_client, catalog, data_logger=None):
        self.mqtt = mqtt_client
        self.catalog = catalog
        self.logger = data_logger
        self.current_topics = set()
        


    def update_subscriptions(self):
        new_topics = set()
        for device in self.catalog.get_devices():
            new_topics.add(device.topic)

        # Subscribe to new topics
        for topic in new_topics - self.current_topics:
            self.mqtt.mySubscribe(topic)
            self.current_topics.add(topic)
            print(f"[SUBSCRIBE] New topic: {topic}")

        # Unsubscribe from removed topics
        for topic in self.current_topics - new_topics:
            self.mqtt.unsubscribe(topic)
            self.current_topics.remove(topic)
            print(f"[UNSUBSCRIBE] Removed topic: {topic}")

    def notify(self, topic, msg):
        print(f"[NOTIFY] Message received on topic: {topic}")
        print(f"[NOTIFY] Raw message: {msg}")

        try:
            data = json.loads(msg)
            timestamp = data.get("Timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
            row = {
                "Timestamp": timestamp,
                "Device ID": data.get("Device ID"),
                "Device Name": data.get("Device Name", ""),
                "Measurement Type": data.get("Measurement Type"),
                "Value": data.get("Value"),
                "Unit": data.get("Unit"),
                "Topic": topic,
                "Room": topic.split("/")[2].title() if "sensors" in topic else "Unknown"
            }

            print(f"[NOTIFY] Final row: {row}")
            print(f"[NOTIFY] Calling add_data()")
            add_data(row)

            if self.logger:
                self.logger.log(row)

        except Exception as e:
            print(f"[ERROR] Failed to process message on {topic}: {e}")

print(f"[SUBSCRIBER] Shared data memory location: {id(shared_data)}")

