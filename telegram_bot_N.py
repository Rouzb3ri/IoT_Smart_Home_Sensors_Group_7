"""Telegram interface. Constructing/importing it does not connect to MQTT or Telegram."""
from functools import wraps
import logging
import os
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from catalog_cli import CatalogManager
from config import allowed_users, dashboard_url
from sensor_views import sensor_status, format_reading
from shared_memory import control_sensor, snapshot

log = logging.getLogger(__name__)
MENU = ReplyKeyboardMarkup([["📊 Status", "📋 Sensors"], ["🎛 Simulation", "🧾 Recent"],
                            ["🖥 Dashboard", "⚙️ Settings"], ["❓ Help"]], resize_keyboard=True)


def authorized(handler):
    @wraps(handler)
    async def wrapper(update, context):
        users = context.application.bot_data.get("allowed_users", set())
        if not update.effective_user or update.effective_user.id not in users:
            if update.callback_query:
                await update.callback_query.answer("Access is restricted to the configured users.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text("Access is restricted. Ask the owner to add your numeric Telegram user ID.")
            return
        return await handler(update, context)
    return wrapper


async def send_lines(message, lines):
    """Split at line boundaries to respect Telegram's message limit."""
    chunk = ""
    for line in lines:
        # Each line is bounded too, so a pathological device name cannot overflow a message.
        for start in range(0, max(1, len(line)), 3000):
            part = line[start:start + 3000]
            if len(chunk) + len(part) + 1 > 3500:
                await message.reply_text(chunk)
                chunk = ""
            chunk += part + "\n"
    if chunk:
        await message.reply_text(chunk.rstrip())


def catalog(context):
    return context.application.bot_data["catalog"]


def room_name(room):
    return room.replace("livingroom", "living room").replace("_", " ").title()


@authorized
async def start(update, context):
    await update.effective_message.reply_text(
        "Welcome to Smart Home.\n\nSee the latest reading for every sensor, check stale data, "
        "and pause or resume individual sensor simulations.\n\n"
        "This project uses simulated readings; these controls do not switch physical lights or heating.\n"
        "Use /status, /sensors, /control, /recent, /dashboard, /settings or /help.", reply_markup=MENU)


@authorized
async def status(update, context):
    data = sensor_status(catalog(context))
    unit = context.user_data.get("temperature_unit", "C")
    runtime = data["runtime"]
    connection = "Local demo" if runtime["mode"] == "demo" else ("MQTT connected" if runtime["mqtt_connected"] else "MQTT offline")
    lines = [f"Smart Home · {connection} · simulated sensors"]
    if runtime["error"]:
        lines.append(runtime["error"])
    if not data["devices"]:
        lines.append("No sensors are configured in the catalog.")
    for device in data["devices"]:
        age = "" if device["age_seconds"] is None else f" · {int(device['age_seconds'])}s ago"
        lines.append(f"{room_name(device['room'])} · {device['name']}\n"
                     f"{format_reading(device, unit)} · {device['state']}{age}")
    await send_lines(update.effective_message, lines)


@authorized
async def sensors(update, context):
    devices = sensor_status(catalog(context))["devices"]
    await send_lines(update.effective_message, ["Configured sensors"] +
                     [f"#{d['id']} · {d['name']} · {room_name(d['room'])} · {d['type']}" for d in devices])


def control_keyboard(context):
    devices = sensor_status(catalog(context))["devices"]
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        f"{d['name']} · {'Resume' if d['state'] == 'paused' else 'Pause'}",
        callback_data=f"choose:{d['id']}:{'resume' if d['state'] == 'paused' else 'pause'}")]
        for d in devices])


@authorized
async def control(update, context):
    if not catalog(context).get_devices():
        await update.effective_message.reply_text("No sensors are configured.")
        return
    await update.effective_message.reply_text("Choose a sensor simulation to pause or resume:", reply_markup=control_keyboard(context))


