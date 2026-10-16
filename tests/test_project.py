import asyncio
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import shared_memory as memory
from catalog_cli import CatalogManager
from sensor_views import sensor_status, format_reading
from subscriber import DynamicSubscriber
import telegram_bot_N as bot


class StateTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CatalogManager()
        with memory._lock:
            memory.shared_data.clear()
            memory._latest.clear()
            memory._paused.clear()
            memory._actions.clear()
        memory.set_runtime(mode="demo", mqtt_connected=False, error=None)

    def row(self, value=20, device_id=0):
        return {"Device ID": device_id, "Value": value, "Room": "kitchen"}

    def test_catalog_returns_simulatable_sensor(self):
        device = self.catalog.get_devices()[0]
        self.assertEqual(device.unit, "Celsius")
        self.assertIsInstance(device.generate_value(), float)

    def test_latest_per_sensor_and_bounded_history(self):
        for value in range(1200):
            memory.add_data(self.row(value))
        memory.add_data(self.row(500, 1))
        data = memory.snapshot()
        self.assertEqual(len(memory.shared_data), 1000)
        self.assertEqual(len(data["readings"]), 2)
        self.assertEqual(len(data["history"]), 50)
        self.assertEqual(data["readings"][0]["Value"], 1199)
        data["readings"][0]["Value"] = -999
        self.assertEqual(memory.snapshot()["readings"][0]["Value"], 1199)

    def test_rejects_invalid_values(self):
        for value in [True, float("nan"), float("inf"), None, "20"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                memory.add_data(self.row(value))

    def test_status_waiting_live_stale_paused(self):
        self.assertEqual(sensor_status(self.catalog)["devices"][0]["state"], "waiting")
        memory.add_data(self.row())
        self.assertEqual(sensor_status(self.catalog)["devices"][0]["state"], "live")
        memory._latest["0"]["received_at"] = (datetime.now(timezone.utc)-timedelta(seconds=45)).isoformat()
        self.assertEqual(sensor_status(self.catalog)["devices"][0]["state"], "stale")
        memory.control_sensor(0, "pause", self.catalog)
        self.assertEqual(sensor_status(self.catalog)["devices"][0]["state"], "paused")
        memory.control_sensor(0, "resume", self.catalog)
        self.assertFalse(memory.is_paused(0))

    def test_control_validation(self):
        for device_id, action in [(999,"pause"),(0,"on"),(None,"resume")]:
            with self.subTest(device=device_id, action=action), self.assertRaises(ValueError):
                memory.control_sensor(device_id, action, self.catalog)

    def test_subscriber_rejects_commands_and_foreign_devices(self):
        subscriber = DynamicSubscriber(Mock(), self.catalog)
        topic = self.catalog.get_devices()[0].topic
        for payload in ['"ON"', '{"command":"ON"}', '{bad', json.dumps(self.row(20,999))]:
            self.assertFalse(subscriber.notify(topic, payload))
        self.assertTrue(subscriber.notify(topic, json.dumps(self.row())))
        self.assertEqual(memory.snapshot()["readings"][0]["Room"], "kitchen")

    def test_subscription_retries_after_offline_failure(self):
        mqtt = Mock()
        mqtt.mySubscribe.return_value = False
        subscriber = DynamicSubscriber(mqtt, self.catalog)
        subscriber.update_subscriptions()
        self.assertEqual(subscriber.current_topics, set())
        mqtt.mySubscribe.return_value = True
        subscriber.update_subscriptions()
        self.assertEqual(len(subscriber.current_topics), len(self.catalog.get_devices()))

    def test_paused_sensor_does_not_publish(self):
        from publisher import SensorPublisher
        memory.control_sensor(0, "pause", self.catalog)
        mqtt = Mock()
        SensorPublisher(mqtt, self.catalog).publish_all()
        self.assertFalse(any(call.args[1]["Device ID"] == 0 for call in mqtt.myPublish.call_args_list))

    def test_temperature_conversion(self):
        memory.add_data(self.row(20))
        device = sensor_status(self.catalog)["devices"][0]
        self.assertEqual(format_reading(device,"F"), "68.0 °F")

    def test_imports_do_not_start_services(self):
        with patch('threading.Thread.start', side_effect=AssertionError("thread started")), patch('socket.socket.connect', side_effect=AssertionError("network")):
            import main
            importlib.reload(main)
            importlib.reload(bot)

    def context(self, user_id=1, callback_data=None):
        message=SimpleNamespace(reply_text=AsyncMock())
        query=SimpleNamespace(data=callback_data, answer=AsyncMock(), edit_message_text=AsyncMock()) if callback_data else None
        update=SimpleNamespace(effective_user=SimpleNamespace(id=user_id), effective_message=message, callback_query=query)
        context=SimpleNamespace(application=SimpleNamespace(bot_data={"allowed_users":{1},"catalog":self.catalog}), user_data={})
        return update, context

    def test_telegram_rejects_unauthorized_control(self):
        update, context = self.context(99,"apply:0:pause")
        asyncio.run(bot.callback(update, context))
        self.assertFalse(memory.is_paused(0))
        update.callback_query.answer.assert_awaited_once()

    def test_telegram_confirm_and_apply_simulation(self):
        update, context = self.context(callback_data="choose:0:pause")
        asyncio.run(bot.callback(update, context))
        self.assertFalse(memory.is_paused(0))
        self.assertIn("No physical devices", update.callback_query.edit_message_text.call_args.args[0])
        update.callback_query.data="apply:0:pause"
        asyncio.run(bot.callback(update, context))
        self.assertTrue(memory.is_paused(0))

    def test_telegram_status_covers_all_devices_once(self):
        update, context = self.context()
        asyncio.run(bot.status(update, context))
        text="\n".join(c.args[0] for c in update.effective_message.reply_text.call_args_list)
        for device in self.catalog.get_devices():
            self.assertEqual(text.count(device.name),1)

    def test_telegram_chunks_large_messages(self):
        message=SimpleNamespace(reply_text=AsyncMock())
        asyncio.run(bot.send_lines(message,["x"*9000]))
        self.assertGreater(message.reply_text.await_count,1)
        self.assertTrue(all(len(c.args[0])<=3500 for c in message.reply_text.call_args_list))

    def test_telegram_requires_explicit_config(self):
        with patch.dict(os.environ,{},clear=True), self.assertRaises(ValueError):
            bot.build_application()

    def test_phone_dashboard_explains_localhost(self):
        update, context = self.context()
        with patch.dict(os.environ,{"DASHBOARD_URL":""}):
            asyncio.run(bot.dashboard(update, context))
        self.assertIn("phone cannot reach",update.effective_message.reply_text.call_args.args[0])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            cls.port=sock.getsockname()[1]
        cls.base=f'http://127.0.0.1:{cls.port}'
        cls.process=subprocess.Popen([sys.executable,str(ROOT/'main.py'),'--demo','--port',str(cls.port)],cwd=ROOT,
                                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with urlopen(cls.base+'/status',timeout=1) as response:
                    json.load(response)
                return
            except OSError:
                time.sleep(.1)
        cls.process.terminate()
        cls.process.wait(timeout=5)
        raise RuntimeError('Demo server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)

    def test_dashboard_and_all_sensor_readings(self):
        with urlopen(self.base,timeout=3) as response:
            self.assertIn('Room by room',response.read().decode())
        with urlopen(self.base+'/status',timeout=3) as response:
            data=json.load(response)
        self.assertEqual(data['runtime']['mode'],'demo')
        self.assertEqual(len(data['devices']),11)
        self.assertTrue(all(d['reading'] for d in data['devices']))

    def post(self,payload,headers=True):
        h={'Content-Type':'application/json'}
        if headers:h['X-SmartHome-Client']='dashboard'
        return urlopen(Request(self.base+'/control',data=json.dumps(payload).encode(),headers=h),timeout=3)

    def test_control_http_validation_and_shared_status(self):
        with self.assertRaises(HTTPError) as error:
            self.post({'device_id':0,'action':'pause'},headers=False)
        self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError) as error:
            self.post({'device_id':999,'action':'pause'})
        self.assertEqual(error.exception.code,400)
        with self.post({'device_id':0,'action':'pause'}) as response:
            self.assertEqual(json.load(response)['action'],'pause')
        with urlopen(self.base+'/status',timeout=3) as response:
            self.assertEqual(json.load(response)['devices'][0]['state'],'paused')
        with self.post({'device_id':0,'action':'resume'}):pass


if __name__ == '__main__':
    unittest.main()
