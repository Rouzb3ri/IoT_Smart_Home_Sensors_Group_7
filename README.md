# Smart Home Sensors · Group 7

A local temperature/light dashboard with an optional Telegram companion. All sensor readings are **simulated**. Pause/resume controls the simulation, not physical lights or heating.

## Start on Windows

Open this repository folder in VS Code, then use its terminal:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --demo
```

Open **http://127.0.0.1:8080**. Stop with Ctrl+C. Use `--port 8081` if 8080 is occupied.
The demo generates local readings every five seconds without contacting MQTT or Telegram.
Catalog paths are resolved relative to the project, so launching from another working directory works too.

## Dashboard

- Latest value for every configured sensor, organized by room.
- Room filtering and Celsius/Fahrenheit display.
- Live, waiting, stale (over 30 seconds), paused, and offline indicators.
- Pause/resume each simulation and view recent actions from dashboard or Telegram.
- Polling without whole-page reloads, with clear reconnect/error messages.

Readings, actions and Telegram unit preferences are held in memory and reset when the process restarts. History is bounded to 1,000 readings and 50 actions. Edit the catalog with `python catalog_cli.py` while the app is stopped; restart to pick up changes.

## Telegram (optional)

The old source contained an embedded Telegram bot token. **Revoke/replace that token using BotFather before use.** Removing it from the current files does not remove it from existing GitHub history. Never paste the replacement into a chat or commit it.

Set these variables in the same PowerShell terminal that will run the app:

```powershell
$env:TELEGRAM_BOT_TOKEN = 'your-new-bot-token'
$env:TELEGRAM_ALLOWED_USER_IDS = 'your-numeric-telegram-user-id'
.\.venv\Scripts\python.exe main.py --demo --telegram
```

Use a comma-separated list for multiple authorized IDs. Both settings are required; unlisted users are denied access. `.env.example` lists settings, but **the app does not load .env files automatically**.

Use `/start`, `/status`, `/sensors`, `/control`, `/recent`, `/dashboard`, `/settings`, `/help` or the menu buttons. Status shows one latest reading per sensor and its age. Simulation controls require confirmation and only report success after the local state changes. Telegram tests use mocks; live message delivery needs your new token and has not been verified by the automated tests.

The dashboard listens only on `127.0.0.1`. A phone cannot use the computer's localhost address. `DASHBOARD_URL` changes the link sent by the bot; it does not expose the server. Leave it unset until you have a protected reachable address through a separately configured authenticated proxy/VPN. This app has no dashboard login and is not ready for public hosting. Automatic alerts and physical actuator control are future work.

## MQTT (optional)

Without `--demo`, simulated readings are published to and received from MQTT every 10 seconds. `MQTT_BROKER` defaults to `broker.hivemq.com`; `MQTT_PORT` defaults to `1883`. The dashboard shows connection state and automatically reconnects. Each runtime uses a unique client ID.

The sample catalog uses public `iot_project/sensors/...` topics, plaintext MQTT, and no authentication. These are classroom/demo defaults. Other broker users can see or spoof traffic. Use local demo mode for private previews. Before real home deployment, configure an authenticated TLS broker and a private topic namespace across catalog and clients. Broker addresses in catalog service metadata are descriptive; runtime uses `MQTT_BROKER`.

## GitHub, VS Code and Copilot

Upstream: https://github.com/Rouzb3ri/IoT_Smart_Home_Sensors_Group_7

Keep this folder as the shared working copy. Save changes in VS Code, review its Source Control diff, commit to a feature branch and push. Pull changes before starting work on another computer; avoid editing the same files simultaneously from two agents. Google Drive file sync is separate from Git: use GitHub for version history, and pause competing Drive edits during Git operations.

`.github/copilot-instructions.md` provides repository guidance for Copilot; `AGENTS.md` provides the same conventions to coding agents. Open this exact folder in VS Code so the instructions are in scope. Check the references on a Copilot response to confirm the instructions were used. This does not share Copilot chats with ChatGPT or authenticate a Copilot subscription.

```powershell
git status
git pull --ff-only
# After saving and reviewing your work:
git add <specific-files>
git commit -m "Describe the change"
git push
```

Run pull only with a clean working tree. A GitHub review branch is separate from `main`; merge its pull request when reviewed, then update your local branch. Do not use `git push --force` to resolve sync problems.

## Checks and architecture

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover imports without service startup, catalog sensor construction, current/stale/paused readings, bounded history, malformed MQTT messages, subscription retry, Telegram authorization/confirmation/chunking, and a real local HTTP demo with control validation. No live Telegram, MQTT or physical-device operations occur in tests. GitHub Actions runs the same checks.

| File | Purpose |
| --- | --- |
| `main.py` | Explicit startup and shutdown; demo or MQTT mode |
| `Webserver.py`, `dashboard.html` | CherryPy JSON endpoints and responsive dashboard |
| `sensor_views.py` | Consistent current status and temperature formatting |
| `shared_memory.py` | Synchronized state, bounded history and simulation controls |
| `telegram_bot_N.py` | Restricted Telegram commands with no import-time networking |
| `catalog_cli.py`, `catalog.json`, `sensor_device.py` | Device registry and simulated measurements |
| `MyMQTT.py`, `publisher.py`, `subscriber.py` | MQTT 2.x integration and validated readings |

The README previously referred to missing `app.py`, `catalog_manager.py` and `webserver.app` modules. Startup now uses the files present in this repository.
