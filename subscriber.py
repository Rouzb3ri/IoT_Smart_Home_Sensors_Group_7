import json
from shared_memory import add_data, is_paused


class DynamicSubscriber:
    def __init__(self, mqtt_client, catalog, data_logger=None):
        self.mqtt = mqtt_client
        self.catalog = catalog
        self.logger = data_logger
        self.current_topics = set()

    def update_subscriptions(self):
        topics = {device.topic for device in self.catalog.get_devices()}
        for topic in topics - self.current_topics:
            if self.mqtt.mySubscribe(topic):
                self.current_topics.add(topic)
        for topic in self.current_topics - topics:
            self.mqtt.unsubscribe(topic)
            self.current_topics.discard(topic)

    def notify(self, topic, msg):
        try:
            data = json.loads(msg)
            if not isinstance(data, dict):
                return False
            device = next((d for d in self.catalog.get_devices()
                           if d.topic == topic and d.id == data.get("Device ID")), None)
            if not device or is_paused(device.id):
                return False
            row = {"Timestamp": data.get("Timestamp", ""), "Device ID": device.id,
                   "Device Name": device.name, "Measurement Type": device.measure_type,
                   "Value": data.get("Value"), "Unit": device.unit,
                   "Topic": topic, "Room": topic.split("/")[2]}
            add_data(row)
            if self.logger:
                self.logger.log(row)
            return True
        except (ValueError, TypeError, IndexError):
            return False
