"""The same current sensor status for the dashboard and Telegram."""
from datetime import datetime, timezone
from shared_memory import snapshot


def sensor_status(catalog):
    data = snapshot()
    latest = {str(row["Device ID"]): row for row in data["readings"]}
    devices = []
    for device in catalog.get_devices():
        row = latest.get(str(device.id))
        age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(row["received_at"])).total_seconds()) if row else None
        state = ("paused" if str(device.id) in data["paused"] else
                 "waiting" if row is None else "stale" if age > 30 else "live")
        devices.append({"id": device.id, "name": device.name, "type": device.measure_type,
                        "room": device.topic.split("/")[2], "unit": device.unit,
                        "reading": row, "age_seconds": age, "state": state})
    data["devices"] = devices
    return data


def format_reading(device, unit="C"):
    row = device["reading"]
    if row is None:
        return "Waiting for first reading"
    value = row["Value"]
    if device["type"].lower() == "temperature":
        if unit == "F":
            value = value * 9 / 5 + 32
        return f"{value:.1f} °{unit}"
    return f"{value:.0f} lux"