@authorized
async def callback(update, context):
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    if parts[0] == "cancel":
        await query.edit_message_text("Cancelled. No changes made.")
        return
    if parts[0] == "unit":
        unit = "F" if context.user_data.get("temperature_unit", "C") == "C" else "C"
        context.user_data["temperature_unit"] = unit
        await query.edit_message_text(f"Temperature display: °{unit}.\nUse /settings to change it again.")
        return
    if len(parts) != 3 or parts[0] not in {"choose", "apply"} or parts[2] not in {"pause", "resume"}:
        await query.edit_message_text("This control is outdated. Use /control to refresh it.")
        return
    _, device_id, action = parts
    device = next((d for d in catalog(context).get_devices() if str(d.id) == device_id), None)
    if device is None:
        await query.edit_message_text("This sensor no longer exists. Use /control to refresh.")
        return
    if parts[0] == "choose":
        await query.edit_message_text(f"{action.title()} simulation for {device.name}?\nNo physical devices will be switched.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Confirm", callback_data=f"apply:{device_id}:{action}"),
                                                InlineKeyboardButton("Cancel", callback_data="cancel")]]))
        return
    try:
        control_sensor(device_id, action, catalog(context), actor="Telegram")
    except ValueError as error:
        await query.edit_message_text(str(error))
        return
    await query.edit_message_text(f"{device.name}: simulation {'paused' if action == 'pause' else 'resumed'}.\nUse /status for readings or /control for another sensor.")


@authorized
async def recent(update, context):
    actions = snapshot()["actions"][:10]
    devices = {str(d.id): d.name for d in catalog(context).get_devices()}
    await send_lines(update.effective_message, ["Recent simulation actions"] +
        ([f"{a['timestamp']} · {devices.get(a['device_id'], a['device_id'])} · {a['action']} · {a['actor']}" for a in actions]
         or ["No actions yet."]))


@authorized
async def dashboard(update, context):
    url = dashboard_url()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        await update.effective_message.reply_text(
            "On the computer running this app, open http://127.0.0.1:8080.\n"
            "A phone cannot reach that computer through localhost. The owner can configure DASHBOARD_URL "
            "after setting up a reachable, protected dashboard address.")
        return
    await update.effective_message.reply_text(f"Dashboard: {url}", disable_web_page_preview=True)


@authorized
async def settings(update, context):
    unit = context.user_data.get("temperature_unit", "C")
    await update.effective_message.reply_text(f"Your temperature unit: °{unit}\nPreferences reset when the app restarts.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Switch °C / °F", callback_data="unit")]]))


@authorized
async def help_cmd(update, context):
    await update.effective_message.reply_text(
        "/status — latest reading for each sensor, with freshness\n/sensors — configured devices\n"
        "/control — pause or resume sensor simulations\n/recent — last 10 simulation actions\n"
        "/dashboard — dashboard address\n/settings — °C or °F\n"
        "Live = received within 30 seconds. Stale = older reading. Paused = simulation paused.\n"
        "Automatic alerts and physical actuator control are not implemented.", reply_markup=MENU)


@authorized
async def handle_buttons(update, context):
    handlers = {"📊 Status": status, "📋 Sensors": sensors, "🎛 Simulation": control,
                "🧾 Recent": recent, "🖥 Dashboard": dashboard, "⚙️ Settings": settings, "❓ Help": help_cmd}
    handler = handlers.get((update.effective_message.text or "").strip())
    if handler:
        await handler(update, context)
    else:
        await update.effective_message.reply_text("Choose a menu button or use /help.", reply_markup=MENU)


async def on_error(update, context):
    # Never log exception text: network exceptions can include the bot token in a URL.
    log.error("Telegram request failed (%s)", type(context.error).__name__)
    if isinstance(context.error, BadRequest) and "Message is not modified" in str(context.error):
        return
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("That request could not be completed. Please try /status or /control again.")
        except Exception:
            log.error("Could not deliver the error message")


def build_application():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    users = allowed_users()
    if not token or not users:
        raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_IDS before enabling Telegram")
    app = ApplicationBuilder().token(token).build()
    app.bot_data.update(catalog=CatalogManager(), allowed_users=users)
    for name, handler in {"start": start, "status": status, "sensors": sensors, "control": control,
                          "recent": recent, "dashboard": dashboard, "settings": settings, "help": help_cmd}.items():
        app.add_handler(CommandHandler(name, handler))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    app.add_error_handler(on_error)
    return app


def build_bot_and_run():
    build_application().run_polling()
