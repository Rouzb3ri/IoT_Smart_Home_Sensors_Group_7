
from datetime import datetime
from typing import Dict, Any, List
import socket

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

from shared_memory import shared_data, pending_commands  
from catalog_cli import CatalogManager
from MyMQTT import MyMQTT

BOT_TOKEN = "8119929054:AAGyyQCk7LfaSNmmrOkPblEmxP4Yhi-2jCM"  

def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LAN_IP = _get_lan_ip()
DASHBOARD_URL = "http://localhost:8080"


catalog = CatalogManager("catalog.json")
mqtt = MyMQTT("TelegramBot", "broker.hivemq.com", 1883)
mqtt.start()

recent_actions: List[str] = []


user_settings: Dict[int, Dict[str, Any]] = {}

def get_user_settings(user_id: int) -> Dict[str, Any]:
    if user_id not in user_settings:
        user_settings[user_id] = {"temperature_unit": "C", "notifications": True}
    return user_settings[user_id]


def log_action(user: str, room: str, device_type: str, action: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] ✅ {room} {device_type} {action.upper()} by {user}"
    recent_actions.append(entry)
    if len(recent_actions) > 20:
        recent_actions.pop(0)

def room_icon(room: str) -> str:
    mapping = {
        "kitchen": "🍳",
        "livingroom": "🛋",
        "garage": "🚗",
        "bedroom": "🛏",
        "basement": "🏚",
        "bathroom": "🚿"
    }
    return mapping.get(room.lower(), "🏠")

def main_menu_markup() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("📊 Status"),    KeyboardButton("📋 Sensors")],
        [KeyboardButton("💡 Control"),   KeyboardButton("🧾 Recent")],
        [KeyboardButton("🖥 Dashboard"), KeyboardButton("❓ Help")],
        [KeyboardButton("⚙️ Settings")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def format_temp(value_c: float, unit_pref: str):
    if unit_pref == "F":
        return (value_c * 9.0 / 5.0 + 32.0, "Fahrenheit")
    return (value_c, "Celsius")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 Hi, I’m *SmartHomeControlBot* — your smart house buddy!\n\n"
        "📊 Check status of your rooms\n"
        "💡 Control the lights & temperature\n"
        "📋 List available sensors\n"
        "🧾 Review recent changes\n"
        "🖥 Dashboard → Open web dashboard\n"
        "❓ Help\n"
        "⚙️ Settings → Temperature unit & notifications\n\n"
        "✨ Let’s make your home smarter, one tap at a time!"
    )
    await update.message.reply_text(msg, reply_markup=main_menu_markup(), parse_mode="Markdown")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not shared_data:
        await update.message.reply_text("❗ No data received yet.")
        return

    user_id = update.message.from_user.id
    prefs = get_user_settings(user_id)
    unit_pref = prefs["temperature_unit"]  # "C" or "F"

    lines = []
    for row in shared_data[-10:][::-1]:
        mtype = row.get("Measurement Type", "")
        unit = row.get("Unit", "")
        value = row.get("Value", "")
        if mtype.lower().startswith("temp"):
            try:
                value_c = float(value)
                value_conv, _disp_unit = format_temp(value_c, unit_pref)
                value = f"{value_conv:.2f}"
                unit = "°F" if unit_pref == "F" else "°C"
            except Exception:
                pass
        line = f"{room_icon(row['Room'])} *{row['Room']}* — {mtype}: {value} {unit}"
        lines.append(line)

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def sensors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    catalog.load()
    devices = catalog.get_devices()
    if not devices:
        await update.message.reply_text("❗ No sensors available.")
        return
    txt = "\n".join([
        f"🆔 {d.id} | {d.name} | {d.measure_type} | {d.topic}" for d in devices
    ])
    await update.message.reply_text(txt)

