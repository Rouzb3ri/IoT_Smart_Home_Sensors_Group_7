import time

class SensorPublisher:
    def __init__(self, mqtt_client, catalog):
        self.mqtt = mqtt_client
        self.catalog = catalog

    def publish_all(self):
        sensors = self.catalog.get_devices()  
        for sensor in sensors:
            value = sensor.generate_value()   
            message = {
                "Device ID": sensor.id,
                "Device Name": sensor.name,
                "Measurement Type": sensor.measure_type,
                "Unit": sensor.unit,
                "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "Value": value
            }
            self.mqtt.myPublish(sensor.topic, message)  
            print(f"[PUBLISH] {sensor.topic} → {value} {sensor.unit}")
