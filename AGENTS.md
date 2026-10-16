# Smart Home Sensors

Read README.md before changing startup, dashboard or Telegram behavior.
Python 3.11+. Install with `python -m pip install -r requirements.txt`.
Run `python -m unittest discover -s tests -v` for regression tests.
Preview with `python main.py --demo`. This mode uses local simulated readings and no MQTT network.
Do not start Telegram, publish MQTT messages or contact physical devices during tests.
Use environment variables for credentials. Never commit tokens, .env files or real user IDs.
Dashboard and Telegram must use sensor_views.py for current readings and shared_memory.py for state/control.
Controls pause/resume simulations only; never claim physical actuator success without acknowledgments.
Keep state access synchronized and history bounded. Show waiting, stale, paused and offline states honestly.
Use DOM textContent for catalog values and plain Telegram text to avoid markup injection.
Importing modules must not start network connections, servers or worker threads.
