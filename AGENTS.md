# AGENTS.md — Base44 setup notes for Mark LIII (JARVIS)

## What this project is

Mark L III (JARVIS) is a cross-platform **desktop voice AI assistant** built with
PyQt6, the Google Gemini Live API, and local audio/screen capture.  The full
app (`main.py` + `ui.py`) requires a display, microphone, and speakers — it
**cannot run in a headless container**.

The repo also ships a **FastAPI web dashboard** (`dashboard/server.py`) that
serves as a remote-control interface for the desktop app.  This is the only
component that can run in the preview.

## How the preview is set up

- `docker-compose.base44.yml` — single `dashboard` service.
- `Mark-LIII-main/Dockerfile.dashboard` — `python:3.12-slim` + dashboard-only
  deps (fastapi, uvicorn, cryptography, python-multipart).  Source is
  bind-mounted, not baked into the image.
- `Mark-LIII-main/run_dashboard.py` — standalone runner that boots
  `DashboardServer` without the PyQt6 app.  Pre-generates a long-lived demo
  session key, adds a `/demo` auto-login route, and injects a redirect from
  `/login` → `/demo` so the preview loads straight into the dashboard.
- Port mapping: `3000:8000` (dashboard listens on 8000 inside the container).
- Healthcheck: `GET /login` returns 200.

## What works in the preview

- The dashboard UI loads, WebSocket connects, file upload/listing endpoints
  respond, and the AES-256 encryption badge activates.
- **Commands are not processed** — there is no desktop app on the other end of
  the command queue.  This is expected in demo mode.

## What the full app needs (not available in this environment)

- **Google Gemini API key** — stored in `config/api_keys.json` under
  `gemini_api_key`.  Required for the voice assistant to function.
- PyQt6, audio devices (sounddevice), screen capture (mss), desktop automation
  (pyautogui) — none of which work headless.

## Useful commands

```bash
# Start the dashboard
docker compose -f docker-compose.base44.yml up -d --build

# Check status / logs
docker compose -f docker-compose.base44.yml ps
docker compose -f docker-compose.base44.yml logs -f dashboard

# Test endpoints
curl -s http://localhost:3000/login    # login page (auto-redirects to /demo)
curl -s http://localhost:3000/demo      # auto-login, returns token + redirect
curl -s http://localhost:3000/          # dashboard app (needs token in sessionStorage)
```
