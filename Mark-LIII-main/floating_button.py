"""
Floating Button — JARVIS-1 always-on-top HUD anchor (v5 Design Specification).

Implements the "FLOATING BUTTON v5 SPECIFICATION" from 8K layer breakdown:
  - Dual counter-rotating CW & CCW dashed rings with organic dash patterns
  - Chevron Arc Reactor core + 7 planetary positioning dots
  - 10 states with exact spec colours & glyphs
  - Left click  -> 6-node radial quick menu (VOICE / CHAT / QUICK / SLEEP / SETUP / CENTER)
  - Right click -> Quick Actions drawer (context menu)
  - Double click -> opens the Full Command Center (MainWindow)
  - Drag         -> free repositioning, position saved to config
  - Mouse wheel  -> cycle the 4 size presets (40 / 56 / 72 / 88 px)

Self-contained: does not modify ui.py / main.py behaviour. Wire it in with:

    from floating_button import FloatingButton
    fab = FloatingButton(on_open_center=lambda: (win.show(), win.raise_(), win.activateWindow()))
    fab.show()
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
)
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
FB_CONFIG_FILE = CONFIG_DIR / "floating_button.json"

# ── 10 states, exact spec colours ───────────────────────────────────────────
STATES = {
    "IDLE":        {"color": "#00e7ff", "glyph": "▲"},
    "HOVER":       {"color": "#00e7ff", "glyph": "▲"},
    "ACTIVE":      {"color": "#00e7ff", "glyph": "▲"},
    "LISTENING":   {"color": "#00d4ff", "glyph": "◉"},
    "SPEAKING":    {"color": "#209dff", "glyph": "≈"},
    "THINKING":    {"color": "#ffb12b", "glyph": "◇"},
    "TOOL ACTIVE": {"color": "#80ef28", "glyph": "⚙"},
    "MUTED":       {"color": "#ff4760", "glyph": "⊘"},
    "SLEEPING":    {"color": "#718995", "glyph": "◌"},
    "ALERT":       {"color": "#ff4760", "glyph": "!"},
}
DEFAULT_STATE = "IDLE"

# Size presets: (diameter_px) — 40 compact / 56 default / 72 large / 88 XL
SIZE_PRESETS = [40, 56, 72, 88]
DEFAULT_SIZE_IDX = 1  # 56px

RADIAL_NODES = [
    ("VOICE", "🎙"),
    ("CHAT", "💬"),
    ("QUICK", "▦"),
    ("SLEEP", "⏻"),
    ("SETUP", "⚙"),
    ("CENTER", "▣"),
]


def _load_fb_config() -> dict:
    try:
        return json.loads(FB_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_fb_config(data: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        FB_CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


class RadialMenu(QWidget):
    """6-node radial quick menu that pops out around the floating button."""

    node_clicked = pyqtSignal(str)

    def __init__(self, anchor: QWidget, radius: int = 82):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._anchor = anchor
        self._radius = radius
        self._node_size = 38
        self._t = 0.0
        
        span = int((radius + self._node_size) * 2 + 30)
        self.setFixedSize(span, span)
        self._reposition()

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _reposition(self):
        c = self._anchor.geometry().center()
        self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)

    def _step(self):
        self._t = min(1.0, self._t + 0.14)
        self.update()
        if self._t >= 1.0:
            self._tmr.stop()

    def paintEvent(self, _event):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx, cy = self.width() / 2.0, self.height() / 2.0
        t = self._t
        
        # Outer dashed connecting orbital
        p.setPen(QPen(QColor(0, 231, 255, int(80 * t)), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), (self._radius + 18) * t, (self._radius + 18) * t)

        radius = self._radius * t
        n = len(RADIAL_NODES)
        for i, (act, icon) in enumerate(RADIAL_NODES):
            ang = (2 * math.pi * i / n) - math.pi / 2
            nx = cx + radius * math.cos(ang)
            ny = cy + radius * math.sin(ang)

            # Node card / bubble
            p.setBrush(QColor(4, 16, 24, int(245 * t)))
            p.setPen(QPen(QColor(0, 231, 255, int(220 * t)), 1.2))
            p.drawEllipse(QPointF(nx, ny), self._node_size / 2.0, self._node_size / 2.0)

            # Icon
            p.setPen(QPen(QColor(0, 231, 255, int(255 * t)), 1))
            p.setFont(QFont("Segoe UI Emoji", 11))
            p.drawText(
                QRectF(nx - self._node_size / 2.0, ny - self._node_size / 2.0,
                       self._node_size, self._node_size),
                Qt.AlignmentFlag.AlignCenter,
                icon
            )

            # Sub-label
            p.setFont(QFont("Courier New", 6, QFont.Weight.Bold))
            p.setPen(QColor(139, 190, 203, int(220 * t)))
            p.drawText(
                QRectF(nx - 28, ny + self._node_size / 2.0 + 1, 56, 12),
                Qt.AlignmentFlag.AlignCenter,
                act
            )
        p.end()

    def mousePressEvent(self, event):
        pos = event.position()
        cx, cy = self.width() / 2.0, self.height() / 2.0
        radius = self._radius * self._t
        n = len(RADIAL_NODES)
        hit_radius = self._node_size / 2.0 + 4
        
        for i, (name, _icon) in enumerate(RADIAL_NODES):
            ang = (2 * math.pi * i / n) - math.pi / 2
            nx = cx + radius * math.cos(ang)
            ny = cy + radius * math.sin(ang)
            if math.hypot(pos.x() - nx, pos.y() - ny) <= hit_radius:
                self.node_clicked.emit(name)
                self.close()
                return
        self.close()

    def focusOutEvent(self, _event):
        self.close()


class FloatingButton(QWidget):
    """The always-on-top JARVIS-1 floating anchor button (v5 Reference)."""

    open_command_center = pyqtSignal()
    radial_action = pyqtSignal(str)

    def __init__(self, on_open_center=None, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        cfg = _load_fb_config()
        self._size_idx = cfg.get("size_idx", DEFAULT_SIZE_IDX)
        self._state = DEFAULT_STATE
        self._hover = False
        self._pressed = False
        self._drag_offset = None
        self._dragged = False
        self._radial_menu: RadialMenu | None = None

        # v5 Motion Dynamics
        self._spin_cw = 0.0
        self._spin_ccw = 0.0
        self._pulse = 0.0

        if on_open_center:
            self.open_command_center.connect(on_open_center)

        self._apply_size()
        screen = QApplication.primaryScreen().availableGeometry()
        default_x = screen.right() - self.width() - 32
        default_y = screen.bottom() - self.height() - 32
        x = cfg.get("x", default_x)
        y = cfg.get("y", default_y)
        self.move(x, y)

        self.setMouseTracking(True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # ── sizing ───────────────────────────────────────────────────────────
    def _apply_size(self):
        d = SIZE_PRESETS[self._size_idx]
        pad = int(d * 0.4)
        self.resize(d + pad * 2, d + pad * 2)

    def _diameter(self) -> int:
        return SIZE_PRESETS[self._size_idx]

    # ── state API (call from main.py: fab.set_state("LISTENING")) ───────
    def set_state(self, state: str):
        state = state.upper()
        if state in STATES:
            self._state = state
            self.update()

    # ── animation ─────────────────────────────────────────────────────
    def _tick(self):
        dim = self._state == "SLEEPING"
        sp = 0.4 if dim else 1.0
        self._spin_cw  = (self._spin_cw  + 2.0 * sp) % 360
        self._spin_ccw = (self._spin_ccw - 3.6 * sp) % 360
        self._pulse    = (self._pulse    + 0.05 * sp) % (math.pi * 2)
        self.update()

    # ── painting (v5 Specification) ──────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        info = STATES.get(self._state, STATES[DEFAULT_STATE])
        color = QColor(info["color"])
        dim = self._state == "SLEEPING"
        
        W, H = self.width(), self.height()
        cx, cy = W / 2.0, H / 2.0
        
        # Scale to match standard 220px reference coordinate space
        scale = min(W, H) / 220.0
        
        p.save()
        p.translate(cx, cy)
        p.scale(scale, scale)

        # Soft outer radial halo glow
        glow = QRadialGradient(0, 0, 105)
        glow_c = QColor(color)
        glow_c.setAlpha(int(255 * (0.24 if self._hover else (0.06 if dim else 0.14))))
        glow.setColorAt(0, glow_c)
        glow_c0 = QColor(color)
        glow_c0.setAlpha(0)
        glow.setColorAt(1, glow_c0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(0, 0), 105, 105)

        # Stationary outer rings
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), int(255 * (0.06 if dim else 0.14))), 1))
        p.drawEllipse(QPointF(0, 0), 92, 92)
        p.setPen(QPen(color, 1))
        p.drawEllipse(QPointF(0, 0), 85, 85)

        # Spin 1 (CW Ring)
        p.save()
        p.rotate(self._spin_cw)
        pen1 = QPen(color, 1.2)
        pen1.setDashPattern([7, 4, 1, 5])
        p.setPen(pen1)
        p.drawEllipse(QPointF(0, 0), 76, 76)
        
        pen1b = QPen(QColor(color.red(), color.green(), color.blue(), 128), 1)
        pen1b.setDashPattern([2, 5])
        p.setPen(pen1b)
        p.drawEllipse(QPointF(0, 0), 65, 65)
        p.restore()

        # Spin 2 (CCW Ring)
        p.save()
        p.rotate(self._spin_ccw)
        pen2 = QPen(color, 2.0)
        pen2.setDashPattern([22, 4, 4, 8])
        p.setPen(pen2)
        p.drawEllipse(QPointF(0, 0), 52, 52)
        
        pen2b = QPen(QColor(color.red(), color.green(), color.blue(), 128), 1)
        pen2b.setDashPattern([1, 6])
        p.setPen(pen2b)
        p.drawEllipse(QPointF(0, 0), 42, 42)
        p.restore()

        # Pulse Ring
        pulse_r = 38 * (0.85 + 0.25 * (0.5 + 0.5 * math.sin(self._pulse)))
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 130), 1))
        p.drawEllipse(QPointF(0, 0), pulse_r, pulse_r)

        # Core Radial Gradient & Backdrop
        g = QRadialGradient(0, 0, 42)
        g.setColorAt(0, QColor("#ffffff"))
        g.setColorAt(0.06, color)
        c_mid = QColor(color.red(), color.green(), color.blue(), 80)
        g.setColorAt(0.40, c_mid)
        c_fade = QColor(color.red(), color.green(), color.blue(), 0)
        g.setColorAt(1.0, c_fade)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, 0), 42, 42)

        # Dark Inner Chassis
        p.setPen(QPen(color, 1.5))
        p.setBrush(QColor(4, 16, 24, int(235 * (0.6 if dim else 0.95))))
        p.drawEllipse(QPointF(0, 0), 32, 32)

        if self._pressed:
            p.setBrush(QColor(color.red(), color.green(), color.blue(), 80))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(0, 0), 32, 32)

        # 7 Planetary Positioning Dots around core
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(7):
            ang = math.radians(i * (360 / 7))
            px = 25 * math.cos(ang)
            py = 25 * math.sin(ang)
            p.drawEllipse(QPointF(px, py), 1.8, 1.8)

        # Center Arc Reactor Glyph / Chevron Core
        p.setPen(QPen(color, 1))
        p.setFont(QFont("Segoe UI Emoji", 14, QFont.Weight.Bold))
        p.drawText(QRectF(-20, -20, 40, 40), Qt.AlignmentFlag.AlignCenter, info["glyph"])

        p.restore()
        p.end()

    # ── mouse interaction ─────────────────────────────────────────────
    def enterEvent(self, _event):
        self._hover = True
        self.update()

    def leaveEvent(self, _event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        self._pressed = True
        self._dragged = False
        self._drag_offset = event.globalPosition().toPoint() - self.pos()
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            if (new_pos - self.pos()).manhattanLength() > 3:
                self._dragged = True
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self._drag_offset = None
        self.update()
        if self._dragged:
            cfg = _load_fb_config()
            cfg.update({"x": self.x(), "y": self.y(), "size_idx": self._size_idx})
            _save_fb_config(cfg)
            self._dragged = False
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_radial()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_quick_actions()

    def mouseDoubleClickEvent(self, _event):
        if self._radial_menu:
            self._radial_menu.close()
            self._radial_menu = None
        self.open_command_center.emit()

    def wheelEvent(self, event):
        delta = 1 if event.angleDelta().y() > 0 else -1
        self._size_idx = max(0, min(len(SIZE_PRESETS) - 1, self._size_idx + delta))
        old_center = self.pos() + self.rect().center()
        self._apply_size()
        self.move(old_center - self.rect().center())
        self.update()
        cfg = _load_fb_config()
        cfg.update({"x": self.x(), "y": self.y(), "size_idx": self._size_idx})
        _save_fb_config(cfg)

    # ── radial menu / quick actions ──────────────────────────────────
    def _toggle_radial(self):
        if self._radial_menu and self._radial_menu.isVisible():
            self._radial_menu.close()
            self._radial_menu = None
            return
        self._radial_menu = RadialMenu(self)
        self._radial_menu.node_clicked.connect(self._on_radial_node)
        self._radial_menu.show()
        self._radial_menu.raise_()

    def _on_radial_node(self, name: str):
        self._radial_menu = None
        if name == "CENTER":
            self.open_command_center.emit()
        else:
            self.radial_action.emit(name)

    def _show_quick_actions(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#04141c; color:#cfeaf5; border:1px solid #104d5d; }"
            "QMenu::item:selected { background:#00e7ff; color:#00070c; }"
        )
        act_center = menu.addAction("Open Command Center")
        act_mute = menu.addAction("Toggle mute")
        act_sleep = menu.addAction("Sleep")
        menu.addSeparator()
        act_quit = menu.addAction("Quit JARVIS-1")
        chosen = menu.exec(QCursor.pos())
        if chosen == act_center:
            self.open_command_center.emit()
        elif chosen == act_mute:
            self.radial_action.emit("MUTE_TOGGLE")
        elif chosen == act_sleep:
            self.radial_action.emit("SLEEP")
        elif chosen == act_quit:
            QApplication.instance().quit()
