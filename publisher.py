import time
import logging
from shared_memory import is_paused

class SensorPublisher:
    def __init__(self, mqtt_client, catalog):
        self.mqtt = mqtt_client
        self.catalog = catalog

    def publish_all(self):
        sensors = self.catalog.get_devices()
        for sensor in sensors:
            if is_paused(sensor.id):
                continue
            value = sensor.generate_value()
            message = {
                "Device ID": sensor.id,
                "Device Name": sensor.name,
                "Measurement Type": sensor.measure_type,
                "Unit": sensor.unit,
                "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "Value": value
            }
            if self.mqtt.myPublish(sensor.topic, message):
                logging.getLogger(__name__).info("Published simulated reading for %s", sensor.name)
