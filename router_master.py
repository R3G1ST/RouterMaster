import json
import os
import re
import sys
import ctypes
import shutil
import threading
import time
import tempfile
import subprocess
import urllib.request
import urllib.error
import http.cookiejar
import webbrowser
import tkinter as tk
import customtkinter as ctk
import paramiko

APP_VERSION = "1.5.0-beta1"
UPDATE_REPO = "R3G1ST/RouterMaster"
UPDATE_ASSET = "RouterMaster-Setup.exe"

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(os.environ.get("APPDATA", APP_DIR), "RouterMaster")
CONFIG_FILE = os.path.join(DATA_DIR, "router_tool_config.json")
DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")

THEMES = {
    "Argon": {
        "pkg": "luci-theme-argon",
        "url": "https://github.com/jerrykuku/luci-theme-argon/releases/download/v2.4.6/luci-theme-argon-2.4.6-r1.apk",
        "media": "/luci-static/argon",
    },
    "Proton2025": {
        "pkg": "luci-theme-proton2025",
        "url": "https://github.com/ChesterGoodiny/luci-theme-proton2025/releases/download/v1.3.0/luci-theme-proton2025-1.3.0-r1.apk",
        "media": "/luci-static/proton2025",
    },
    "Bootstrap": {"pkg": "luci-theme-bootstrap", "media": "/luci-static/bootstrap"},
    "Bootstrap Dark": {"pkg": "luci-theme-bootstrap", "media": "/luci-static/bootstrap-dark"},
    "Bootstrap Light": {"pkg": "luci-theme-bootstrap", "media": "/luci-static/bootstrap-light"},
}

PODKOP_COMMUNITY_LISTS = (
    "russia_inside russia_outside ukraine_inside geoblock block porn news anime youtube "
    "hdrezka tiktok google_ai google_play hodca discord meta twitter cloudflare cloudfront "
    "digitalocean hetzner ovh telegram roblox"
)

ENC_LABELS = {
    "WPA3 (SAE)": "sae",
    "WPA3 + WPA2 (переходный)": "sae-mixed",
    "WPA2 (PSK)": "psk2",
    "WPA (устаревший)": "psk",
    "Открытая сеть": "none",
}

DEFAULTS = {
    "host": "192.168.1.1",
    "port": 22,
    "user": "root",
    "password": "",
    "theme": "Argon",
    "wifi_ssid": "OpenWrt 5G",
    "wifi_ssid_2g": "OpenWrt 2G",
    "wifi_password": "",
    "wifi_channel": "36",
    "wifi_channel_2g": "auto",
    "wifi_enc_5g": "WPA3 (SAE)",
    "wifi_enc_2g": "WPA2 (PSK)",
    "proxy_string": "",
    "gui_theme": "light",
    "steps": {
        "update_packages": True,
        "install_podkop": True,
        "install_zapret": False,
        "install_argon": True,
        "install_ru": True,
        "setup_wifi": True,
        "setup_wifi_2g": True,
        "setup_proxy": False,
        "update_os": False,
    },
}


PAL = {
    "dark": {
        "bg": "#05070d", "panel": "#0a0f1c", "card": "#101828",
        "border": "#1c2740", "field": "#0d1526", "text": "#e8ecf4",
        "muted": "#97a3b8", "accent": "#6366f1", "accent_hover": "#818cf8",
        "accent2": "#22d3ee", "ok": "#34d399", "err": "#f87171",
    },
    "light": {
        "bg": "#f2f5fb", "panel": "#e6ebf6", "card": "#ffffff",
        "border": "#d4dcec", "field": "#ffffff", "text": "#0f172a",
        "muted": "#64748b", "accent": "#4f46e5", "accent_hover": "#6366f1",
        "accent2": "#0e7490", "ok": "#059669", "err": "#dc2626",
    },
}


class RouterToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RouterMaster — OpenWrt")
        self.root.geometry("1040x720")
        self.root.minsize(920, 640)
        self.config = self.load_config()

        self.is_dark = self.config.get("gui_theme", DEFAULTS["gui_theme"]) == "dark"
        self.var_gui_dark = tk.BooleanVar(value=self.is_dark)
        self.P = PAL["dark" if self.is_dark else "light"]
        ctk.set_appearance_mode("dark" if self.is_dark else "light")
        self.apply_theme(self.is_dark)
        self.set_app_icon(root)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()

    # ---------- Построение интерфейса ----------
    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=self.P["card"],
                            border_width=1, border_color=self.P["border"],
                            corner_radius=14)
        if title:
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=16, pady=(12, 0))
            ctk.CTkLabel(head, text=title, font=ctk.CTkFont("Segoe UI", 13, "bold"),
                         text_color=self.P["text"]).pack(side="left")
            ctk.CTkLabel(head, text="\u25cf", text_color=self.P["accent2"],
                         font=ctk.CTkFont("Segoe UI", 9)).pack(side="left", padx=(8, 0))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(8, 14))
        card._body = body
        return card

    def _lbl(self, parent, text, **kw):
        kw.setdefault("text_color", self.P["muted"])
        kw.setdefault("font", ctk.CTkFont("Segoe UI", 11))
        return ctk.CTkLabel(parent, text=text, **kw)

    def _entry(self, parent, variable, width=180, show=None):
        return ctk.CTkEntry(parent, textvariable=variable, width=width,
                            fg_color=self.P["field"], border_color=self.P["border"],
                            text_color=self.P["text"], placeholder_text_color=self.P["muted"],
                            show=show, corner_radius=8, border_width=1)

    def _option(self, parent, variable, values, width=200):
        return ctk.CTkOptionMenu(parent, variable=variable, values=values, width=width,
                                 fg_color=self.P["field"], button_color=self.P["accent"],
                                 button_hover_color=self.P["accent_hover"],
                                 text_color=self.P["text"], corner_radius=8)

    def _switch(self, parent, text, variable, command=None):
        return ctk.CTkSwitch(parent, text=text, variable=variable, command=command,
                             fg_color=self.P["border"], progress_color=self.P["accent"],
                             text_color=self.P["text"],
                             font=ctk.CTkFont("Segoe UI", 12))

    def _nav_btn(self, parent, text, page):
        btn = ctk.CTkButton(parent, text=text, anchor="w", corner_radius=10,
                            fg_color="transparent", hover_color=self.P["card"],
                            text_color=self.P["text"], height=36,
                            font=ctk.CTkFont("Segoe UI", 12),
                            command=lambda: self._show_page(page))
        btn.pack(fill="x", padx=10, pady=2)
        return btn

    def _build_ui(self):
        root = self.root
        root.configure(fg_color=self.P["bg"])

        outer = ctk.CTkFrame(root, fg_color=self.P["bg"])
        outer.pack(fill="both", expand=True)

        # ===== Сайдбар =====
        side = ctk.CTkFrame(outer, width=210, fg_color=self.P["panel"], corner_radius=0)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", padx=14, pady=(18, 14))
        ctk.CTkLabel(brand, text="RouterMaster", font=ctk.CTkFont("Segoe UI", 17, "bold"),
                     text_color=self.P["text"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="умный помощник OpenWrt", font=ctk.CTkFont("Segoe UI", 10),
                     text_color=self.P["muted"]).pack(anchor="w")

        self._nav_btn(side, "\u2302 Главная", "home")
        self._nav_btn(side, "\u2039 Подключение", "conn")
        self._nav_btn(side, "\u2699 Что выполнить", "steps")
        self._nav_btn(side, "\u2726 Параметры", "params")

        side_foot = ctk.CTkFrame(side, fg_color="transparent")
        side_foot.pack(side="bottom", fill="x", padx=14, pady=14)
        ctk.CTkButton(side_foot, text="Проверить обновление", height=32,
                      fg_color=self.P["card"], hover_color=self.P["border"],
                      text_color=self.P["text"], corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=self.check_update).pack(fill="x")
        ctk.CTkLabel(side_foot, text="RouterMaster v%s\nАвтор: R3G1ST" % APP_VERSION,
                     font=ctk.CTkFont("Segoe UI", 10), text_color=self.P["muted"],
                     justify="center").pack(pady=(10, 0))

        # ===== Контент =====
        content = ctk.CTkFrame(outer, fg_color=self.P["bg"], corner_radius=0)
        content.pack(side="left", fill="both", expand=True, padx=(0, 0))

        self.pages_area = ctk.CTkFrame(content, fg_color="transparent")
        self.pages_area.pack(side="top", fill="both", expand=True)

        self.pages = {}

        # ----- Страница: Главная -----
        page = ctk.CTkFrame(content, fg_color="transparent")

        hero = ctk.CTkFrame(page, fg_color="transparent")
        hero.pack(fill="both", expand=True, padx=28, pady=24)
        ctk.CTkLabel(hero, text="RouterMaster", font=ctk.CTkFont("Segoe UI", 34, "bold"),
                     text_color=self.P["text"]).pack(anchor="w")
        ctk.CTkLabel(hero, text="Умный помощник по настройке роутеров на OpenWrt",
                     font=ctk.CTkFont("Segoe UI", 13), text_color=self.P["muted"]).pack(anchor="w", pady=(2, 16))

        self.btn_run = ctk.CTkButton(hero, text="ВЫПОЛНИТЬ", height=56,
                                     fg_color=self.P["accent"], hover_color=self.P["accent_hover"],
                                     text_color="#ffffff", corner_radius=14,
                                     font=ctk.CTkFont("Segoe UI", 16, "bold"),
                                     command=self.run_all)
        self.btn_run.pack(anchor="w", fill="x", pady=(4, 10))

        self.btn_reset = ctk.CTkButton(hero, text="Сброс + настройка", height=44,
                                       fg_color=self.P["card"], hover_color=self.P["border"],
                                       border_width=1, border_color=self.P["border"],
                                       text_color=self.P["text"], corner_radius=12,
                                       font=ctk.CTkFont("Segoe UI", 13),
                                       command=self.reset_and_setup)
        self.btn_reset.pack(anchor="w", fill="x")

        hero_actions = ctk.CTkFrame(hero, fg_color="transparent")
        hero_actions.pack(anchor="w", pady=(14, 0))
        ctk.CTkButton(hero_actions, text="Сохранить настройки", height=32,
                      fg_color="transparent", hover_color=self.P["card"],
                      text_color=self.P["muted"], corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=self.save_config).pack(side="left", padx=(0, 8))
        ctk.CTkButton(hero_actions, text="Открыть лог", height=32,
                      fg_color="transparent", hover_color=self.P["card"],
                      text_color=self.P["muted"], corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=self._show_log).pack(side="left", padx=8)

        info = ctk.CTkFrame(page, fg_color=self.P["card"], border_width=1,
                            border_color=self.P["border"], corner_radius=14)
        info.pack(fill="x", padx=28, pady=(0, 24))
        ctk.CTkLabel(info,
                     text="1. Введите данные роутера на вкладке «Подключение»\n"
                          "2. Выберите шаги на вкладке «Что выполнить»\n"
                          "3. Настройте Wi-Fi и прокси на вкладке «Параметры»\n"
                          "4. Нажмите «ВЫПОЛНИТЬ» — результат будет виден в окне лога",
                     justify="left", text_color=self.P["text"],
                     font=ctk.CTkFont("Segoe UI", 12)).pack(anchor="w", padx=18, pady=16)

        self.pages["home"] = page

        # ----- Страница: Подключение -----
        page = ctk.CTkFrame(content, fg_color="transparent")
        card = self._card(page, "Подключение к роутеру")
        card.pack(fill="x", padx=14, pady=(14, 10))

        self.var_host = tk.StringVar(value=self.config.get("host", DEFAULTS["host"]))
        self.var_port = tk.StringVar(value=self.config.get("port", DEFAULTS["port"]))
        self.var_user = tk.StringVar(value=self.config.get("user", DEFAULTS["user"]))
        self.var_pass = tk.StringVar(value=self.config.get("password", DEFAULTS["password"]))

        b = card._body
        grid = ctk.CTkFrame(b, fg_color="transparent")
        grid.pack(fill="x")
        self._lbl(grid, "IP роутера").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        self._entry(grid, self.var_host, 170).grid(row=0, column=1, sticky="w", pady=6)
        self._lbl(grid, "Порт").grid(row=0, column=2, sticky="w", padx=(18, 8), pady=6)
        self._entry(grid, self.var_port, 70).grid(row=0, column=3, sticky="w", pady=6)
        self._lbl(grid, "Логин").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        self._entry(grid, self.var_user, 170).grid(row=1, column=1, sticky="w", pady=6)
        self._lbl(grid, "Пароль").grid(row=1, column=2, sticky="w", padx=(18, 8), pady=6)
        self.e_pass = self._entry(grid, self.var_pass, 170, show="*")
        self.e_pass.grid(row=1, column=3, sticky="w", pady=6)
        self.btn_show_pass = ctk.CTkButton(grid, text="Показать", width=90, height=32,
                                           fg_color=self.P["card"], hover_color=self.P["border"],
                                           border_width=1, border_color=self.P["border"],
                                           text_color=self.P["text"], corner_radius=8,
                                           command=self.toggle_show_password)
        self.btn_show_pass.grid(row=1, column=4, sticky="w", padx=(10, 0), pady=6)

        theme_row = ctk.CTkFrame(b, fg_color="transparent")
        theme_row.pack(fill="x", pady=(10, 2))
        self.switch_theme = self._switch(theme_row, "Тёмная тема", self.var_gui_dark,
                                         command=self.toggle_gui_theme)
        self.switch_theme.pack(side="left")

        self.pages["conn"] = page

        # ----- Страница: Что выполнить -----
        page = ctk.CTkFrame(content, fg_color="transparent")
        card = self._card(page, "Что выполнить (можно выбрать несколько)")
        card.pack(fill="x", padx=14, pady=(14, 10))
        b = card._body

        self.var_update = tk.BooleanVar(value=self.config["steps"].get("update_packages", True))
        self.var_podkop = tk.BooleanVar(value=self.config["steps"].get("install_podkop", True))
        self.var_zapret = tk.BooleanVar(value=self.config["steps"].get("install_zapret", False))
        self.var_argon = tk.BooleanVar(value=self.config["steps"].get("install_argon", True))
        self.var_ru = tk.BooleanVar(value=self.config["steps"].get("install_ru", True))
        self.var_wifi = tk.BooleanVar(value=self.config["steps"].get("setup_wifi", True))
        self.var_wifi_2g = tk.BooleanVar(value=self.config["steps"].get("setup_wifi_2g", True))
        self.var_enc_5g = tk.StringVar(value=self.config.get("wifi_enc_5g", DEFAULTS["wifi_enc_5g"]))
        self.var_enc_2g = tk.StringVar(value=self.config.get("wifi_enc_2g", DEFAULTS["wifi_enc_2g"]))
        self.var_proxy = tk.BooleanVar(value=self.config["steps"].get("setup_proxy", False))
        self.var_os = tk.BooleanVar(value=self.config["steps"].get("update_os", False))

        def row_switch(text, var):
            r = ctk.CTkFrame(b, fg_color="transparent")
            r.pack(fill="x", pady=3)
            self._switch(r, text, var).pack(side="left")
            return r

        def small_btn(parent, text, cmd, side="left"):
            return ctk.CTkButton(parent, text=text, width=80, height=28,
                                 fg_color=self.P["card"], hover_color=self.P["border"],
                                 border_width=1, border_color=self.P["border"],
                                 text_color=self.P["muted"], corner_radius=8,
                                 font=ctk.CTkFont("Segoe UI", 10), command=cmd).pack(
                                     side=side, padx=(10, 0))

        row_switch("Обновить все пакеты", self.var_update)
        r = row_switch("Установить / обновить Podkop", self.var_podkop)
        small_btn(r, "Удалить", self.remove_podkop)
        r = row_switch("Установить / обновить Zapret", self.var_zapret)
        small_btn(r, "Удалить", self.remove_zapret)

        r = row_switch("Установить тему:", self.var_argon)
        self.var_theme = tk.StringVar(value=self.config.get("theme", DEFAULTS["theme"]))
        self._option(r, self.var_theme, list(THEMES.keys()), 210).pack(side="left", padx=(10, 0))

        row_switch("Русский язык интерфейса", self.var_ru)

        r = row_switch("Создать Wi-Fi 5G:", self.var_wifi)
        self._option(r, self.var_enc_5g, list(ENC_LABELS.keys()), 210).pack(side="left", padx=(10, 0))
        r = row_switch("Создать Wi-Fi 2G:", self.var_wifi_2g)
        self._option(r, self.var_enc_2g, list(ENC_LABELS.keys()), 210).pack(side="left", padx=(10, 0))

        row_switch("Задать прокси для Podkop", self.var_proxy)

        r = row_switch("Проверить и обновить ОС (прошивку)", self.var_os)
        small_btn(r, "Доп. Софт", self.open_extra_soft)

        self.pages["steps"] = page

        # ----- Страница: Параметры -----
        page = ctk.CTkFrame(content, fg_color="transparent")
        card = self._card(page, "Параметры")
        card.pack(fill="x", padx=14, pady=(14, 10))
        b = card._body

        self.var_ssid = tk.StringVar(value=self.config.get("wifi_ssid", DEFAULTS["wifi_ssid"]))
        self.var_ssid_2g = tk.StringVar(value=self.config.get("wifi_ssid_2g", DEFAULTS["wifi_ssid_2g"]))
        self.var_wifi_pass = tk.StringVar(value=self.config.get("wifi_password", DEFAULTS["wifi_password"]))
        self.var_channel = tk.StringVar(value=self.config.get("wifi_channel", DEFAULTS["wifi_channel"]))
        self.var_channel_2g = tk.StringVar(value=self.config.get("wifi_channel_2g", DEFAULTS["wifi_channel_2g"]))

        grid = ctk.CTkFrame(b, fg_color="transparent")
        grid.pack(fill="x")
        self._lbl(grid, "SSID 5G").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        self._entry(grid, self.var_ssid, 160).grid(row=0, column=1, sticky="w", pady=6)
        self._lbl(grid, "SSID 2G").grid(row=0, column=2, sticky="w", padx=(18, 8), pady=6)
        self._entry(grid, self.var_ssid_2g, 160).grid(row=0, column=3, sticky="w", pady=6)
        self._lbl(grid, "Пароль Wi-Fi").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        self._entry(grid, self.var_wifi_pass, 160).grid(row=1, column=1, sticky="w", pady=6)
        self._lbl(grid, "Канал 5G").grid(row=1, column=2, sticky="w", padx=(18, 8), pady=6)
        self._entry(grid, self.var_channel, 70).grid(row=1, column=3, sticky="w", pady=6)
        self._lbl(grid, "Канал 2G").grid(row=1, column=4, sticky="w", padx=(18, 8), pady=6)
        self._entry(grid, self.var_channel_2g, 70).grid(row=1, column=5, sticky="w", pady=6)

        self._lbl(b, "Прокси (vless:// или подписка):").pack(anchor="w", pady=(10, 4))
        self.proxy_text = ctk.CTkTextbox(b, height=56, wrap="word",
                                         fg_color=self.P["field"], border_color=self.P["border"],
                                         border_width=1, text_color=self.P["text"],
                                         corner_radius=8, font=ctk.CTkFont("Consolas", 11))
        self.proxy_text.pack(fill="x")
        self.proxy_text.insert("1.0", self.config.get("proxy_string", DEFAULTS["proxy_string"]))

        self.pages["params"] = page

        for name, pg in self.pages.items():
            pg.place(in_=self.pages_area, relx=0, rely=0, relwidth=1, relheight=1)

        self._show_page("home")

    def _show_page(self, name):
        for n, pg in self.pages.items():
            if n == name:
                pg.lift()
            else:
                pg.lower()

    # ---------- Окно лога (модалка) ----------
    def _ensure_log(self):
        if hasattr(self, "log_win") and self.log_win.winfo_exists():
            return
        win = ctk.CTkToplevel(self.root)
        win.title("RouterMaster — лог выполнения")
        win.geometry("760x480")
        win.minsize(560, 360)
        win.configure(fg_color=self.P["panel"])
        self.log_win = win

        head = ctk.CTkFrame(win, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(head, text="Лог выполнения", font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=self.P["text"]).pack(side="left")
        self.lbl_time = ctk.CTkLabel(head, text="Время: 0:00",
                                     font=ctk.CTkFont("Segoe UI", 11), text_color=self.P["muted"])
        self.lbl_time.pack(side="right")

        self.progress = ctk.CTkProgressBar(win, mode="indeterminate",
                                           progress_color=self.P["accent2"], height=6,
                                           corner_radius=3)
        self.progress.pack(fill="x", padx=16, pady=(8, 0))
        self.progress.set(0)

        self.log_text = ctk.CTkTextbox(win, wrap="word",
                                       fg_color=self.P["field"], border_color=self.P["border"],
                                       border_width=1, text_color=self.P["text"],
                                       corner_radius=10, font=ctk.CTkFont("Consolas", 11))
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        self.log_text.configure(state="disabled")

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=12)
        self._dialog_btn(btns, "Скопировать лог", self.copy_log).pack(side="left")
        self._dialog_btn(btns, "Очистить лог", self.clear_log).pack(side="left", padx=(8, 0))
        self._dialog_btn(btns, "Скрыть окно", self._close_log).pack(side="right")

        win.protocol("WM_DELETE_WINDOW", self._close_log)
        self.root.after(120, self._center_log)
        self.log("Готово. Заполните настройки и нажмите «ВЫПОЛНИТЬ».")
        win.lift()
        win.focus_force()

    def _center_log(self):
        try:
            self.log_win.update_idletasks()
            x = self.root.winfo_rootx() + (self.root.winfo_width() - self.log_win.winfo_width()) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - self.log_win.winfo_height()) // 2
            self.log_win.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        except Exception:
            pass

    def _show_log(self):
        self._ensure_log()
        self.log_win.deiconify()
        self.log_win.lift()
        self.log_win.focus_force()

    def _close_log(self):
        if hasattr(self, "log_win") and self.log_win.winfo_exists():
            self.log_win.withdraw()

    def apply_theme(self, dark):
        if dark:
            titlebar_dark = True
        else:
            titlebar_dark = False
        self.root.after(100, lambda: self.set_dark_titlebar(titlebar_dark))

    def toggle_gui_theme(self):
        self.is_dark = bool(self.var_gui_dark.get())
        self.config["gui_theme"] = "dark" if self.is_dark else "light"
        try:
            self.save_config()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)])

    def toggle_show_password(self):
        if self.e_pass.cget("show") == "*":
            self.e_pass.configure(show="")
            self.btn_show_pass.configure(text="Скрыть")
        else:
            self.e_pass.configure(show="*")
            self.btn_show_pass.configure(text="Показать")

    # ---------- Диалоги в стиле темы ----------
    def _dialog_window(self, title):
        win = ctk.CTkToplevel(self.root)
        win.overrideredirect(True)
        win.configure(fg_color=self.P["panel"])
        win.transient(self.root)
        win.grab_set()

        bar = ctk.CTkFrame(win, fg_color=self.P["panel"], corner_radius=0)
        bar.pack(fill="x")
        ctk.CTkLabel(bar, text=title, text_color=self.P["text"],
                     font=ctk.CTkFont("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=8)
        close = ctk.CTkLabel(bar, text="\u2715", text_color=self.P["muted"],
                             cursor="hand2", font=ctk.CTkFont("Segoe UI", 12))
        close.pack(side="right", padx=10, pady=4)
        close.bind("<Button-1>", lambda e: win.destroy())

        def start_drag(e):
            win._dx = e.x
            win._dy = e.y

        def drag(e):
            try:
                win.geometry("+%d+%d" % (e.x_root - win._dx, e.y_root - win._dy))
            except Exception:
                pass

        bar.bind("<Button-1>", start_drag)
        bar.bind("<B1-Motion>", drag)

        body = ctk.CTkFrame(win, fg_color=self.P["card"], corner_radius=0)
        body.pack(fill="both", expand=True)
        win._body = body
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_reqheight()) // 3
        win.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        win.update()
        win.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        win.lift()
        win.focus_force()
        return win

    def _dialog_btn(self, parent, text, command, accent=False, width=90):
        if accent:
            return ctk.CTkButton(parent, text=text, width=width, height=34,
                                 fg_color=self.P["accent"], hover_color=self.P["accent_hover"],
                                 text_color="#ffffff", corner_radius=8,
                                 font=ctk.CTkFont("Segoe UI", 11, "bold"), command=command)
        return ctk.CTkButton(parent, text=text, width=width, height=34,
                             fg_color=self.P["card"], hover_color=self.P["border"],
                             border_width=1, border_color=self.P["border"],
                             text_color=self.P["text"], corner_radius=8,
                             font=ctk.CTkFont("Segoe UI", 11), command=command)

    def show_message(self, title, message):
        win = self._dialog_window(title)
        ctk.CTkLabel(win._body, text=message, wraplength=400, justify="left",
                     text_color=self.P["text"],
                     font=ctk.CTkFont("Segoe UI", 11)).pack(padx=18, pady=(16, 12))
        self._dialog_btn(win._body, "OK", win.destroy, accent=True).pack(pady=(0, 14))
        win.lift()
        win.focus_force()
        self.root.wait_window(win)

    def open_extra_soft(self):
        win = self._dialog_window("Доп. Софт")
        ctk.CTkLabel(win._body,
                     text="Здесь будут дополнительные программы\nдля установки на роутер.\nПока пусто — вернитесь позже.",
                     wraplength=400, justify="center", text_color=self.P["text"],
                     font=ctk.CTkFont("Segoe UI", 11)).pack(padx=18, pady=(18, 12))
        self._dialog_btn(win._body, "Закрыть", win.destroy, accent=True).pack(pady=(0, 14))
        win.lift()
        win.focus_force()
        self.root.wait_window(win)

    def ask_confirm(self, title, message):
        result = {"ok": False}
        win = self._dialog_window(title)
        ctk.CTkLabel(win._body, text=message, wraplength=420, justify="left",
                     text_color=self.P["text"],
                     font=ctk.CTkFont("Segoe UI", 11)).pack(padx=18, pady=(16, 12))

        def yes():
            result["ok"] = True
            win.destroy()

        btns = ctk.CTkFrame(win._body, fg_color="transparent")
        btns.pack(pady=(0, 14))
        self._dialog_btn(btns, "Да", yes, accent=True).pack(side="left", padx=6)
        self._dialog_btn(btns, "Отмена", win.destroy).pack(side="left", padx=6)
        win.lift()
        win.focus_force()
        self.root.wait_window(win)
        return result["ok"]

    # ---------- Прогресс и время ----------
    def start_progress(self):
        self._timer_running = True
        self._start_time = time.time()
        self.progress.start(10)
        self.lbl_time.configure(text="Время: 0:00")
        self._update_timer()

    def _update_timer(self):
        if not self._timer_running:
            return
        el = int(time.time() - self._start_time)
        m, s = divmod(el, 60)
        self.lbl_time.configure(text="Время: %d:%02d" % (m, s))
        self.root.after(1000, self._update_timer)

    def stop_progress(self):
        self._timer_running = False
        self.progress.stop()
        self.progress.set(0)
        if hasattr(self, "_start_time"):
            el = int(time.time() - self._start_time)
            m, s = divmod(el, 60)
            self.lbl_time.configure(text="Время: %d:%02d (готово)" % (m, s))

    # ---------- Удаление сервисов ----------
    def _connect_ssh(self):
        host = self.var_host.get().strip()
        port = int(self.var_port.get() or 22)
        user = self.var_user.get().strip()
        password = self.var_pass.get()
        self.log("=== Подключение к %s:%s ... ===" % (host, port))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password,
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log("Подключено.")
        return client

    def remove_podkop(self):
        if not self.var_host.get().strip() or not self.var_pass.get():
            self.show_message("Внимание", "Укажите IP роутера и пароль SSH!")
            return
        if not self.ask_confirm("Удаление Podkop",
                                "Удалить Podkop с роутера?\n\n"
                                "Будут остановлены и удалены:\n"
                                "- сервис /etc/init.d/podkop\n"
                                "- конфигурация uci podkop и файл /etc/config/podkop\n"
                                "- пакеты podkop, luci-app-podkop, luci-i18n-podkop-ru"):
            return
        threading.Thread(target=self._remove_podkop_worker, daemon=True).start()

    def _remove_podkop_worker(self):
        self.start_progress()
        try:
            self.log("--- Podkop: удаление ---")
            client = self._connect_ssh()
            cmd = (
                "/etc/init.d/podkop stop 2>/dev/null; "
                "/etc/init.d/podkop disable 2>/dev/null; "
                "rm -f /etc/init.d/podkop; "
                "uci -q delete podkop; uci commit 2>/dev/null; "
                "rm -rf /etc/podkop /etc/config/podkop /tmp/podkop*; "
                "apk del podkop luci-app-podkop luci-i18n-podkop-ru 2>/dev/null; "
                "opkg remove podkop luci-app-podkop luci-i18n-podkop-ru 2>/dev/null; "
                "echo REMOVE_DONE"
            )
            self.ssh_exec(client, cmd, timeout=300)
            self.log("Podkop успешно удалён с роутера.")
            client.close()
        except Exception as e:
            self.log("ОШИБКА: " + str(e))
            self.root.after(0, lambda: self.show_message("Ошибка", str(e)))
        finally:
            self.stop_progress()
            self.log("Удаление завершено.")

    def remove_zapret(self):
        if not self.var_host.get().strip() or not self.var_pass.get():
            self.show_message("Внимание", "Укажите IP роутера и пароль SSH!")
            return
        if not self.ask_confirm("Удаление Zapret",
                                "Удалить Zapret и Zapret-Manager с роутера?\n\n"
                                "Будут остановлены и удалены:\n"
                                "- сервис /etc/init.d/zapret\n"
                                "- файлы /etc/zapret, /opt/zapret\n"
                                "- утилиты zms / zmsA\n"
                                "- конфигурация uci zapret"):
            return
        threading.Thread(target=self._remove_zapret_worker, daemon=True).start()

    def _remove_zapret_worker(self):
        self.start_progress()
        try:
            self.log("--- Zapret: удаление ---")
            client = self._connect_ssh()
            cmd = (
                "/etc/init.d/zapret stop 2>/dev/null; "
                "/etc/init.d/zapret disable 2>/dev/null; "
                "rm -f /etc/init.d/zapret; "
                "rm -rf /etc/zapret /opt/zapret /usr/lib/zapret; "
                "rm -f /usr/bin/zms /usr/bin/zmsA /usr/sbin/zapret /usr/sbin/zapret-xray; "
                "uci -q delete zapret; uci commit 2>/dev/null; "
                "rm -f /etc/config/zapret; "
                "echo REMOVE_DONE"
            )
            self.ssh_exec(client, cmd, timeout=300)
            self.log("Zapret успешно удалён с роутера.")
            client.close()
        except Exception as e:
            self.log("ОШИБКА: " + str(e))
            self.root.after(0, lambda: self.show_message("Ошибка", str(e)))
        finally:
            self.stop_progress()
            self.log("Удаление завершено.")

    def set_dark_titlebar(self, dark, win=None):
        try:
            if win is None:
                win = self.root
            hwnd = win.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                hwnd = parent
            value = ctypes.c_int(1 if dark else 0)
            for attr in (20, 19):
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
                except Exception:
                    pass
        except Exception:
            pass

    def set_app_icon(self, root):
        try:
            base = getattr(sys, "_MEIPASS", APP_DIR)
            ico = os.path.join(base, "assets", "icon.ico")
            if os.path.exists(ico):
                root.iconbitmap(default=ico)
        except Exception:
            pass

    def add_context_menu(self, widget):
        menu = tk.Menu(widget, tearoff=0)

        def get_text():
            try:
                return widget.get("1.0", "end-1c")
            except Exception:
                try:
                    return widget.get()
                except Exception:
                    return ""

        menu.add_command(label="Копировать", command=lambda: (
            self.root.clipboard_clear(),
            self.root.clipboard_append(get_text())))
        try:
            menu.add_command(label="Вставить", command=lambda: widget.insert(
                "insert" if hasattr(widget, "insert") and not isinstance(widget.get(), str) else "end",
                self.root.clipboard_get()))
        except Exception:
            pass
        menu.add_command(label="Выделить всё", command=lambda: widget.focus_set())
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    # ---------- Лог ----------
    def on_close(self):
        try:
            self.save_config()
        except Exception:
            pass
        self.root.destroy()

    def log(self, msg):
        if not hasattr(self, "log_text") or not self.log_text.winfo_exists():
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()

    def clear_log(self):
        if not hasattr(self, "log_text") or not self.log_text.winfo_exists():
            return
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def copy_log(self):
        if not hasattr(self, "log_text") or not self.log_text.winfo_exists():
            return
        content = self.log_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.log("Лог скопирован в буфер обмена.")

    # ---------- Обновление ----------
    def check_update(self):
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _ver_tuple(self, v):
        parts = re.findall(r"\d+", v)
        parts = (parts + ["0", "0", "0"])[:3]
        return tuple(int(x) for x in parts)

    def _check_update_worker(self):
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/%s/releases/latest" % UPDATE_REPO,
                headers={"User-Agent": "RouterMaster"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            latest_tag = str(data.get("tag_name", "v0.0.0")).lstrip("v")
            if self._ver_tuple(latest_tag) > self._ver_tuple(APP_VERSION):
                self.root.after(0, lambda: self._prompt_update(data, latest_tag))
            else:
                self.root.after(0, lambda: self.show_message(
                    "Обновление", "Установлена последняя версия %s" % APP_VERSION))
        except Exception as e:
            self.root.after(0, lambda: self.show_message(
                "Ошибка", "Не удалось проверить обновление:\n%s" % e))

    def _prompt_update(self, data, latest_tag):
        if not self.ask_confirm(
                "Обновление",
                "Доступна новая версия %s!\n\nТекущая версия: %s\n\n"
                "Скачать установщик и установить сейчас?" % (latest_tag, APP_VERSION)):
            return
        for a in data.get("assets", []):
            if a.get("name", "").lower() == UPDATE_ASSET.lower():
                self._download_and_install(a["browser_download_url"], a["name"])
                return
        self.show_message("Обновление", "Установщик не найден в релизе.")

    def _unblock_file(self, path):
        try:
            return bool(ctypes.windll.kernel32.DeleteFileW(path + ":Zone.Identifier"))
        except Exception:
            return False

    def _download_and_install(self, url, name):
        def work():
            try:
                tmp = os.path.join(tempfile.gettempdir(), name)
                req = urllib.request.Request(url, headers={"User-Agent": "RouterMaster"})
                with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as f:
                    shutil.copyfileobj(r, f)
                self.log("Обновление скачано: %s" % tmp)
                self.log("Снимаю блокировку SmartScreen (Mark of the Web)...")
                self._unblock_file(tmp)
                self.log("Запускаю тихую установку (без окон)...")
                upd_src = os.path.join(
                    getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                    "assets", "rm_updater.exe")
                upd_tmp = os.path.join(tempfile.gettempdir(), "rm_updater.exe")
                shutil.copyfile(upd_src, upd_tmp)
                subprocess.Popen([upd_tmp, tmp, self._installed_exe()],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                self.log("Программа закроется и перезапустится автоматически.")
                self.root.after(1000, self._close_for_update)
            except Exception as e:
                self.root.after(0, lambda: self.show_message(
                    "Ошибка", "Не удалось скачать обновление:\n%s" % e))
        self.log("Скачивание обновления...")
        threading.Thread(target=work, daemon=True).start()

    def _close_for_update(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _installed_exe(self):
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                               "{8E7F2B1C-9A3D-4F5E-8B2A-0C1D2E3F4A5B}_is1")
            loc = winreg.QueryValueEx(k, "InstallLocation")[0]
            return os.path.join(loc, "RouterMaster.exe")
        except Exception:
            return os.path.join(APP_DIR, "RouterMaster.exe")

    # ---------- Конфиг ----------
    def load_config(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
        old_cfg = os.path.join(APP_DIR, "router_tool_config.json")
        if not os.path.exists(CONFIG_FILE) and os.path.exists(old_cfg):
            try:
                shutil.copyfile(old_cfg, CONFIG_FILE)
            except Exception:
                pass
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                for k, v in DEFAULTS.items():
                    cfg.setdefault(k, v)
                return cfg
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULTS))

    def save_config(self):
        cfg = {
            "host": self.var_host.get().strip(),
            "port": int(self.var_port.get() or 22),
            "user": self.var_user.get().strip(),
            "password": self.var_pass.get(),
            "wifi_ssid": self.var_ssid.get().strip(),
            "wifi_ssid_2g": self.var_ssid_2g.get().strip(),
            "wifi_password": self.var_wifi_pass.get(),
            "wifi_channel": self.var_channel.get().strip(),
            "wifi_channel_2g": self.var_channel_2g.get().strip(),
            "wifi_enc_5g": self.var_enc_5g.get(),
            "wifi_enc_2g": self.var_enc_2g.get(),
            "proxy_string": self.proxy_text.get("1.0", "end-1c").strip(),
            "theme": self.var_theme.get(),
            "gui_theme": "dark" if self.var_gui_dark.get() else "light",
            "steps": {
                "update_packages": self.var_update.get(),
                "install_podkop": self.var_podkop.get(),
                "install_zapret": self.var_zapret.get(),
                "install_argon": self.var_argon.get(),
                "install_ru": self.var_ru.get(),
                "setup_wifi": self.var_wifi.get(),
                "setup_wifi_2g": self.var_wifi_2g.get(),
                "setup_proxy": self.var_proxy.get(),
                "update_os": self.var_os.get(),
            },
        }
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self.log("Настройки сохранены в " + CONFIG_FILE)

    # ---------- SSH ----------
    def ssh_exec(self, client, cmd, timeout=300):
        self.log("$ " + cmd)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            for line in out.rstrip().splitlines():
                self.log("  " + line)
        if err.strip():
            for line in err.rstrip().splitlines():
                self.log("  [stderr] " + line)
        return out, err

    def ssh_upload(self, client, local_path, remote_path):
        self.log("Заливаю %s на роутер..." % os.path.basename(local_path))
        sftp = client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()
        self.log("  загружено: %s" % remote_path)

    # ---------- Запуск ----------
    def run_all(self):
        if not self.var_host.get().strip() or not self.var_pass.get():
            self.show_message("Внимание", "Укажите IP роутера и пароль SSH!")
            return
        need_key = (
            (self.var_wifi.get() and ENC_LABELS.get(self.var_enc_5g.get(), "sae") != "none")
            or (self.var_wifi_2g.get() and ENC_LABELS.get(self.var_enc_2g.get(), "psk2") != "none")
        )
        if need_key and len(self.var_wifi_pass.get()) < 8:
            self.show_message("Внимание", "Пароль Wi-Fi должен быть не короче 8 символов!")
            return
        self._ensure_log()
        self._show_log()
        self.btn_run.config(state="disabled")
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        self.start_progress()
        try:
            self.run_steps()
        except Exception as e:
            self.log("ОШИБКА: " + str(e))
            self.root.after(0, lambda: self.show_message("Ошибка", str(e)))
        finally:
            self.stop_progress()
            self.root.after(0, lambda: self.btn_run.config(state="normal"))
            self.root.after(0, self._show_log)
            self.log("Завершено.")

    def run_steps(self):
        host = self.var_host.get().strip()
        port = int(self.var_port.get() or 22)
        user = self.var_user.get().strip()
        password = self.var_pass.get()

        self.log("=== Подключение к %s:%s ... ===" % (host, port))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password,
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log("Подключено.")

        do = self.var_update.get()
        if do:
            self.log("--- Обновление пакетов ---")
            self.ssh_exec(client, "apk update")
            out, _ = self.ssh_exec(client, "apk upgrade")
            if "error" in out.lower():
                out2, _ = self.ssh_exec(client, "apk upgrade")
                self.log("Повторный apk upgrade выполнен.")

        if self.var_podkop.get():
            self.log("--- Podkop: установка/обновление ---")
            self.ssh_exec(client, "wget -qO /tmp/podkop_install.sh https://raw.githubusercontent.com/itdoginfo/podkop/refs/heads/main/install.sh")
            self.ssh_exec(client, "printf 'y\\ny\\ny\\ny\\ny\\n' | sh /tmp/podkop_install.sh", timeout=600)
            self.ssh_exec(client, "uci delete podkop.@section[0].community_lists 2>/dev/null; for s in %s; do uci add_list podkop.@section[0].community_lists=\"$s\"; done; uci commit podkop" % PODKOP_COMMUNITY_LISTS)
            self.ssh_exec(client, "/etc/init.d/podkop enable; /etc/init.d/podkop start", timeout=60)

        if self.var_zapret.get():
            self.log("--- Zapret-Manager + Zapret (быстрый старт) ---")
            cmd = (
                "git='github.com'; grep -q \"^140.82.114.3 $git\" /etc/hosts || { "
                "printf '#$git\\n140.82.114.3 $git\\n185.199.110.154 github.githubassets.com\\n185.199.110.133 camo.githubassets.com\\n' >> /etc/hosts; "
                "/etc/init.d/dnsmasq restart 2>/dev/null; }; "
                "wget -q -O /tmp/Zapret-Manager.sh https://raw.githubusercontent.com/StressOzz/Zapret-Manager/main/Zapret-Manager.sh && "
                "printf 'f\\n' | sh /tmp/Zapret-Manager.sh; "
                "rm -f /tmp/Zapret-Manager.sh; "
                "[ -f /etc/init.d/zapret ] && /etc/init.d/zapret enable && /etc/init.d/zapret start"
            )
            self.ssh_exec(client, cmd, timeout=900)

        if self.var_argon.get():
            theme_name = self.var_theme.get() or "Argon"
            theme = THEMES.get(theme_name, THEMES["Argon"])
            self.log("--- Тема: %s ---" % theme_name)
            if "url" in theme:
                exists, _ = self.ssh_exec(client, "apk info 2>/dev/null | grep -c '^%s$'" % theme["pkg"])
                if exists.strip() == "0":
                    self.install_theme_file(client, theme)
            else:
                self.ssh_exec(client, "apk add " + theme["pkg"], timeout=300)
            self.ssh_exec(client, "uci set luci.main.mediaurlbase='%s'; uci commit luci" % theme["media"])

        if self.var_ru.get():
            self.log("--- Русский язык ---")
            self.ssh_exec(client, "apk add luci-i18n-base-ru", timeout=300)
            self.ssh_exec(client, "uci set luci.main.lang=ru; uci commit luci")

        if self.var_wifi.get() or self.var_wifi_2g.get():
            self.log("--- Wi-Fi ---")
            wp = self.var_wifi_pass.get()
            chan = self.var_channel.get().strip() or "36"
            parts = []
            if self.var_wifi.get():
                ssid = self.var_ssid.get().strip()
                enc5 = ENC_LABELS.get(self.var_enc_5g.get(), "sae")
                self.log("Wi-Fi 5G: SSID '%s', канал %s, шифрование %s" % (ssid, chan, enc5))
                parts.append("uci set wireless.default_radio1.ssid='%s'; " % ssid.replace("'", ""))
                if enc5 == "none":
                    parts.append("uci set wireless.default_radio1.encryption='none'; "
                                 "uci delete wireless.default_radio1.key; ")
                else:
                    parts.append("uci set wireless.default_radio1.encryption='%s'; "
                                 "uci set wireless.default_radio1.key='%s'; "
                                 % (enc5, wp.replace("'", "")))
                parts.append("uci set wireless.default_radio1.disabled='0'; "
                             "uci set wireless.radio1.channel='%s'; " % chan)
            if self.var_wifi_2g.get():
                ssid2 = self.var_ssid_2g.get().strip() or "OpenWrt 2G"
                enc2 = ENC_LABELS.get(self.var_enc_2g.get(), "psk2")
                chan2 = self.var_channel_2g.get().strip() or "auto"
                self.log("Wi-Fi 2G: SSID '%s', канал %s, шифрование %s" % (ssid2, chan2, enc2))
                parts.append("uci set wireless.default_radio0.ssid='%s'; " % ssid2.replace("'", ""))
                if enc2 == "none":
                    parts.append("uci set wireless.default_radio0.encryption='none'; "
                                 "uci delete wireless.default_radio0.key; ")
                else:
                    parts.append("uci set wireless.default_radio0.encryption='%s'; "
                                 "uci set wireless.default_radio0.key='%s'; "
                                 % (enc2, wp.replace("'", "")))
                parts.append("uci set wireless.default_radio0.disabled='0'; "
                             "uci set wireless.radio0.channel='%s'; " % chan2)
            cmd = "".join(parts) + "uci commit wireless; wifi reload"
            self.ssh_exec(client, cmd)

        if self.var_proxy.get():
            proxy = self.proxy_text.get("1.0", "end-1c").strip()
            if proxy:
                self.log("--- Прокси для Podkop ---")
                self.ssh_exec(client,
                              "uci set podkop.@section[0].proxy_string='%s'; uci commit podkop; "
                              "/etc/init.d/podkop restart" % proxy.replace("'", ""))
            else:
                self.log("Прокси не задан — пропускаю.")

        if self.var_os.get():
            self.log("--- Проверка версии ОС ---")
            out, _ = self.ssh_exec(client, "owut check 2>&1 | grep -E 'Version-from|Version-to|ERROR'", timeout=300)
            upgrade = None
            for line in out.splitlines():
                if "Version-to" in line:
                    upgrade = line.split("Version-to")[1].strip()
            if upgrade and "25.12.5" not in upgrade:
                self.log("Найдено обновление ОС: " + upgrade)
                ok = self.ask_confirm("Обновление ОС",
                                          "Найдено обновление: %s\n\n"
                                          "ВНИМАНИЕ: роутер перезагрузится, SSH-соединение прервётся на 2-5 минут.\n"
                                          "Продолжить?" % upgrade)
                if ok:
                    self.ssh_exec(client,
                                  "printf 'y\\n' | owut upgrade --ignored-changes 'luci-app-podkop,luci-i18n-podkop-ru,luci-theme-argon,podkop' >/dev/null 2>&1 &",
                                  timeout=60)
                    self.log("Обновление запущено. Роутер перезагрузится. Подождите 2-5 минут, "
                             "затем запустите программу ещё раз для установки Podkop и темы Argon.")
                else:
                    self.log("Обновление ОС отменено пользователем.")
            else:
                self.log("ОС актуальна — обновлений нет (25.12.5).")

        self.log("=== Установка завершена. Перезагружаю роутер... ===")
        try:
            self.ssh_exec(client, "sleep 2; reboot", timeout=30)
        except Exception:
            pass
        client.close()

        self.log("Ожидаю включения роутера...")
        deadline = time.time() + 300
        back_up = False
        while time.time() < deadline:
            time.sleep(10)
            try:
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(host, port=port, username=user, password=password,
                          timeout=8, look_for_keys=False, allow_agent=False)
                c.close()
                back_up = True
                break
            except Exception:
                self.log("  ожидание роутера...")

        if back_up:
            self.log("Роутер снова в сети!")
            self.root.after(0, lambda: self.show_message(
                "Готово",
                "Роутер перезагрузился и снова в сети.\n\n"
                "Обновите страницу в браузере (Ctrl+F5),\n"
                "чтобы увидеть новый интерфейс: http://%s" % host))
        else:
            self.log("Роутер не вернулся в сеть за 5 минут — проверьте питание.")

    def install_theme_file(self, client, theme):
        self.log("%s: скачивание apk на ПК..." % theme["pkg"])
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        except Exception:
            pass
        local = os.path.join(DOWNLOAD_DIR, theme["pkg"] + ".apk")
        urllib.request.urlretrieve(theme["url"], local)
        self.log("  скачано: %s байт (папка программы: %s)" % (os.path.getsize(local), DOWNLOAD_DIR))
        self.ssh_exec(client, "apk add openssh-sftp-server", timeout=300)
        self.ssh_upload(client, local, "/tmp/theme.apk")
        self.ssh_exec(client, "apk add --allow-untrusted /tmp/theme.apk", timeout=300)

    # ---------- Сброс + настройка ----------
    def reset_and_setup(self):
        if not self.var_host.get().strip() or not self.var_pass.get():
            self.show_message("Внимание", "Укажите IP роутера и пароль SSH!")
            return
        ok = self.ask_confirm(
            "Сброс роутера",
            "ВНИМАНИЕ! Все настройки роутера будут сброшены к заводским:\n"
            "- удалятся пароли, Wi-Fi, Podkop, тема, пакеты\n\n"
            "После сброса роутер перезагрузится,\n"
            "затем пароль %s будет установлен автоматически,\n"
            "и автоматически выполнится полная настройка:\n"
            "Wi-Fi 2.4/5 ГГц, Podkop, тема, язык.\n\n"
            "Обычно это занимает 3-4 минуты, редко дольше.\n\n"
            "Продолжить?" % self.var_pass.get())
        if not ok:
            return
        self.new_password = self.var_pass.get()
        self._ensure_log()
        self._show_log()
        self.btn_run.config(state="disabled")
        self.btn_reset.config(state="disabled")
        threading.Thread(target=self.reset_worker, daemon=True).start()

    def reset_worker(self):
        self.start_progress()
        try:
            self.do_reset_and_setup()
        except Exception as e:
            self.log("ОШИБКА: " + str(e))
            self.root.after(0, lambda: self.show_message("Ошибка", str(e)))
        finally:
            self.stop_progress()
            self.root.after(0, lambda: self.btn_run.config(state="normal"))
            self.root.after(0, lambda: self.btn_reset.config(state="normal"))
            self.root.after(0, self._show_log)
            self.log("Завершено.")

    def do_reset_and_setup(self):
        host = self.var_host.get().strip()
        port = int(self.var_port.get() or 22)
        user = self.var_user.get().strip()

        self.log("=== Сброс к заводским настройкам ===")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=self.var_pass.get(),
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log("Подключено. Выполняю сброс (как кнопка Perform reset в LuCI)...")
        try:
            self.ssh_exec(client, "/sbin/firstboot -r -y", timeout=60)
        except Exception:
            self.log("Соединение прервано — роутер сбрасывается.")
        client.close()

        self.log("Открываю веб-панель: http://%s" % host)
        webbrowser.open("http://%s/cgi-bin/luci/admin/system/flash" % host)

        self.log("Ожидаю загрузки роутера...")
        deadline = time.time() + 600
        luci_up = False
        while time.time() < deadline:
            time.sleep(5)
            try:
                urllib.request.urlopen("http://%s/cgi-bin/luci/" % host, timeout=5)
                luci_up = True
                break
            except urllib.error.HTTPError as e:
                if e.code in (200, 301, 302, 403):
                    luci_up = True
                    break
            except Exception:
                self.log("  ожидание роутера...")

        if luci_up:
            self.log("LuCI доступна — устанавливаю пароль автоматически...")
            if self.luci_set_password(host, self.new_password):
                self.log("Пароль установлен автоматически!")
            else:
                self.log("Автоустановка пароля не прошла — установите пароль %s в веб-панели вручную." % self.new_password)
        else:
            self.log("LuCI не поднялась за 10 минут — проверьте роутер.")

        self.log("Ожидаю SSH...")
        deadline = time.time() + 900
        connected = False
        while time.time() < deadline:
            time.sleep(10)
            try:
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(host, port=port, username=user, password=self.new_password,
                          timeout=8, look_for_keys=False, allow_agent=False)
                c.close()
                connected = True
                break
            except Exception:
                self.log("  ожидание SSH...")

        if not connected:
            raise RuntimeError("Не удалось подключиться после сброса за 15 минут. Проверьте пароль в веб-панели.")

        self.log("Роутер доступен с новым паролем! Устанавливаю всё...")
        self.var_pass.set(self.new_password)
        self.save_config()
        self.run_steps()

    def luci_set_password(self, host, new_password):
        try:
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            data = "luci_username=root&luci_password=".encode()
            req = urllib.request.Request("http://%s/cgi-bin/luci/" % host, data=data, method="POST")
            try:
                opener.open(req, timeout=10)
            except urllib.error.HTTPError:
                pass
            sid = None
            for c in cj:
                if c.name in ("sysauth_http", "sysauth_https"):
                    sid = c.value
            if not sid:
                return False
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "call",
                               "params": [sid, "luci", "setPassword",
                                          {"username": "root", "password": new_password}]}).encode()
            req = urllib.request.Request("http://%s/ubus" % host, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = opener.open(req, timeout=10)
            reply = json.loads(resp.read().decode())
            result = reply.get("result", [])
            return len(result) > 1 and result[0] == 0 and result[1].get("result") is True
        except Exception:
            return False


def main():
    root = ctk.CTk()
    RouterToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()