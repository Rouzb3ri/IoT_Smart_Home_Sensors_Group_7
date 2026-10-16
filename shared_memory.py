"""Bounded, synchronized state shared by MQTT, dashboard and Telegram."""
from collections import deque
from datetime import datetime, timezone
from threading import RLock
import math

_lock = RLock()
shared_data = deque(maxlen=1000)
_latest = {}
_paused = set()
_actions = deque(maxlen=50)
_runtime = {"mode": "stopped", "mqtt_connected": False, "error": None}


def add_data(row):
    value = row.get("Value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Sensor reading must be a finite number")
    if row.get("Device ID") is None:
        raise ValueError("Sensor reading requires a device ID")
    reading = dict(row)
    reading["received_at"] = datetime.now(timezone.utc).isoformat()
    with _lock:
        shared_data.append(reading)
        _latest[str(reading["Device ID"])] = reading


def snapshot():
    with _lock:
        return {"readings": [dict(row) for row in _latest.values()],
                "history": [dict(row) for row in list(shared_data)[-50:]][::-1],
                "paused": sorted(_paused), "actions": [dict(a) for a in reversed(_actions)],
                "runtime": dict(_runtime)}


def set_runtime(**values):
    with _lock:
        _runtime.update(values)


def is_paused(device_id):
    with _lock:
        return str(device_id) in _paused


def control_sensor(device_id, action, catalog, actor="Dashboard"):
    device_id = str(device_id)
    if action not in {"pause", "resume"}:
        raise ValueError("Choose pause or resume")
    if not any(str(d.id) == device_id for d in catalog.get_devices()):
        raise ValueError("Sensor no longer exists. Refresh and try again.")
    with _lock:
        if _runtime["mode"] not in {"demo", "mqtt"}:
            raise ValueError("Sensor simulation is not running")
        if action == "pause":
            _paused.add(device_id)
        else:
            _paused.discard(device_id)
        entry = {"device_id": device_id, "action": action, "actor": actor,
                 "timestamp": datetime.now(timezone.utc).isoformat()}
        _actions.append(entry)
        return dict(entry)
