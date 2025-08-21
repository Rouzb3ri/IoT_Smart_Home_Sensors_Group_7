import time
import threading
from MyMQTT import MyMQTT
from catalog_manager import CatalogManager
from publisher import SensorPublisher
from subscriber import DynamicSubscriber
from shared_memory import shared_data
from webserver.app import DashboardWebServer
from telegram_bot_N import build_bot_and_run  
from shared_memory import pending_commands


def run_webserver():
    import cherrypy
    cherrypy.quickstart(DashboardWebServer(), '/', {
        '/': {
            'tools.sessions.on': True,
        }
    })
    
def handle_telegram_command(cmd, mqtt):
    parts = cmd.split()
    if len(parts) != 2:
        print("[ERROR] Invalid command format. Expected: light_on room")
        return

    action, room = parts
    topic = f"iot_project/sensors/{room}/light"

    if action == "light_on":
        mqtt.myPublish(topic, "ON") 
    elif action == "light_off":
        mqtt.myPublish(topic, "OFF") 
    else:
        print(f"[ERROR] Unknown action: {action}")



def run_iot_mqtt_logic():
    client_id = "SmartHouseClient_8"
    broker = "broker.hivemq.com"
    port = 1883

    mqtt = MyMQTT(client_id, broker, port)

    catalog = CatalogManager("catalog.json")

    subscriber = DynamicSubscriber(mqtt, catalog)
    mqtt.notifier = subscriber

    publisher = SensorPublisher(mqtt, catalog)

    mqtt.start()

    time.sleep(2)
    while True:
        catalog.load()
        subscriber.update_subscriptions()
        publisher.publish_all()

        
        while pending_commands:
            cmd = pending_commands.pop(0)
            print(f"[TELEGRAM → MQTT] Publishing command: {cmd}")
            handle_telegram_command(cmd, mqtt)

        time.sleep(10)



threading.Thread(target=run_iot_mqtt_logic, daemon=True).start()
threading.Thread(target=run_webserver, daemon=True).start()


if __name__ == '__main__':
    print("[MAIN] Starting Telegram bot...")
    build_bot_and_run()
