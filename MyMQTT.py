"""Paho 2 adapter with subscriptions restored after reconnect."""
import json
import logging
import paho.mqtt.client as PahoMQTT
from shared_memory import set_runtime

log = logging.getLogger(__name__)


class MyMQTT:
    def __init__(self, clientID, broker, port, notifier=None, qos=1):
        self.notifier = notifier
        self.broker, self.port, self.qos = broker, port, qos
        self._topics = {}
        self._isConnected = False
        self._paho_mqtt = PahoMQTT.Client(PahoMQTT.CallbackAPIVersion.VERSION2, client_id=clientID)
        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_disconnect = self.myOnDisconnect
        self._paho_mqtt.on_message = self.myOnMessageReceived
        self._paho_mqtt.reconnect_delay_set(1, 30)

    def myOnConnect(self, client, userdata, flags, reason_code, properties):
        self._isConnected = reason_code == 0
        set_runtime(mqtt_connected=self._isConnected,
                    error=None if self._isConnected else "MQTT broker rejected the connection")
        if self._isConnected:
            for topic, qos in self._topics.copy().items():
                client.subscribe(topic, qos)

    def myOnDisconnect(self, client, userdata, flags, reason_code, properties):
        self._isConnected = False
        set_runtime(mqtt_connected=False)

    def myOnMessageReceived(self, client, userdata, msg):
        try:
            if self.notifier:
                self.notifier.notify(msg.topic, msg.payload.decode("utf-8"))
        except (UnicodeError, ValueError):
            log.warning("Ignored malformed MQTT message")

    def myPublish(self, topic, msg, qos=None):
        if not self._isConnected:
            return False
        result = self._paho_mqtt.publish(topic, json.dumps(msg, allow_nan=False),
                                         self.qos if qos is None else qos)
        return result.rc == PahoMQTT.MQTT_ERR_SUCCESS

    def mySubscribe(self, topic, qos=None):
        qos = self.qos if qos is None else qos
        self._topics[topic] = qos
        if self._isConnected:
            result, _ = self._paho_mqtt.subscribe(topic, qos)
            return result == PahoMQTT.MQTT_ERR_SUCCESS
        return False

    def unsubscribe(self, topic):
        self._topics.pop(topic, None)
        if self._isConnected:
            self._paho_mqtt.unsubscribe(topic)

    def start(self):
        self._paho_mqtt.connect_async(self.broker, self.port, keepalive=60)
        self._paho_mqtt.loop_start()

    def stop(self):
        self._paho_mqtt.disconnect()
        self._paho_mqtt.loop_stop()
        self._isConnected = False
        set_runtime(mqtt_connected=False)
