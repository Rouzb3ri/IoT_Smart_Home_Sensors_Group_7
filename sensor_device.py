class SensorDevice:
    def __init__(self, deviceID, name, measure_type, topic):
        self.id = deviceID
        self.name = name
        self.measure_type = measure_type
        self.topic = topic
        self.unit = "Celsius" if measure_type == "Temperature" else "Lux"

    def generate_value(self):
        import random
        if self.measure_type == "Temperature":
            return round(random.uniform(18.0, 30.0), 2)
        elif self.measure_type == "Light":
            return round(random.uniform(300.0, 1000.0), 2)
