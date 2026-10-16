"""Run the local dashboard; all startup happens inside main()."""
import argparse
import logging
import os
import threading
import time
from uuid import uuid4

import cherrypy
from catalog_cli import CatalogManager
from Webserver import DashboardWebServer
from shared_memory import add_data, is_paused, set_runtime


def demo_loop(catalog, stop):
    while not stop.is_set():
        for device in catalog.get_devices():
            if not is_paused(device.id):
                add_data({"Device ID": device.id, "Device Name": device.name,
                          "Measurement Type": device.measure_type, "Unit": device.unit,
                          "Value": device.generate_value(), "Topic": device.topic,
                          "Room": device.topic.split("/")[2],
                          "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})
        stop.wait(5)


def mqtt_loop(catalog, stop):
    from MyMQTT import MyMQTT
    from publisher import SensorPublisher
    from subscriber import DynamicSubscriber
    mqtt = MyMQTT("SmartHouse-" + uuid4().hex[:12],
                  os.environ.get("MQTT_BROKER", "broker.hivemq.com"),
                  int(os.environ.get("MQTT_PORT", "1883")))
    subscriber = DynamicSubscriber(mqtt, catalog)
    mqtt.notifier = subscriber
    publisher = SensorPublisher(mqtt, catalog)
    mqtt.start()
    try:
        while not stop.is_set():
            subscriber.update_subscriptions()
            publisher.publish_all()
            stop.wait(10)
    finally:
        mqtt.stop()


def main():
    parser = argparse.ArgumentParser(description="Smart Home Sensors dashboard")
    parser.add_argument("--demo", action="store_true", help="Local simulated data; no MQTT network")
    parser.add_argument("--telegram", action="store_true", help="Enable Telegram (requires environment settings)")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    bot = None
    if args.telegram:
        from telegram_bot_N import build_application
        bot = build_application()
    catalog = CatalogManager()
    stop = threading.Event()
    set_runtime(mode="demo" if args.demo else "mqtt", error=None)

    def run_worker():
        try:
            (demo_loop if args.demo else mqtt_loop)(catalog, stop)
        except Exception:
            logging.exception("Sensor worker stopped")
            set_runtime(error="Sensor worker stopped. Check the application log.")

    worker = threading.Thread(target=run_worker, daemon=True)
    cherrypy.config.update({"server.socket_host": "127.0.0.1", "server.socket_port": args.port,
                            "engine.autoreload.on": False, "log.screen": True})
    cherrypy.tree.mount(DashboardWebServer(catalog), "/")
    worker.start()
    try:
        cherrypy.engine.start()
        print(f"Dashboard: http://127.0.0.1:{args.port} (simulated sensors)")
        if bot:
            bot.run_polling()
        else:
            cherrypy.engine.block()
    finally:
        stop.set()
        worker.join(timeout=5)
        cherrypy.engine.exit()
        set_runtime(mode="stopped")


if __name__ == "__main__":
    main()