async def control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rooms = sorted(set(d.get('Room', 'Unknown') for d in shared_data))
    rooms = [r for r in rooms if r and r != 'Unknown']
    if not rooms:
        await update.message.reply_text("❗ No room data available.")
        return
    keyboard = [
        [InlineKeyboardButton(f"{room_icon(room)} {room}", callback_data=f"control_room:{room}")]
        for room in rooms
    ]
    await update.message.reply_text(
        "Select a room to control:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def control_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, room = query.data.split(":", 1)

    keyboard = [
        [InlineKeyboardButton("🔆 Light ON",               callback_data=f"cmd:{room}:light:on")],
        [InlineKeyboardButton("⛔️ Light OFF (Power Cut)", callback_data=f"cmd:{room}:light:off")],
        [InlineKeyboardButton("🌡 Temp ON",                callback_data=f"cmd:{room}:temperature:on")],
        [InlineKeyboardButton("❄️ Temp OFF",               callback_data=f"cmd:{room}:temperature:off")],
        [InlineKeyboardButton("⬅️ Back",                   callback_data="go_back")]
    ]
    await query.edit_message_text(
        f"{room_icon(room)} *{room}* Controls:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, room, typ, state = query.data.split(":")
    room = room.lower()

    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data=f"do:{room}:{typ}:{state}")],
        [InlineKeyboardButton("❌ Cancel",  callback_data="cancel_action")]
    ]
    await query.edit_message_text(
        f"Confirm action: *{state.upper()}* {room} {typ}?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def do_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, room, typ, state = query.data.split(":")
    control_topic = f"iot_project/control/{room}/{typ}"
    msg = {"command": state.upper()}
    mqtt.myPublish(control_topic, msg)

    user = query.from_user.first_name or "User"
    log_action(user, room, typ, state)

    await query.edit_message_text(
        f"✅ {room_icon(room)} {room} {typ} set to {state.upper()}",
        parse_mode="Markdown"
    )

async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Action cancelled.")

async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rooms = sorted(set(d.get('Room', 'Unknown') for d in shared_data))
    rooms = [r for r in rooms if r and r != 'Unknown']
    if not rooms:
        await query.edit_message_text("❗ No room data available.")
        return
    keyboard = [
        [InlineKeyboardButton(f"{room_icon(room)} {room}", callback_data=f"control_room:{room}")]
        for room in rooms
    ]
    await query.edit_message_text(
        "Select a room to control:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not recent_actions:
        await update.message.reply_text("🧾 No recent actions yet.")
        return
    txt = "🧾 *Last actions:*\n\n" + "\n".join(recent_actions[::-1][-10:])
    await update.message.reply_text(txt, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "❓ *Help — What I can do for you:*\n\n"
        "📊 Status → Show last readings per room (respects your °C/°F setting)\n"
        "💡 Control → Choose a room, then toggle *Light* and *Temperature* (Confirm/Cancel)\n"
        "📋 Sensors → List devices from catalog.json\n"
        "🧾 Recent → Last actions with time & user\n"
        f"🖥 Dashboard → Opens {DASHBOARD_URL}\n"
        "⚙️ Settings → Temperature unit & notifications\n"
        "⬅️ Back buttons take you to the previous step."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    header = f"🌐 *Open Dashboard here:* [{DASHBOARD_URL}]({DASHBOARD_URL})\n\n"
    if not shared_data:
        await update.message.reply_text(header + "_No data yet._", parse_mode="Markdown", disable_web_page_preview=True)
        return

    rows = shared_data[-10:][::-1]
    lines = []
    for r in rows:
        ts   = r.get("Timestamp", "")
        rid  = r.get("Device ID", "")
        name = r.get("Device Name", "")
        mtyp = r.get("Measurement Type", "")
        val  = r.get("Value", "")
        unit = r.get("Unit", "")
        room = r.get("Room", "")
        lines.append(f"• [{ts}] 🆔{rid} | {room_icon(room)} {room} — {name} / {mtyp}: {val} {unit}")

    await update.message.reply_text(
        header + "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    prefs = get_user_settings(user_id)

    unit = "🌡 Celsius (°C)" if prefs["temperature_unit"] == "C" else "🌡 Fahrenheit (°F)"
    notif = "🔔 Notifications: ON" if prefs["notifications"] else "🔕 Notifications: OFF"

    keyboard = [
        [InlineKeyboardButton(unit,  callback_data="settings:unit")],
        [InlineKeyboardButton(notif, callback_data="settings:notifications")],
        [InlineKeyboardButton("⬅️ Back", callback_data="settings:back")]
    ]
    await update.message.reply_text(
        "⚙️ *Settings*\n\nAdjust your preferences below:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    prefs = get_user_settings(user_id)

    _, choice = query.data.split(":")
    if choice == "unit":
        prefs["temperature_unit"] = "F" if prefs["temperature_unit"] == "C" else "C"
        unit_label = "🌡 Fahrenheit (°F)" if prefs["temperature_unit"] == "F" else "🌡 Celsius (°C)"
        notif = "🔔 Notifications: ON" if prefs["notifications"] else "🔕 Notifications: OFF"
        kb = [
            [InlineKeyboardButton(unit_label, callback_data="settings:unit")],
            [InlineKeyboardButton(notif,      callback_data="settings:notifications")],
            [InlineKeyboardButton("⬅️ Back",  callback_data="settings:back")]
        ]
        await query.edit_message_text(
            f"⚙️ *Settings*\n\nTemperature unit set to: *{prefs['temperature_unit']}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    elif choice == "notifications":
        prefs["notifications"] = not prefs["notifications"]
        unit_label = "🌡 Fahrenheit (°F)" if prefs["temperature_unit"] == "F" else "🌡 Celsius (°C)"
        notif = "🔔 Notifications: ON" if prefs["notifications"] else "🔕 Notifications: OFF"
        kb = [
            [InlineKeyboardButton(unit_label, callback_data="settings:unit")],
            [InlineKeyboardButton(notif,      callback_data="settings:notifications")],
            [InlineKeyboardButton("⬅️ Back",  callback_data="settings:back")]
        ]
        state = "ON 🔔" if prefs["notifications"] else "OFF 🔕"
        await query.edit_message_text(
            f"⚙️ *Settings*\n\nNotifications turned *{state}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    elif choice == "back":
        await query.edit_message_text("⬅️ Back to main menu.")
        await context.bot.send_message(chat_id=query.message.chat_id, text="Choose an option:", reply_markup=main_menu_markup())


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "📊 Status":
        await status(update, context)
    elif text == "📋 Sensors":
        await sensors(update, context)
    elif text == "💡 Control":
        await control(update, context)
    elif text == "🧾 Recent":
        await recent(update, context)
    elif text == "🖥 Dashboard":
        await dashboard(update, context)
    elif text == "❓ Help":
        await help_cmd(update, context)
    elif text == "⚙️ Settings":
        await settings(update, context)
    else:
        await update.message.reply_text("❗ Unknown command. Use the buttons below.", reply_markup=main_menu_markup())


def build_bot_and_run():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    app.add_handler(CallbackQueryHandler(control_callback, pattern="control_room:"))
    app.add_handler(CallbackQueryHandler(confirm_action,  pattern="cmd:"))
    app.add_handler(CallbackQueryHandler(do_action,       pattern="do:"))
    app.add_handler(CallbackQueryHandler(cancel_action,   pattern="cancel_action"))
    app.add_handler(CallbackQueryHandler(go_back,         pattern="go_back"))

    app.add_handler(CallbackQueryHandler(settings_callback, pattern="settings:"))

    print(f"[BOT] Running with dashboard at {DASHBOARD_URL}")
    app.run_polling()
