"""
AlgoBotPro v1.0 — Android App (Kivy)
NSE Trading Bot — Zerodha Integration
"""

import sys, os, json, hashlib, threading, time, csv, math, traceback
import queue, sqlite3, collections, datetime

# ── Kivy imports ─────────────────────────────────────────────────────────────
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import StringProperty, BooleanProperty, NumericProperty

# ── Try optional imports ──────────────────────────────────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from kiteconnect import KiteConnect, KiteTicker
    HAS_KITE = True
except ImportError:
    HAS_KITE = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# ── Android storage path ──────────────────────────────────────────────────────
try:
    from android.storage import app_storage_path
    BASE = app_storage_path()
except ImportError:
    BASE = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE, "config.json")
USERS_FILE  = os.path.join(BASE, "users.json")
TRADES_FILE = os.path.join(BASE, "trades_log.csv")
DB_FILE     = os.path.join(BASE, "trades.db")

# ── Colors ────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#0F172A",
    "sidebar":   "#1E293B",
    "card":      "#1E293B",
    "border":    "#334155",
    "accent":    "#7C3AED",
    "accent2":   "#A855F7",
    "green":     "#22C55E",
    "red":       "#EF4444",
    "amber":     "#F59E0B",
    "blue":      "#3B82F6",
    "muted":     "#94A3B8",
    "text":      "#F1F5F9",
    "white":     "#FFFFFF",
}

