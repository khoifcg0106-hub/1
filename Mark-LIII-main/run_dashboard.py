#!/usr/bin/env python3
"""
Standalone dashboard runner — boots the JARVIS web dashboard without the
PyQt6 desktop app.  Intended for headless / preview environments where the
full voice assistant (display, audio, microphone) cannot run.

A long-lived demo session key is pre-generated so the login page auto-
redirects into the dashboard with no manual key entry.
"""

import asyncio
import secrets

from dashboard.server import DashboardServer
from fastapi.responses import HTMLResponse


async def main() -> None:
    ds = DashboardServer()

    # Pre-register a long-lived demo key (1 year) so /demo always works.
    demo_key = ds.new_key(expiry_secs=86400 * 365)

    # ── /demo route: create a session token, stash it client-side, redirect ──
    @ds.app.get("/demo")
    async def demo_login():
        tok = secrets.token_urlsafe(32)
        ds._tokens.add(tok)
        ds._token_keys[tok] = demo_key
        ds._aes_key(demo_key)
        return HTMLResponse(
            "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
            "<title>JARVIS</title></head>"
            "<body style='background:#07090f;color:#dde3ed;font-family:sans-serif;"
            "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
            "<p style='color:#5e6a7e'>Connecting to JARVIS…</p>"
            "<script>\n"
            f"  sessionStorage.setItem('jarvis_token','{tok}');\n"
            f"  sessionStorage.setItem('jarvis_key','{demo_key}');\n"
            "  location.replace('/');\n"
            "</script></body></html>"
        )

    # ── Auto-redirect the login page to /demo (no manual key needed) ──
    ds._login_html = ds._login_html.replace(
        "<script>",
        "<script>location.replace('/demo');</script>\n    <script>",
        1,
    )

    # ── Pre-populate the feed so the dashboard isn't empty ──
    ds._history.append({
        "type": "log", "speaker": "jarvis",
        "text": "👋 Welcome! JARVIS dashboard is running in demo mode.",
    })
    ds._history.append({
        "type": "sys",
        "text": "Demo mode — the desktop app isn't connected, "
                "so commands won't be processed.",
    })

    print(f"[Dashboard] Demo key: {demo_key}")
    print("[Dashboard] Open /demo to auto-login, or enter the key on /login")
    await ds.serve()


if __name__ == "__main__":
    asyncio.run(main())
