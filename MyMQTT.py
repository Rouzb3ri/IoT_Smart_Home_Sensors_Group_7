
import paho.mqtt.client as PahoMQTT
import json

class MyMQTT:
    def __init__(self, clientID, broker, port, notifier=None, qos=2):
        self.broker = broker
        self.port = port
        self.notifier = notifier
        self.clientID = clientID
        self.qos = qos
        self._topics = set()
        self._isSubscriber = False
        self._isConnected = False

        self._paho_mqtt = PahoMQTT.Client(client_id=clientID, clean_session=True)

        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_message = self.myOnMessageReceived
        self._paho_mqtt.on_disconnect = self.myOnDisconnect

    def myOnConnect(self, paho_mqtt, userdata, flags, rc):
        if rc == 0:
            self._isConnected = True
            print(f"[INFO] Connected to {self.broker}:{self.port} with result code {rc}")
        else:
            print(f"[ERROR] Connection failed with code {rc}")

    def myOnMessageReceived(self, paho_mqtt, userdata, msg):
        print(f"[DEBUG] MQTT message received on {msg.topic}")
        try:
            payload = msg.payload.decode("utf-8")
            print(f"[DEBUG] Payload received: {payload}")
            if self.notifier:
                self.notifier.notify(msg.topic, payload)
        except Exception as e:
            print(f"[ERROR] Failed to decode or notify: {e}")


    def myOnDisconnect(self, paho_mqtt, userdata, rc):
        self._isConnected = False
        print(f"[INFO] Disconnected from {self.broker}:{self.port}")

    def myPublish(self, topic, msg, qos=None):
        if self._isConnected:
            qos = qos if qos is not None else self.qos
            try:
                self._paho_mqtt.publish(topic, json.dumps(msg), qos)
                print(f"[INFO] Published to {topic} with QoS {qos}: {json.dumps(msg)}")
            except Exception as e:
                print(f"[ERROR] Failed to publish to {topic}: {e}")
        else:
            print("[ERROR] Not connected to broker. Cannot publish.")

    def mySubscribe(self, topic, qos=None):
        if self._isConnected:
            qos = qos if qos is not None else self.qos
            if topic not in self._topics:
                try:
                    self._paho_mqtt.subscribe(topic, qos)
                    self._topics.add(topic)
                    print(f"[INFO] Subscribed to {topic} with QoS {qos}")
                except Exception as e:
                    print(f"[ERROR] Failed to subscribe to {topic}: {e}")
        else:
            print("[ERROR] Not connected to broker. Cannot subscribe.")

    def start(self):
        if not self._isConnected:
            try:
                self._paho_mqtt.connect(self.broker, self.port)
                self._paho_mqtt.loop_start()
                print(f"[INFO] MQTT client started for {self.clientID}")
            except Exception as e:
                print(f"[ERROR] Failed to start MQTT client: {e}")

    def unsubscribe(self, topic=None):
        if self._isConnected:
            try:
                if topic:
                    self._paho_mqtt.unsubscribe(topic)
                    self._topics.discard(topic)
                    print(f"[INFO] Unsubscribed from {topic}")
                else:
                    for t in list(self._topics):
                        self._paho_mqtt.unsubscribe(t)
                        print(f"[INFO] Unsubscribed from {t}")
                    self._topics.clear()
            except Exception as e:
                print(f"[ERROR] Failed to unsubscribe: {e}")
        else:
            print("[ERROR] Not connected to broker. Cannot unsubscribe.")

    def stop(self):
        if self._isConnected:
            self.unsubscribe()
            self._paho_mqtt.loop_stop()
            self._paho_mqtt.disconnect()
            self._isConnected = False
            print(f"[INFO] MQTT client stopped for {self.clientID}")