# ── Default Config ────────────────────────────────────────────────────────────
DEFAULT_CFG = {
    "mode": "paper", "capital": 100000, "risk_pct": 1.5, "max_pos": 5,
    "broker": "Zerodha", "api_key": "", "api_secret": "",
    "tg_token": "", "tg_chat": "", "tg_command_password": "",
    "tg_on_signal": True, "tg_on_order": True, "tg_on_squareoff": True,
    "tg_on_daily_report": True, "tg_on_loss_limit": True,
    "bot_start": "09:15", "bot_stop": "15:25",
    "min_trade": 1500, "profit_lock_pct": 50,
    "auto_squareoff_mins": 5,
    "theme": "dark", "sound_alerts": True, "confirm_orders": False,
    "daily_loss_limit_pct": 3.0, "daily_target_pct": 10.0,
    "auto_squareoff": True,
    "broker_password": "", "access_token": "",
    "gemini_key": "",
    "max_positions": 5, "consecutive_loss_limit": 3,
    "scan_nifty": True, "scan_banknifty": True, "scan_finnifty": True,
    "scan_midcpnifty": False,
    "strat_momentum_on": True, "strat_reversal_on": True,
    "strat_supertrend_on": True, "strat_bollinger_on": True,
    "strat_short_strangle_on": False, "strat_iron_condor_on": False,
    "confidence_gate": 55, "signal_interval_s": 3,
    "black_swan_on": True, "news_window_block": True,
    "bs_vix_spike_pct": 2.0, "bs_price_crash_pct": 1.5,
    "sl_pct": 0.4, "t1_pct": 0.6, "t2_pct": 1.0,
    "rsi_period": 9, "macd_fast": 5, "macd_slow": 13, "macd_signal": 4,
    "atr_period": 7, "supertrend_period": 10, "supertrend_multiplier": 3.0,
    "bb_period": 20, "bb_stddev": 2.0,
    "trailing_sl_on": True, "trailing_sl_activation_pct": 0.5,
    "adx_min_trend": 18, "mtf_enabled": True,
    "cooldown_paper_s": 45, "cooldown_live_s": 75,
    "regime_detection": True, "event_guard": True,
    "strategy_winrate_min": 30, "strategy_sample_size": 20,
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def load_cfg():
    cfg = dict(DEFAULT_CFG)
    if os.path.exists(CONFIG_FILE):
        try: cfg.update(json.loads(open(CONFIG_FILE).read()))
        except: pass
    return cfg

def save_cfg(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Save cfg error: {e}")

def load_users():
    if os.path.exists(USERS_FILE):
        try: return json.loads(open(USERS_FILE).read())
        except: pass
    users = {"admin": {"password": hash_pw("admin123"), "name": "Admin Trader"}}
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return users

def now_ist():
    utc = datetime.datetime.now(datetime.timezone.utc)
    return (utc + datetime.timedelta(hours=5, minutes=30)).replace(tzinfo=None)

def market_status(bot_start="09:15", bot_stop="15:25"):
    now = now_ist()
    wd = now.weekday()
    mins = now.hour * 60 + now.minute
    bs_h, bs_m = map(int, bot_start.split(":"))
    be_h, be_m = map(int, bot_stop.split(":"))
    bot_open  = bs_h * 60 + bs_m
    bot_close = be_h * 60 + be_m
    if wd >= 5:
        return "CLOSED", C["red"], "Weekend"
    if mins < bot_open:
        return "PRE-MARKET", C["amber"], f"Opens {bot_start}"
    if mins >= bot_close:
        return "CLOSED", C["red"], f"Bot stopped"
    return "TRADING", C["green"], f"Active until {bot_stop}"

# ── SQLite trades ─────────────────────────────────────────────────────────────
TRADE_HEADERS = [
    "date","time","order_id","symbol","side","direction",
    "qty","entry_price","exit_price","pnl","net_pnl","strategy","status"
]

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, time TEXT, order_id TEXT, symbol TEXT, side TEXT,
            direction TEXT, qty INTEGER, entry_price REAL, exit_price REAL,
            pnl REAL, net_pnl REAL, strategy TEXT, status TEXT
        )""")
        conn.commit(); conn.close()
    except Exception as e:
        print(f"DB init error: {e}")

def load_trades():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 100").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except: return []

def save_trade(trade):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""INSERT INTO trades
            (date,time,order_id,symbol,side,direction,qty,entry_price,exit_price,pnl,net_pnl,strategy,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [trade.get(h,"") for h in TRADE_HEADERS])
        conn.commit(); conn.close()
    except Exception as e:
        print(f"Save trade error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def hex_color(h, a=1):
    h = h.lstrip('#')
    r,g,b = int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255
    return (r,g,b,a)

class CardWidget(BoxLayout):
    def __init__(self, bg=None, radius=12, **kwargs):
        super().__init__(**kwargs)
        self._bg_color = bg or C["card"]
        self._radius = radius
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*hex_color(self._bg_color))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])

class TopBar(BoxLayout):
    def __init__(self, title="AlgoBotPro", on_menu=None, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None,
                         height=dp(56), padding=[dp(16),dp(8)], spacing=dp(8), **kwargs)
        with self.canvas.before:
            Color(*hex_color(C["sidebar"]))
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        if on_menu:
            btn = Button(text="☰", size_hint=(None,1), width=dp(44),
                         background_color=(0,0,0,0), color=hex_color(C["text"]),
                         font_size=dp(22))
            btn.bind(on_press=on_menu)
            self.add_widget(btn)

        lbl = Label(text=title, color=hex_color(C["text"]),
                    font_size=dp(18), bold=True, halign='left')
        lbl.bind(size=lbl.setter('text_size'))
        self.add_widget(lbl)

        self._status_lbl = Label(text="●", color=hex_color(C["muted"]),
                                  font_size=dp(14), size_hint=(None,1), width=dp(60),
                                  halign='right')
        self._status_lbl.bind(size=self._status_lbl.setter('text_size'))
        self.add_widget(self._status_lbl)

    def set_status(self, text, color):
        self._status_lbl.text = f"● {text}"
        self._status_lbl.color = hex_color(color)

    def _upd(self, *a):
        self._rect.pos = self.pos; self._rect.size = self.size

def make_btn(text, bg=None, color=None, height=dp(46), font_size=dp(14), **kwargs):
    bg = bg or C["accent"]
    color = color or C["white"]
    btn = Button(text=text, size_hint_y=None, height=height,
                 background_color=(0,0,0,0),
                 color=hex_color(color), font_size=font_size,
                 bold=True, **kwargs)
    with btn.canvas.before:
        clr = Color(*hex_color(bg))
        rr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[10])
    def upd(*a): rr.pos=btn.pos; rr.size=btn.size
    btn.bind(pos=upd, size=upd)
    btn._bg_clr = clr
    btn._bg_rr  = rr
    return btn

def make_label(text, color=None, font_size=dp(13), bold=False, **kwargs):
    color = color or C["text"]
    lbl = Label(text=text, color=hex_color(color), font_size=font_size,
                bold=bold, **kwargs)
    return lbl

def make_input(hint="", text="", password=False, **kwargs):
    inp = TextInput(hint_text=hint, text=str(text),
                    background_color=hex_color(C["bg"]),
                    foreground_color=hex_color(C["text"]),
                    hint_text_color=hex_color(C["muted"]),
                    cursor_color=hex_color(C["accent"]),
                    size_hint_y=None, height=dp(44),
                    padding=[dp(12), dp(10)],
                    font_size=dp(13),
                    password=password,
                    multiline=False, **kwargs)
    return inp

def make_section(title, parent):
    lbl = Label(text=f"  {title}", color=hex_color(C["accent"]),
                font_size=dp(13), bold=True,
                size_hint_y=None, height=dp(32),
                halign='left')
    lbl.bind(size=lbl.setter('text_size'))
    parent.add_widget(lbl)

def scroll_wrap(inner):
    sv = ScrollView(size_hint=(1,1), bar_width=dp(3),
                    bar_color=hex_color(C["accent"]),
                    scroll_type=['bars','content'])
    sv.add_widget(inner)
    return sv

# ═══════════════════════════════════════════════════════════════════════════════
#  PAPER ENGINE (Simulation)
# ═══════════════════════════════════════════════════════════════════════════════
class PaperEngine:
    """Simulates trading signals and paper trades."""
    def __init__(self, cfg, log_cb=None):
        self.cfg = cfg
        self.log_cb = log_cb
        self.running = False
        self.positions = {}
        self.prices = {"NIFTY":24578.0,"BANKNIFTY":52140.0,
                       "FINNIFTY":23890.0,"MIDCPNIFTY":13420.0}
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self._thread = None
        self._signal_cbs = []
        self._price_cbs  = []
        self._trade_cbs  = []

    def log(self, msg, level="info"):
        if self.log_cb:
            try: self.log_cb(msg, level)
            except: pass

    def start(self):
        if self.running: return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log("✅ Bot started (Paper Mode)", "ok")

    def stop(self):
        self.running = False
        self.log("🛑 Bot stopped", "warn")

    def _run(self):
        while self.running:
            try:
                self._update_prices()
                self._check_signals()
                time.sleep(float(self.cfg.get("signal_interval_s", 3)))
            except Exception as e:
                self.log(f"Engine error: {e}", "error")
                time.sleep(5)

    def _update_prices(self):
        import random
        for sym in self.prices:
            chg = random.uniform(-0.003, 0.003)
            self.prices[sym] = round(self.prices[sym] * (1 + chg), 2)
        for cb in self._price_cbs:
            try: cb(dict(self.prices))
            except: pass

    def _check_signals(self):
        import random
        if not self.running: return
        status, _, _ = market_status(
            self.cfg.get("bot_start","09:15"),
            self.cfg.get("bot_stop","15:25"))
        if status != "TRADING": return

        cap_used = len(self.positions) * self.cfg.get("min_trade", 1500)
        cap_avail = self.cfg.get("capital", 100000) - cap_used
        max_pos = self.cfg.get("max_positions", 5)

        if len(self.positions) < max_pos and cap_avail >= self.cfg.get("min_trade",1500):
            if random.random() < 0.15:
                syms = []
                if self.cfg.get("scan_nifty",True): syms.append("NIFTY")
                if self.cfg.get("scan_banknifty",True): syms.append("BANKNIFTY")
                if self.cfg.get("scan_finnifty",True): syms.append("FINNIFTY")
                if not syms: return

                sym = random.choice(syms)
                strategies = []
                if self.cfg.get("strat_momentum_on",True): strategies.append("Momentum")
                if self.cfg.get("strat_reversal_on",True): strategies.append("Reversal")
                if self.cfg.get("strat_supertrend_on",True): strategies.append("Supertrend")
                if self.cfg.get("strat_bollinger_on",True): strategies.append("Bollinger")
                if not strategies: return

                strat = random.choice(strategies)
                side = random.choice(["CE","PE"])
                price = self.prices.get(sym, 24000)
                strike = round(price / 50) * 50
                opt_sym = f"{sym}{strike}{side}"
                opt_price = random.uniform(80, 250)
                conf = random.randint(55, 90)

                if conf >= self.cfg.get("confidence_gate", 55):
                    self._enter_trade(opt_sym, strat, side, opt_price, conf)

        # Check exits for open positions
        for sym in list(self.positions.keys()):
            pos = self.positions[sym]
            current = pos["entry"] * random.uniform(0.95, 1.08)
            pnl_pct = (current - pos["entry"]) / pos["entry"] * 100
            if pnl_pct >= self.cfg.get("t2_pct", 1.0) or pnl_pct <= -self.cfg.get("sl_pct", 0.4):
                self._exit_trade(sym, current)

    def _enter_trade(self, sym, strat, side, price, conf):
        now = now_ist()
        qty = max(1, int(self.cfg.get("min_trade",1500) / price))
        self.positions[sym] = {
            "symbol": sym, "strategy": strat,
            "side": side, "entry": price,
            "qty": qty, "time": now.strftime("%H:%M:%S"),
            "confidence": conf
        }
        msg = f"📈 SIGNAL [{strat}] {sym} @ ₹{price:.0f} | Conf:{conf}%"
        self.log(msg, "ok")
        for cb in self._signal_cbs:
            try: cb({"symbol":sym,"strategy":strat,"side":side,
                     "price":price,"confidence":conf})
            except: pass

    def _exit_trade(self, sym, exit_price):
        if sym not in self.positions: return
        pos = self.positions.pop(sym)
        pnl = (exit_price - pos["entry"]) * pos["qty"]
        pnl = round(pnl, 2)
        self.daily_pnl += pnl
        self.total_trades += 1
        if pnl >= 0: self.wins += 1
        else: self.losses += 1
        now = now_ist()
        trade = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "order_id": f"PAPER{int(time.time())}",
            "symbol": sym, "side": pos["side"],
            "direction": "LONG",
            "qty": pos["qty"],
            "entry_price": pos["entry"],
            "exit_price": exit_price,
            "pnl": pnl, "net_pnl": round(pnl*0.98,2),
            "strategy": pos["strategy"],
            "status": "COMPLETE"
        }
        save_trade(trade)
        emoji = "✅" if pnl >= 0 else "❌"
        msg = f"{emoji} EXIT {sym} | P&L: ₹{pnl:+.2f}"
        self.log(msg, "ok" if pnl >= 0 else "error")
        for cb in self._trade_cbs:
            try: cb(trade)
            except: pass

    def get_stats(self):
        wr = (self.wins/self.total_trades*100) if self.total_trades > 0 else 0
        return {
            "daily_pnl": self.daily_pnl,
            "total_trades": self.total_trades,
            "wins": self.wins, "losses": self.losses,
            "win_rate": wr,
            "open_positions": len(self.positions),
            "prices": dict(self.prices)
        }

# ═══════════════════════════════════════════════════════════════════════════════
#  SCREENS
# ═══════════════════════════════════════════════════════════════════════════════

# ── LOGIN SCREEN ──────────────────────────────────────────────────────────────
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*hex_color(C["bg"]))
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self._build()

    def _upd(self, *a):
        self._bg.pos=self.pos; self._bg.size=self.size

    def _build(self):
        root = FloatLayout()

        box = BoxLayout(orientation='vertical', spacing=dp(16),
                        padding=[dp(32),dp(0)],
                        size_hint=(0.9, None), height=dp(480),
                        pos_hint={'center_x':0.5,'center_y':0.5})

        # Logo
        logo = Label(text="🤖", font_size=dp(64), size_hint_y=None, height=dp(80))
        box.add_widget(logo)

        title = Label(text="AlgoBotPro", color=hex_color(C["text"]),
                      font_size=dp(28), bold=True,
                      size_hint_y=None, height=dp(40))
        box.add_widget(title)

        sub = Label(text="NSE Algo Trading Bot",
                    color=hex_color(C["muted"]), font_size=dp(13),
                    size_hint_y=None, height=dp(24))
        box.add_widget(sub)

        box.add_widget(Widget(size_hint_y=None, height=dp(20)))

        # Username
        self.user_inp = make_input(hint="Username", text="admin")
        box.add_widget(self.user_inp)

        # Password
        self.pass_inp = make_input(hint="Password", text="admin123", password=True)
        box.add_widget(self.pass_inp)

        # Status
        self.status_lbl = Label(text="", color=hex_color(C["red"]),
                                 font_size=dp(12), size_hint_y=None, height=dp(24))
        box.add_widget(self.status_lbl)

        # Login button
        btn = make_btn("🔐 Login", bg=C["accent"], height=dp(52))
        btn.bind(on_press=self._do_login)
        box.add_widget(btn)

        # Demo hint
        hint = Label(text="Default: admin / admin123",
                     color=hex_color(C["muted"]), font_size=dp(11),
                     size_hint_y=None, height=dp(20))
        box.add_widget(hint)

        root.add_widget(box)
        self.add_widget(root)

    def _do_login(self, *a):
        users = load_users()
        uname = self.user_inp.text.strip()
        passw = self.pass_inp.text.strip()
        if uname in users and users[uname]["password"] == hash_pw(passw):
            app = App.get_running_app()
            app.username = uname
            app.user_name = users[uname].get("name", uname)
            app.cfg = load_cfg()
            self.manager.transition = SlideTransition(direction='left')
            self.manager.current = 'main'
        else:
            self.status_lbl.text = "❌ Invalid username or password"

# ── MAIN SCREEN ───────────────────────────────────────────────────────────────
class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*hex_color(C["bg"]))
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self.engine = None
        self.log_lines = []
        self._current_tab = "dashboard"
        self._built = False

    def _upd(self, *a):
        self._bg.pos=self.pos; self._bg.size=self.size

    def on_enter(self):
        if not self._built:
            self._build()
            self._built = True
            self._init_engine()
        Clock.schedule_interval(self._refresh_ui, 2.0)

    def on_leave(self):
        Clock.unschedule(self._refresh_ui)

    def _init_engine(self):
        app = App.get_running_app()
        self.engine = PaperEngine(app.cfg, log_cb=self._on_log)
        self.engine._price_cbs.append(self._on_prices)

    def _on_log(self, msg, level="info"):
        now = now_ist().strftime("%H:%M:%S")
        color_map = {"ok":"✅","error":"❌","warn":"⚠️","info":"ℹ️"}
        icon = color_map.get(level, "•")
        line = f"[{now}] {icon} {msg}"
        self.log_lines.append(line)
        if len(self.log_lines) > 200:
            self.log_lines = self.log_lines[-200:]

    def _on_prices(self, prices):
        pass  # Refresh handled by clock

    def _build(self):
        root = BoxLayout(orientation='vertical')

        # Top bar
        self.topbar = TopBar("AlgoBotPro", on_menu=self._toggle_drawer)
        root.add_widget(self.topbar)

        # Content area
        self.content = BoxLayout(orientation='horizontal')

        # Side drawer (hidden by default on mobile)
        self._drawer_open = False
        self._drawer = self._make_drawer()

        # Main content
        self.page_area = BoxLayout(orientation='vertical')
        self.content.add_widget(self.page_area)
        root.add_widget(self.content)

        # Bottom nav bar
        nav = self._make_nav()
        root.add_widget(nav)

        self.add_widget(root)
        self._show_dashboard()

    def _make_drawer(self):
        drawer = BoxLayout(orientation='vertical', size_hint=(None,1),
                           width=0, padding=0, spacing=0)
        with drawer.canvas.before:
            Color(*hex_color(C["sidebar"]))
            self._drawer_rect = Rectangle(pos=drawer.pos, size=drawer.size)
        drawer.bind(pos=lambda *a: setattr(self._drawer_rect,'pos',drawer.pos),
                    size=lambda *a: setattr(self._drawer_rect,'size',drawer.size))

        nav_items = [
            ("🏠 Dashboard", "dashboard"),
            ("📊 Positions", "positions"),
            ("📋 Trades", "trades"),
            ("⚙️ Settings", "settings"),
            ("🤖 Strategies", "strategies"),
            ("📰 News", "news"),
            ("📈 Performance", "performance"),
        ]
        for label, page in nav_items:
            btn = Button(text=label, size_hint_y=None, height=dp(48),
                         background_color=(0,0,0,0),
                         color=hex_color(C["text"]), font_size=dp(14),
                         halign='left')
            btn._page = page
            btn.bind(on_press=self._on_nav)
            drawer.add_widget(btn)
        drawer.add_widget(Widget())
        return drawer

    def _toggle_drawer(self, *a):
        if self._drawer_open:
            self.content.remove_widget(self._drawer)
        else:
            self.content.add_widget(self._drawer, index=len(self.content.children))
            self._drawer.width = dp(220)
        self._drawer_open = not self._drawer_open

    def _on_nav(self, btn):
        page = btn._page
        if self._drawer_open:
            self._toggle_drawer()
        self._navigate(page)

    def _make_nav(self):
        nav = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(56),
                        spacing=2, padding=[dp(4),dp(4)])
        with nav.canvas.before:
            Color(*hex_color(C["sidebar"]))
            r = Rectangle(pos=nav.pos, size=nav.size)
        nav.bind(pos=lambda *a: setattr(r,'pos',nav.pos),
                 size=lambda *a: setattr(r,'size',nav.size))

        items = [
            ("🏠\nHome","dashboard"),("📊\nPositions","positions"),
            ("📋\nTrades","trades"),("⚙️\nSettings","settings"),
        ]
        for label, page in items:
            btn = Button(text=label, background_color=(0,0,0,0),
                         color=hex_color(C["muted"]), font_size=dp(10))
            btn._page = page
            btn.bind(on_press=lambda b,p=page: self._navigate(p))
            nav.add_widget(btn)
        return nav

    def _navigate(self, page):
        self._current_tab = page
        self.page_area.clear_widgets()
        nav_map = {
            "dashboard": self._show_dashboard,
            "positions": self._show_positions,
            "trades":    self._show_trades,
            "settings":  self._show_settings,
            "strategies":self._show_strategies,
            "news":      self._show_news,
            "performance":self._show_performance,
        }
        nav_map.get(page, self._show_dashboard)()

    # ─── DASHBOARD PAGE ───────────────────────────────────────────────────────
    def _show_dashboard(self):
        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', spacing=dp(12),
                          padding=[dp(12),dp(12)],
                          size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))

        app = App.get_running_app()
        cfg = app.cfg

        # Market status card
        status, scolor, sdesc = market_status(
            cfg.get("bot_start","09:15"), cfg.get("bot_stop","15:25"))
        self.topbar.set_status(status, scolor)

        status_card = CardWidget(orientation='vertical', padding=dp(14),
                                 spacing=dp(6), size_hint_y=None, height=dp(90))
        status_card.add_widget(Label(
            text=f"Market: {status}",
            color=hex_color(scolor), font_size=dp(16), bold=True,
            size_hint_y=None, height=dp(28), halign='left'))
        status_card.add_widget(Label(
            text=sdesc, color=hex_color(C["muted"]), font_size=dp(12),
            size_hint_y=None, height=dp(20), halign='left'))
        mode_txt = f"Mode: {'🟢 PAPER' if cfg.get('mode')=='paper' else '🔴 LIVE'}"
        status_card.add_widget(Label(
            text=mode_txt, color=hex_color(C["text"]), font_size=dp(12),
            size_hint_y=None, height=dp(20), halign='left'))
        inner.add_widget(status_card)

        # Stats cards row
        stats = self.engine.get_stats() if self.engine else {}
        stats_row = GridLayout(cols=2, spacing=dp(8),
                               size_hint_y=None, height=dp(180))
        stat_items = [
            ("💰 Daily P&L", f"₹{stats.get('daily_pnl',0):+,.2f}",
             C["green"] if stats.get('daily_pnl',0)>=0 else C["red"]),
            ("📈 Win Rate", f"{stats.get('win_rate',0):.1f}%", C["blue"]),
            ("🔄 Trades", str(stats.get('total_trades',0)), C["text"]),
            ("📂 Open Pos", str(stats.get('open_positions',0)), C["amber"]),
        ]
        for label, value, vcolor in stat_items:
            card = CardWidget(orientation='vertical', padding=dp(12), spacing=dp(4))
            card.add_widget(Label(text=label, color=hex_color(C["muted"]),
                                   font_size=dp(11), size_hint_y=None, height=dp(20),
                                   halign='left'))
            card.add_widget(Label(text=value, color=hex_color(vcolor),
                                   font_size=dp(18), bold=True,
                                   size_hint_y=None, height=dp(28),
                                   halign='left'))
            stats_row.add_widget(card)
        inner.add_widget(stats_row)

        # Prices card
        prices_card = CardWidget(orientation='vertical', padding=dp(14),
                                  spacing=dp(4), size_hint_y=None,
                                  height=dp(40 + 28*4))
        prices_card.add_widget(Label(
            text="📡 Live Prices", color=hex_color(C["accent"]),
            font_size=dp(13), bold=True, size_hint_y=None, height=dp(28),
            halign='left'))
        prices = stats.get('prices', self.engine.prices if self.engine else {})
        for sym, price in prices.items():
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(24))
            row.add_widget(Label(text=sym, color=hex_color(C["muted"]),
                                  font_size=dp(12), halign='left'))
            row.add_widget(Label(text=f"₹{price:,.2f}", color=hex_color(C["text"]),
                                  font_size=dp(12), bold=True, halign='right'))
            prices_card.add_widget(row)
        inner.add_widget(prices_card)
        self._prices_card = prices_card
        self._prices_dict = prices

        # Bot controls
        ctrl_card = CardWidget(orientation='vertical', padding=dp(14),
                                spacing=dp(10), size_hint_y=None, height=dp(140))
        ctrl_card.add_widget(Label(
            text="🎛️ Bot Controls", color=hex_color(C["accent"]),
            font_size=dp(13), bold=True, size_hint_y=None, height=dp(28),
            halign='left'))

        ctrl_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        self.start_btn = make_btn("▶ Start", bg=C["green"])
        self.stop_btn  = make_btn("⏹ Stop", bg=C["red"])
        self.start_btn.bind(on_press=self._start_bot)
        self.stop_btn.bind(on_press=self._stop_bot)
        ctrl_row.add_widget(self.start_btn)
        ctrl_row.add_widget(self.stop_btn)
        ctrl_card.add_widget(ctrl_row)

        self.bot_status_lbl = Label(
            text="● Bot Stopped", color=hex_color(C["muted"]),
            font_size=dp(12), size_hint_y=None, height=dp(24), halign='left')
        ctrl_card.add_widget(self.bot_status_lbl)
        inner.add_widget(ctrl_card)

        # Live log
        log_card = CardWidget(orientation='vertical', padding=dp(14),
                               spacing=dp(4), size_hint_y=None, height=dp(220))
        log_card.add_widget(Label(
            text="📋 Live Log", color=hex_color(C["accent"]),
            font_size=dp(13), bold=True, size_hint_y=None, height=dp(28),
            halign='left'))
        log_sv = ScrollView(size_hint=(1,1))
        self.log_box = BoxLayout(orientation='vertical', spacing=dp(2),
                                  size_hint_y=None)
        self.log_box.bind(minimum_height=self.log_box.setter('height'))
        log_sv.add_widget(self.log_box)
        log_card.add_widget(log_sv)
        inner.add_widget(log_card)
        self._update_log_display()

        sv.add_widget(inner)
        self.page_area.add_widget(sv)

    def _start_bot(self, *a):
        if self.engine and not self.engine.running:
            self.engine.start()
            if hasattr(self,'bot_status_lbl'):
                self.bot_status_lbl.text = "● Bot Running"
                self.bot_status_lbl.color = hex_color(C["green"])

    def _stop_bot(self, *a):
        if self.engine and self.engine.running:
            self.engine.stop()
            if hasattr(self,'bot_status_lbl'):
                self.bot_status_lbl.text = "● Bot Stopped"
                self.bot_status_lbl.color = hex_color(C["muted"])

    def _update_log_display(self):
        if not hasattr(self,'log_box'): return
        self.log_box.clear_widgets()
        lines = self.log_lines[-30:]
        for line in reversed(lines):
            col = C["green"] if "✅" in line else (
                  C["red"] if "❌" in line else (
                  C["amber"] if "⚠️" in line else C["muted"]))
            lbl = Label(text=line, color=hex_color(col), font_size=dp(11),
                        size_hint_y=None, height=dp(18),
                        halign='left', text_size=(Window.width-dp(60), None))
            self.log_box.add_widget(lbl)

    def _refresh_ui(self, dt):
        if self._current_tab == "dashboard":
            self._update_log_display()
            if self.engine and hasattr(self,'bot_status_lbl'):
                if self.engine.running:
                    self.bot_status_lbl.text = "● Bot Running"
                    self.bot_status_lbl.color = hex_color(C["green"])

    # ─── POSITIONS PAGE ───────────────────────────────────────────────────────
    def _show_positions(self):
        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', spacing=dp(8),
                          padding=dp(12), size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))

        make_section("📊 Open Positions", inner)
        positions = self.engine.positions if self.engine else {}
        if not positions:
            card = CardWidget(padding=dp(20), size_hint_y=None, height=dp(80))
            card.add_widget(Label(text="No open positions",
                                   color=hex_color(C["muted"]), font_size=dp(14)))
            inner.add_widget(card)
        else:
            for sym, pos in positions.items():
                card = CardWidget(orientation='vertical', padding=dp(14),
                                   spacing=dp(4), size_hint_y=None, height=dp(100))
                card.add_widget(Label(text=f"📈 {sym}",
                                       color=hex_color(C["text"]), font_size=dp(14),
                                       bold=True, size_hint_y=None, height=dp(24),
                                       halign='left'))
                card.add_widget(Label(
                    text=f"Strategy: {pos['strategy']} | Entry: ₹{pos['entry']:.0f}",
                    color=hex_color(C["muted"]), font_size=dp(12),
                    size_hint_y=None, height=dp(20), halign='left'))
                card.add_widget(Label(
                    text=f"Qty: {pos['qty']} | Conf: {pos['confidence']}%",
                    color=hex_color(C["accent"]), font_size=dp(12),
                    size_hint_y=None, height=dp(20), halign='left'))

                exit_btn = make_btn(f"Exit {sym}", bg=C["red"],
                                    height=dp(36), font_size=dp(12))
                exit_btn._sym = sym
                exit_btn.bind(on_press=lambda b: self._manual_exit(b._sym))
                card.add_widget(exit_btn)
                inner.add_widget(card)

        sv.add_widget(inner)
        self.page_area.add_widget(sv)

    def _manual_exit(self, sym):
        if self.engine and sym in self.engine.positions:
            import random
            exit_price = self.engine.positions[sym]["entry"] * random.uniform(0.97, 1.05)
            self.engine._exit_trade(sym, exit_price)
            self._navigate("positions")

    # ─── TRADES PAGE ─────────────────────────────────────────────────────────
    def _show_trades(self):
        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', spacing=dp(8),
                          padding=dp(12), size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))

        make_section("📋 Trade History (Last 50)", inner)
        trades = load_trades()
        if not trades:
            card = CardWidget(padding=dp(20), size_hint_y=None, height=dp(80))
            card.add_widget(Label(text="No trades yet",
                                   color=hex_color(C["muted"]), font_size=dp(14)))
            inner.add_widget(card)
        else:
            for t in trades[:50]:
                pnl = float(t.get("net_pnl",0) or 0)
                pnl_col = C["green"] if pnl >= 0 else C["red"]
                card = CardWidget(orientation='vertical', padding=dp(12),
                                   spacing=dp(2), size_hint_y=None, height=dp(80))
                row1 = BoxLayout(size_hint_y=None, height=dp(22))
                row1.add_widget(Label(text=t.get("symbol","?"),
                                       color=hex_color(C["text"]),
                                       font_size=dp(13), bold=True, halign='left'))
                row1.add_widget(Label(text=f"₹{pnl:+.2f}",
                                       color=hex_color(pnl_col),
                                       font_size=dp(13), bold=True, halign='right'))
                card.add_widget(row1)
                row2 = BoxLayout(size_hint_y=None, height=dp(18))
                row2.add_widget(Label(
                    text=f"{t.get('strategy','?')} | {t.get('date','?')} {t.get('time','?')}",
                    color=hex_color(C["muted"]), font_size=dp(11), halign='left'))
                card.add_widget(row2)
                inner.add_widget(card)

        sv.add_widget(inner)
        self.page_area.add_widget(sv)

    # ─── SETTINGS PAGE ───────────────────────────────────────────────────────
    def _show_settings(self):
        app = App.get_running_app()
        cfg = app.cfg

        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', spacing=dp(10),
                          padding=dp(12), size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))

        # ── Trading Mode ──
        make_section("⚙️ Trading Mode", inner)
        mode_card = CardWidget(orientation='vertical', padding=dp(14),
                                spacing=dp(8), size_hint_y=None, height=dp(100))
        mode_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        self._mode_spinner = Spinner(
            text=cfg.get("mode","paper").upper(),
            values=["PAPER","LIVE"],
            size_hint=(None,1), width=dp(120),
            background_color=hex_color(C["accent"]),
            color=hex_color(C["white"]))
        mode_row.add_widget(Label(text="Mode:", color=hex_color(C["text"]),
                                   font_size=dp(13)))
        mode_row.add_widget(self._mode_spinner)
        mode_card.add_widget(mode_row)
        inner.add_widget(mode_card)

        # ── Capital & Risk ──
        make_section("💰 Capital & Risk", inner)
        risk_card = CardWidget(orientation='vertical', padding=dp(14),
                                spacing=dp(8), size_hint_y=None, height=dp(220))

        self._capital_inp = make_input("Capital (₹)", cfg.get("capital",100000))
        self._risk_inp    = make_input("Risk % per trade", cfg.get("risk_pct",1.5))
        self._maxpos_inp  = make_input("Max Positions", cfg.get("max_positions",5))
        self._loss_inp    = make_input("Daily Loss Limit %", cfg.get("daily_loss_limit_pct",3.0))

        for inp in [self._capital_inp, self._risk_inp, self._maxpos_inp, self._loss_inp]:
            risk_card.add_widget(inp)
        inner.add_widget(risk_card)

        # ── Broker Settings ──
        make_section("🔗 Broker (Zerodha)", inner)
        broker_card = CardWidget(orientation='vertical', padding=dp(14),
                                  spacing=dp(8), size_hint_y=None, height=dp(200))
        self._apikey_inp  = make_input("API Key", cfg.get("api_key",""))
        self._apisec_inp  = make_input("API Secret", cfg.get("api_secret",""), password=True)
        self._token_inp   = make_input("Access Token", cfg.get("access_token",""), password=True)
        for inp in [self._apikey_inp, self._apisec_inp, self._token_inp]:
            broker_card.add_widget(inp)
        inner.add_widget(broker_card)

        # ── Telegram ──
        make_section("📱 Telegram Alerts", inner)
        tg_card = CardWidget(orientation='vertical', padding=dp(14),
                              spacing=dp(8), size_hint_y=None, height=dp(150))
        self._tg_token_inp = make_input("Bot Token", cfg.get("tg_token",""))
        self._tg_chat_inp  = make_input("Chat ID", cfg.get("tg_chat",""))
        for inp in [self._tg_token_inp, self._tg_chat_inp]:
            tg_card.add_widget(inp)
        inner.add_widget(tg_card)

        # ── Bot Timing ──
        make_section("⏰ Bot Timing", inner)
        time_card = CardWidget(orientation='vertical', padding=dp(14),
                                spacing=dp(8), size_hint_y=None, height=dp(130))
        self._start_inp = make_input("Start Time (HH:MM)", cfg.get("bot_start","09:15"))
        self._stop_inp  = make_input("Stop Time (HH:MM)", cfg.get("bot_stop","15:25"))
        for inp in [self._start_inp, self._stop_inp]:
            time_card.add_widget(inp)
        inner.add_widget(time_card)

        # Save button
        save_btn = make_btn("💾 Save All Settings", bg=C["green"], height=dp(52))
        save_btn.bind(on_press=self._save_settings)
        inner.add_widget(save_btn)

        # Logout button
        logout_btn = make_btn("🚪 Logout", bg=C["red"], height=dp(46))
        logout_btn.bind(on_press=self._logout)
        inner.add_widget(logout_btn)

        inner.add_widget(Widget(size_hint_y=None, height=dp(20)))
        sv.add_widget(inner)
        self.page_area.add_widget(sv)

    def _save_settings(self, *a):
        app = App.get_running_app()
        try:
            app.cfg["mode"] = self._mode_spinner.text.lower()
            app.cfg["capital"] = float(self._capital_inp.text or 100000)
            app.cfg["risk_pct"] = float(self._risk_inp.text or 1.5)
            app.cfg["max_positions"] = int(self._maxpos_inp.text or 5)
            app.cfg["daily_loss_limit_pct"] = float(self._loss_inp.text or 3.0)
            app.cfg["api_key"] = self._apikey_inp.text.strip()
            app.cfg["api_secret"] = self._apisec_inp.text.strip()
            app.cfg["access_token"] = self._token_inp.text.strip()
            app.cfg["tg_token"] = self._tg_token_inp.text.strip()
            app.cfg["tg_chat"] = self._tg_chat_inp.text.strip()
            app.cfg["bot_start"] = self._start_inp.text.strip()
            app.cfg["bot_stop"] = self._stop_inp.text.strip()
            save_cfg(app.cfg)
            if self.engine: self.engine.cfg = app.cfg
            self._show_popup("✅ Saved!", "Settings saved successfully!")
        except Exception as e:
            self._show_popup("❌ Error", str(e))

    def _logout(self, *a):
        if self.engine and self.engine.running:
            self.engine.stop()
        Clock.unschedule(self._refresh_ui)
        self._built = False
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'login'

    # ─── STRATEGIES PAGE ─────────────────────────────────────────────────────
    def _show_strategies(self):
        app = App.get_running_app()
        cfg = app.cfg
        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', spacing=dp(10),
                          padding=dp(12), size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))

        make_section("🤖 Active Strategies", inner)
        strategies = [
            ("strat_momentum_on",       "📈 Momentum Strategy"),
            ("strat_reversal_on",       "🔄 Reversal Strategy"),
            ("strat_supertrend_on",     "📉 Supertrend Strategy"),
            ("strat_bollinger_on",      "📊 Bollinger Bands"),
            ("strat_short_strangle_on", "🔀 Short Strangle"),
            ("strat_iron_condor_on",    "🦅 Iron Condor"),
        ]
        self._strat_switches = {}
        for key, label in strategies:
            card = CardWidget(orientation='horizontal', padding=dp(14),
                               size_hint_y=None, height=dp(52))
            card.add_widget(Label(text=label, color=hex_color(C["text"]),
                                   font_size=dp(13), halign='left'))
            sw = Switch(active=bool(cfg.get(key, False)),
                         size_hint=(None,1), width=dp(60))
            self._strat_switches[key] = sw
            card.add_widget(sw)
            inner.add_widget(card)

        make_section("📡 Symbols to Scan", inner)
        syms = [
            ("scan_nifty","NIFTY 50"),
            ("scan_banknifty","BANK NIFTY"),
            ("scan_finnifty","FIN NIFTY"),
            ("scan_midcpnifty","MIDCAP NIFTY"),
        ]
        self._sym_switches = {}
        for key, label in syms:
            card = CardWidget(orientation='horizontal', padding=dp(14),
                               size_hint_y=None, height=dp(52))
            card.add_widget(Label(text=label, color=hex_color(C["text"]),
                                   font_size=dp(13), halign='left'))
            sw = Switch(active=bool(cfg.get(key, False)),
                         size_hint=(None,1), width=dp(60))
            self._sym_switches[key] = sw
            card.add_widget(sw)
            inner.add_widget(card)

        make_section("🎯 Signal Settings", inner)
        sig_card = CardWidget(orientation='vertical', padding=dp(14),
                               spacing=dp(8), size_hint_y=None, height=dp(130))
        self._conf_inp = make_input("Confidence Gate %", cfg.get("confidence_gate",55))
        self._int_inp  = make_input("Signal Interval (sec)", cfg.get("signal_interval_s",3))
        sig_card.add_widget(self._conf_inp)
        sig_card.add_widget(self._int_inp)
        inner.add_widget(sig_card)

        save_btn = make_btn("💾 Save Strategies", bg=C["accent"], height=dp(52))
        save_btn.bind(on_press=self._save_strategies)
        inner.add_widget(save_btn)
        inner.add_widget(Widget(size_hint_y=None, height=dp(20)))
        sv.add_widget(inner)
        self.page_area.add_widget(sv)

    def _save_strategies(self, *a):
        app = App.get_running_app()
        for key, sw in self._strat_switches.items():
            app.cfg[key] = sw.active
        for key, sw in self._sym_switches.items():
            app.cfg[key] = sw.active
        try:
            app.cfg["confidence_gate"] = int(self._conf_inp.text or 55)
            app.cfg["signal_interval_s"] = int(self._int_inp.text or 3)
        except: pass
        save_cfg(app.cfg)
        if self.engine: self.engine.cfg = app.cfg
        self._show_popup("✅ Saved!", "Strategy settings saved!")

    # ─── NEWS PAGE ───────────────────────────────────────────────────────────
    def _show_news(self):
        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', spacing=dp(10),
                          padding=dp(12), size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))
        make_section("📰 Market News (NSE/ET)", inner)

        card = CardWidget(padding=dp(16), size_hint_y=None, height=dp(80))
        card.add_widget(Label(
            text="News feed requires internet connection.\nTap Refresh to load.",
            color=hex_color(C["muted"]), font_size=dp(13),
            halign='center'))
        inner.add_widget(card)

        ref_btn = make_btn("🔄 Refresh News", bg=C["blue"], height=dp(46))
        ref_btn.bind(on_press=self._load_news)
        inner.add_widget(ref_btn)

        self._news_inner = inner
        sv.add_widget(inner)
        self.page_area.add_widget(sv)

    def _load_news(self, *a):
        self._on_log("📰 Loading news...", "info")

    # ─── PERFORMANCE PAGE ────────────────────────────────────────────────────
    def _show_performance(self):
        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', spacing=dp(10),
                          padding=dp(12), size_hint_y=None)
        inner.bind(minimum_height=inner.setter('height'))
        make_section("📈 Performance Stats", inner)

        stats = self.engine.get_stats() if self.engine else {}
        trades = load_trades()

        # Session stats
        sess_card = CardWidget(orientation='vertical', padding=dp(14),
                                spacing=dp(6), size_hint_y=None, height=dp(180))
        sess_card.add_widget(Label(text="This Session",
                                    color=hex_color(C["accent"]), font_size=dp(14),
                                    bold=True, size_hint_y=None, height=dp(28),
                                    halign='left'))
        items = [
            ("Daily P&L", f"₹{stats.get('daily_pnl',0):+,.2f}",
             C["green"] if stats.get('daily_pnl',0)>=0 else C["red"]),
            ("Total Trades", str(stats.get('total_trades',0)), C["text"]),
            ("Win Rate", f"{stats.get('win_rate',0):.1f}%", C["blue"]),
            ("Wins/Losses", f"{stats.get('wins',0)} / {stats.get('losses',0)}", C["text"]),
        ]
        for label, value, col in items:
            row = BoxLayout(size_hint_y=None, height=dp(26))
            row.add_widget(Label(text=label, color=hex_color(C["muted"]),
                                  font_size=dp(12), halign='left'))
            row.add_widget(Label(text=value, color=hex_color(col),
                                  font_size=dp(12), bold=True, halign='right'))
            sess_card.add_widget(row)
        inner.add_widget(sess_card)

        # All time stats
        if trades:
            total_pnl = sum(float(t.get("net_pnl",0) or 0) for t in trades)
            wins = sum(1 for t in trades if float(t.get("net_pnl",0) or 0) >= 0)
            hist_card = CardWidget(orientation='vertical', padding=dp(14),
                                    spacing=dp(6), size_hint_y=None, height=dp(140))
            hist_card.add_widget(Label(text="All Time",
                                        color=hex_color(C["accent"]), font_size=dp(14),
                                        bold=True, size_hint_y=None, height=dp(28),
                                        halign='left'))
            for label, value, col in [
                ("Total P&L", f"₹{total_pnl:+,.2f}",
                 C["green"] if total_pnl>=0 else C["red"]),
                ("Total Trades", str(len(trades)), C["text"]),
                ("Win Rate", f"{wins/len(trades)*100:.1f}%", C["blue"]),
            ]:
                row = BoxLayout(size_hint_y=None, height=dp(26))
                row.add_widget(Label(text=label, color=hex_color(C["muted"]),
                                      font_size=dp(12), halign='left'))
                row.add_widget(Label(text=value, color=hex_color(col),
                                      font_size=dp(12), bold=True, halign='right'))
                hist_card.add_widget(row)
            inner.add_widget(hist_card)

        inner.add_widget(Widget(size_hint_y=None, height=dp(20)))
        sv.add_widget(inner)
        self.page_area.add_widget(sv)

    def _show_popup(self, title, msg):
        content = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text=msg, color=hex_color(C["text"]),
                                  font_size=dp(13)))
        btn = make_btn("OK", bg=C["accent"])
        popup = Popup(title=title, content=content,
                      size_hint=(0.8, None), height=dp(180),
                      background_color=hex_color(C["card"]),
                      title_color=hex_color(C["text"]))
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()


# ═══════════════════════════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════════════════════════
class AlgoBotProApp(App):
    title = "AlgoBotPro"
    username = StringProperty("")
    user_name = StringProperty("")

    def build(self):
        Window.clearcolor = hex_color(C["bg"])
        init_db()
        self.cfg = load_cfg()

        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(MainScreen(name='main'))
        return sm

    def on_stop(self):
        # Stop engine safely on exit
        for screen in self.root.screens:
            if isinstance(screen, MainScreen) and screen.engine:
                screen.engine.stop()


if __name__ == "__main__":
    AlgoBotProApp().run()
