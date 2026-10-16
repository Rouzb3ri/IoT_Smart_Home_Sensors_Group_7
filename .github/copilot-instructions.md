# Project context for GitHub Copilot

Follow AGENTS.md and README.md at the repository root.
This Python app combines a CherryPy dashboard, simulated temperature/light sensors, optional MQTT and optional python-telegram-bot.
Use `python main.py --demo` for local previews and `python -m unittest discover -s tests -v` for tests.
The dashboard and Telegram share sensor_views.py and shared_memory.py. Preserve latest-per-sensor readings, stale indicators, synchronized bounded state and accurate simulation labels.
Do not add physical light/heating controls without an actuator protocol and delivery acknowledgment.
Keep imports free of network side effects; mock Telegram and MQTT in tests.
Credentials belong only in environment variables. Never commit bot tokens or .env files.
Keep dashboard UI usable on mobile, keyboard accessible and resilient to API failures.
