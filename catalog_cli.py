
import json
import os
from datetime import datetime
from config import CATALOG_PATH
from sensor_device import SensorDevice

class CatalogManager:
    def __init__(self, catalog_file=CATALOG_PATH):
        self.catalog_file = catalog_file
        self.load()

    def load(self):
        if not os.path.exists(self.catalog_file):
            self.catalog = {"device_list": []}
        else:
            with open(self.catalog_file, "r") as f:
                self.catalog = json.load(f)

    def save(self):
        with open(self.catalog_file, "w") as f:
            json.dump(self.catalog, f, indent=4)
        print("[INFO] Catalog saved.")

    def get_next_id(self):
        ids = [dev["deviceID"] for dev in self.catalog["device_list"]]
        return max(ids) + 1 if ids else 0

    def get_devices(self):
        devices = []
        for d in self.catalog.get("device_list", []):
            for service in d.get("availableServices", []):
                if service.get("serviceType") == "MQTT":
                    topic = service["topics"][0]
                    devices.append(SensorDevice(
                        d["deviceID"],
                        d["deviceName"],
                        d["measureType"],
                        topic
                    ))
        return devices

    def add_sensor(self, device_name, measure_type, room):
        device_id = self.get_next_id()
        topic = f"iot_project/sensors/{room}/{measure_type.lower()}"

        new_device = {
            "deviceID": device_id,
            "deviceName": device_name,
            "measureType": measure_type,
            "availableServices": [
                {
                    "serviceType": "MQTT",
                    "serviceIP": "mqtt.eclipseprojects.io",
                    "topics": [topic]
                }
            ],
            "lastUpdate": datetime.now().strftime("%Y-%m-%d")
        }

        self.catalog["device_list"].append(new_device)
        self.save()
        print(f"[INFO] Sensor '{device_name}' added with ID {device_id} and topic '{topic}'")

    def delete_sensor(self, device_id):
        before = len(self.catalog["device_list"])
        self.catalog["device_list"] = [
            d for d in self.catalog["device_list"] if d["deviceID"] != device_id
        ]
        after = len(self.catalog["device_list"])
        if before == after:
            print(f"[WARNING] Sensor with ID {device_id} not found.")
        else:
            self.save()
            print(f"[INFO] Sensor with ID {device_id} deleted.")

# CLIENT PART

if __name__ == "__main__":
    cat = CatalogManager()

    while True:
        cmd = input("\n📋 Sensor Catalog CLI\n"
                    "Press 's' to show all sensors\n"
                    "Press 'n' to add a new sensor\n"
                    "Press 'd' to delete a sensor\n"
                    "Press 'q' to quit\n> ").strip().lower()

        if cmd == 's':
            devices = cat.get_devices()
            if not devices:
                print(" No sensors found in catalog.")
            else:
                for d in devices:
                    print(f"🆔 ID: {d.id} | {d.name} | {d.measure_type} | Topic: {d.topic}")

        elif cmd == 'n':
            name = input("Device name (e.g., Kitchen-Temp): ").strip()
            measure = input("Measurement type (Temperature/Light): ").strip().capitalize()
            room = input("Room (e.g., kitchen): ").strip().lower()

            if measure not in ["Temperature", "Light"]:
                print("[ERROR] Invalid measurement type. Must be 'Temperature' or 'Light'.")
            else:
                cat.add_sensor(name, measure, room)

        elif cmd == 'd':
            try:
                device_id = int(input("Enter Device ID to delete: ").strip())
                cat.delete_sensor(device_id)
            except ValueError:
                print("[ERROR] Please enter a valid integer ID.")

        elif cmd == 'q':
            print("Exiting. Bye!")
            break

        else:
            print("Invalid command. Try again.")
