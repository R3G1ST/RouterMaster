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
from tkinter import ttk, messagebox, filedialog, simpledialog
import paramiko

APP_VERSION = "1.2.5"
UPDATE_REPO = "R3G1ST/RouterMaster"
UPDATE_ASSET = "RouterMaster-Setup.exe"

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "router_tool_config.json")
DOWNLOAD_DIR = os.path.join(APP_DIR, "downloads")

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


class RouterToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Роутер Мастер — OpenWrt")
        self.root.geometry("900x660")
        self.root.resizable(False, False)
        self.config = self.load_config()

        self.is_dark = self.config.get("gui_theme", DEFAULTS["gui_theme"]) == "dark"
        self.var_gui_dark = tk.BooleanVar(value=self.is_dark)
        self.apply_theme(root, self.is_dark)
        self.set_app_icon(root)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        # ============ Настройки подключения ============
        conn = ttk.LabelFrame(main, text="Подключение к роутеру", padding=8)
        conn.pack(fill="x", pady=(0, 8))

        self.var_host = tk.StringVar(value=self.config.get("host", DEFAULTS["host"]))
        self.var_port = tk.StringVar(value=self.config.get("port", DEFAULTS["port"]))
        self.var_user = tk.StringVar(value=self.config.get("user", DEFAULTS["user"]))
        self.var_pass = tk.StringVar(value=self.config.get("password", DEFAULTS["password"]))

        ttk.Label(conn, text="IP роутера:").grid(row=0, column=0, sticky="e", padx=6, pady=3)
        e_host = ttk.Entry(conn, textvariable=self.var_host, width=18)
        e_host.grid(row=0, column=1, sticky="w", padx=6)
        self.add_context_menu(e_host)
        ttk.Label(conn, text="Порт:").grid(row=0, column=2, sticky="e", padx=6)
        e_port = ttk.Entry(conn, textvariable=self.var_port, width=6)
        e_port.grid(row=0, column=3, sticky="w", padx=6)
        self.add_context_menu(e_port)
        ttk.Label(conn, text="Логин:").grid(row=1, column=0, sticky="e", padx=6, pady=3)
        e_user = ttk.Entry(conn, textvariable=self.var_user, width=18)
        e_user.grid(row=1, column=1, sticky="w", padx=6)
        self.add_context_menu(e_user)
        ttk.Label(conn, text="Пароль:").grid(row=1, column=2, sticky="e", padx=6)
        self.e_pass = ttk.Entry(conn, textvariable=self.var_pass, width=18, show="*")
        self.e_pass.grid(row=1, column=3, sticky="w", padx=6)
        self.add_context_menu(self.e_pass)
        self.btn_show_pass = ttk.Button(conn, text="Показать", width=9,
                                        command=self.toggle_show_password)
        self.btn_show_pass.grid(row=1, column=4, sticky="w", padx=(0, 6))
        conn.columnconfigure(4, weight=1)
        ttk.Button(conn, text="Проверить обновление", command=self.check_update).grid(
            row=0, column=5, rowspan=2, sticky="e", padx=6, pady=3)
        ttk.Checkbutton(conn, text="Тёмная тема", variable=self.var_gui_dark,
                        command=self.toggle_gui_theme).grid(
            row=0, column=6, rowspan=2, sticky="e", padx=(0, 6))
        ttk.Label(conn, text="RouterMaster v%s\nАвтор: R3G1ST" % APP_VERSION,
                  justify="right").grid(row=0, column=7, rowspan=2, sticky="ne", padx=(0, 2))

        # ============ Что делать ============
        steps = ttk.LabelFrame(main, text="Что выполнить (можно выбрать несколько)", padding=8)
        steps.pack(fill="x", pady=(0, 8))

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

        ttk.Checkbutton(steps, text="Обновить все пакеты", variable=self.var_update).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(steps, text="Установить / обновить Podkop", variable=self.var_podkop).grid(row=0, column=1, sticky="w", padx=8, pady=4)
        ttk.Button(steps, text="Удалить", width=8, command=self.remove_podkop).grid(row=0, column=2, sticky="w", padx=(0, 8), pady=4)
        ttk.Checkbutton(steps, text="Установить / обновить Zapret", variable=self.var_zapret).grid(row=1, column=1, sticky="w", padx=8, pady=4)
        ttk.Button(steps, text="Удалить", width=8, command=self.remove_zapret).grid(row=1, column=2, sticky="w", padx=(0, 8), pady=4)

        theme_cell = ttk.Frame(steps)
        theme_cell.grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(theme_cell, text="Установить тему:", variable=self.var_argon).pack(side="left")
        self.var_theme = tk.StringVar(value=self.config.get("theme", DEFAULTS["theme"]))
        ttk.Combobox(theme_cell, textvariable=self.var_theme, values=list(THEMES.keys()),
                     state="readonly", width=20).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(steps, text="Русский язык интерфейса", variable=self.var_ru).grid(row=2, column=1, sticky="w", padx=8, pady=4)

        wifi5_cell = ttk.Frame(steps)
        wifi5_cell.grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(wifi5_cell, text="Создать Wi-Fi 5G:", variable=self.var_wifi).pack(side="left")
        ttk.Combobox(wifi5_cell, textvariable=self.var_enc_5g, values=list(ENC_LABELS.keys()),
                     state="readonly", width=20).pack(side="left", padx=(8, 0))

        wifi2_cell = ttk.Frame(steps)
        wifi2_cell.grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(wifi2_cell, text="Создать Wi-Fi 2G:", variable=self.var_wifi_2g).pack(side="left")
        ttk.Combobox(wifi2_cell, textvariable=self.var_enc_2g, values=list(ENC_LABELS.keys()),
                     state="readonly", width=20).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(steps, text="Задать прокси для Podkop", variable=self.var_proxy).grid(row=4, column=0, sticky="w", padx=8, pady=4)

        ttk.Checkbutton(steps, text="Проверить и обновить ОС (прошивку)", variable=self.var_os).grid(row=3, column=1, sticky="w", padx=8, pady=4)

        steps.columnconfigure(0, weight=1, uniform="steps")
        steps.columnconfigure(1, weight=1, uniform="steps")

        # ============ Параметры ============
        params = ttk.LabelFrame(main, text="Параметры", padding=8)
        params.pack(fill="x", pady=(0, 8))

        self.var_ssid = tk.StringVar(value=self.config.get("wifi_ssid", DEFAULTS["wifi_ssid"]))
        self.var_ssid_2g = tk.StringVar(value=self.config.get("wifi_ssid_2g", DEFAULTS["wifi_ssid_2g"]))
        self.var_wifi_pass = tk.StringVar(value=self.config.get("wifi_password", DEFAULTS["wifi_password"]))
        self.var_channel = tk.StringVar(value=self.config.get("wifi_channel", DEFAULTS["wifi_channel"]))
        self.var_channel_2g = tk.StringVar(value=self.config.get("wifi_channel_2g", DEFAULTS["wifi_channel_2g"]))
        self.var_proxy_str = tk.StringVar(value=self.config.get("proxy_string", DEFAULTS["proxy_string"]))

        ttk.Label(params, text="SSID Wi-Fi:").grid(row=0, column=0, sticky="e", padx=6, pady=3)
        e_ssid = ttk.Entry(params, textvariable=self.var_ssid, width=16)
        e_ssid.grid(row=0, column=1, sticky="w", padx=6)
        self.add_context_menu(e_ssid)
        ttk.Label(params, text="SSID 2G:").grid(row=0, column=2, sticky="e", padx=6)
        e_ssid2 = ttk.Entry(params, textvariable=self.var_ssid_2g, width=16)
        e_ssid2.grid(row=0, column=3, sticky="w", padx=6)
        self.add_context_menu(e_ssid2)
        ttk.Label(params, text="Пароль Wi-Fi:").grid(row=0, column=4, sticky="e", padx=6)
        e_wpass = ttk.Entry(params, textvariable=self.var_wifi_pass, width=16)
        e_wpass.grid(row=0, column=5, sticky="w", padx=6)
        self.add_context_menu(e_wpass)
        ttk.Label(params, text="Канал 5G:").grid(row=1, column=0, sticky="e", padx=6, pady=3)
        e_chan = ttk.Entry(params, textvariable=self.var_channel, width=5)
        e_chan.grid(row=1, column=1, sticky="w", padx=6)
        self.add_context_menu(e_chan)
        ttk.Label(params, text="Канал 2G:").grid(row=1, column=2, sticky="e", padx=6, pady=3)
        e_chan2 = ttk.Entry(params, textvariable=self.var_channel_2g, width=5)
        e_chan2.grid(row=1, column=3, sticky="w", padx=6)
        self.add_context_menu(e_chan2)
        ttk.Label(params, text="Прокси (vless:// или подписка):").grid(row=2, column=0, sticky="e", padx=6, pady=3)
        self.proxy_text = tk.Text(params, width=38, height=2, wrap="word",
                                  relief="flat", borderwidth=2)
        self.proxy_text.grid(row=2, column=1, columnspan=5, sticky="we", padx=6, pady=3)
        self.proxy_text.insert("1.0", self.config.get("proxy_string", DEFAULTS["proxy_string"]))
        self.add_context_menu(self.proxy_text)

        # ============ Кнопки ============
        btns = ttk.Frame(main)
        btns.pack(fill="x", pady=(0, 8))

        self.btn_run = ttk.Button(btns, text="ВЫПОЛНИТЬ", command=self.run_all, style="Accent.TButton")
        self.btn_run.pack(side="left", padx=4, pady=2)
        self.btn_reset = ttk.Button(btns, text="Сброс + настройка", command=self.reset_and_setup)
        self.btn_reset.pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Сохранить настройки", command=self.save_config).pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Скопировать лог", command=self.copy_log).pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Очистить лог", command=self.clear_log).pack(side="left", padx=4, pady=2)

        # ============ Лог ============
        log_frame = ttk.LabelFrame(main, text="Лог", padding=4)
        log_frame.pack(fill="both", expand=True)

        self.lbl_time = ttk.Label(log_frame, text="Время: 0:00")
        self.lbl_time.pack(side="right", padx=(4, 8), pady=2)
        self.progress = ttk.Progressbar(log_frame, mode="indeterminate", length=140)
        self.progress.pack(side="right", padx=4, pady=2)

        self.log_text = tk.Text(log_frame, height=12, wrap="word", state="disabled",
                                relief="flat", borderwidth=2, font=("Consolas", 9))
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scroll.set)
        self._apply_text_colors()

        self.add_context_menu(self.log_text)

        self.log("Готово. Заполните настройки и нажмите «Выполнить всё».")

    def apply_theme(self, root, dark):
        if dark:
            bg, panel, field = "#1e1e2e", "#313244", "#45475a"
            fg, accent, accent_active = "#cdd6f4", "#89b4fa", "#a6c8ff"
            titlebar_dark = True
        else:
            bg, panel, field = "#f2f3f5", "#e4e5ea", "#ffffff"
            fg, accent, accent_active = "#1e1e2e", "#2f6fdf", "#4a84e8"
            titlebar_dark = False
        self.cur_bg, self.cur_panel, self.cur_field = bg, panel, field
        self.cur_fg, self.cur_accent = fg, accent

        root.configure(bg=bg)
        root.after(100, lambda: self.set_dark_titlebar(titlebar_dark))

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=bg, foreground=fg, fieldbackground=field,
                        bordercolor=panel, lightcolor=panel, darkcolor=panel,
                        troughcolor=panel, selectbackground=accent, selectforeground=bg,
                        font=("Segoe UI", 9))
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=bg, foreground=fg, bordercolor=panel)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TButton", background=panel, foreground=fg, bordercolor=panel,
                        padding=(8, 4), focuscolor=panel)
        style.map("TButton", background=[("active", field), ("pressed", field)],
                  foreground=[("disabled", "#9aa0a6" if dark else "#a0a4b0")])
        style.configure("Accent.TButton", background=accent, foreground=bg,
                        font=("Segoe UI", 9, "bold"), padding=(10, 5))
        style.map("Accent.TButton", background=[("active", accent_active)])
        style.configure("TEntry", fieldbackground=field, foreground=fg,
                        bordercolor=panel, insertcolor=fg, padding=3)
        style.map("TEntry", bordercolor=[("focus", accent)])
        style.configure("TCombobox", fieldbackground=field, background=panel,
                        foreground=fg, bordercolor=panel, arrowcolor=fg, padding=3)
        style.map("TCombobox", fieldbackground=[("readonly", field)],
                  foreground=[("readonly", fg)], bordercolor=[("focus", accent)])
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.map("TCheckbutton", background=[("active", bg)], foreground=[("active", fg)])
        style.configure("Vertical.TScrollbar", background=panel, troughcolor=bg,
                        bordercolor=bg, arrowcolor=fg)
        style.map("Vertical.TScrollbar", background=[("active", field)])
        style.configure("Horizontal.TScrollbar", background=panel, troughcolor=bg,
                        bordercolor=bg, arrowcolor=fg)
        root.option_add("*TCombobox*Listbox.background", field)
        root.option_add("*TCombobox*Listbox.foreground", fg)
        root.option_add("*TCombobox*Listbox.selectBackground", accent)
        root.option_add("*TCombobox*Listbox.selectForeground", bg)
        root.option_add("*Menu.background", panel)
        root.option_add("*Menu.foreground", fg)
        root.option_add("*Menu.activeBackground", accent)
        root.option_add("*Menu.activeForeground", bg)
        if hasattr(self, "log_text") and hasattr(self, "proxy_text"):
            self._apply_text_colors()

    def _apply_text_colors(self):
        if self.is_dark:
            log_bg, log_fg = "#181825", "#a6adc8"
            field_bg, field_fg = "#45475a", "#cdd6f4"
        else:
            log_bg, log_fg = "#f6f8fa", "#24292f"
            field_bg, field_fg = "#ffffff", "#1e1e2e"
        self.log_text.configure(bg=log_bg, fg=log_fg, insertbackground=log_fg)
        self.proxy_text.configure(bg=field_bg, fg=field_fg, insertbackground=field_fg)

    def toggle_gui_theme(self):
        self.is_dark = bool(self.var_gui_dark.get())
        self.config["gui_theme"] = "dark" if self.is_dark else "light"
        self.apply_theme(self.root, self.is_dark)

    def toggle_show_password(self):
        if self.e_pass.cget("show") == "*":
            self.e_pass.config(show="")
            self.btn_show_pass.config(text="Скрыть")
        else:
            self.e_pass.config(show="*")
            self.btn_show_pass.config(text="Показать")

    # ---------- Диалоги в стиле темы ----------
    def _dialog_window(self, title):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=self.cur_bg)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_reqheight()) // 3
        win.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        return win

    def show_message(self, title, message):
        win = self._dialog_window(title)
        ttk.Label(win, text=message, wraplength=400, justify="left").pack(padx=18, pady=(16, 12))
        ttk.Button(win, text="OK", style="Accent.TButton", width=10, command=win.destroy).pack(pady=(0, 14))
        self.root.wait_window(win)

    def ask_confirm(self, title, message):
        result = {"ok": False}
        win = self._dialog_window(title)
        ttk.Label(win, text=message, wraplength=420, justify="left").pack(padx=18, pady=(16, 12))

        def yes():
            result["ok"] = True
            win.destroy()

        btns = ttk.Frame(win)
        btns.pack(pady=(0, 14))
        ttk.Button(btns, text="Да", style="Accent.TButton", width=10, command=yes).pack(side="left", padx=6)
        ttk.Button(btns, text="Отмена", width=10, command=win.destroy).pack(side="left", padx=6)
        self.root.wait_window(win)
        return result["ok"]

    # ---------- Прогресс и время ----------
    def start_progress(self):
        self._timer_running = True
        self._start_time = time.time()
        self.progress.start(10)
        self.lbl_time.config(text="Время: 0:00")
        self._update_timer()

    def _update_timer(self):
        if not self._timer_running:
            return
        el = int(time.time() - self._start_time)
        m, s = divmod(el, 60)
        self.lbl_time.config(text="Время: %d:%02d" % (m, s))
        self.root.after(1000, self._update_timer)

    def stop_progress(self):
        self._timer_running = False
        self.progress.stop()
        if hasattr(self, "_start_time"):
            el = int(time.time() - self._start_time)
            m, s = divmod(el, 60)
            self.lbl_time.config(text="Время: %d:%02d (готово)" % (m, s))

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

    def set_dark_titlebar(self, dark):
        try:
            hwnd = self.root.winfo_id()
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
        menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Выделить всё", command=lambda: widget.event_generate("<<SelectAll>>"))
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    # ---------- Лог ----------
    def on_close(self):
        try:
            self.save_config()
        except Exception:
            pass
        self.root.destroy()

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def copy_log(self):
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
                bat = os.path.join(tempfile.gettempdir(), "rm_update.bat")
                with open(bat, "w", encoding="utf-8") as f:
                    f.write(
                        '@echo off\r\n'
                        'timeout /t 2 /nobreak >nul\r\n'
                        'taskkill /F /IM RouterMaster.exe /T >nul 2>&1\r\n'
                        'taskkill /F /IM RouterMasterAdmin.exe /T >nul 2>&1\r\n'
                        'start "" /wait "%s" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-\r\n'
                        'del /f /q "%s" >nul 2>&1\r\n' % (tmp, tmp))
                subprocess.Popen(["cmd", "/c", bat],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.root.after(1000, self.root.destroy)
            except Exception as e:
                self.root.after(0, lambda: self.show_message(
                    "Ошибка", "Не удалось скачать обновление:\n%s" % e))
        self.log("Скачивание обновления...")
        threading.Thread(target=work, daemon=True).start()

    # ---------- Конфиг ----------
    def load_config(self):
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
            "После сброса откроется веб-панель — введите в ней пароль,\n"
            "который уже указан в настройках программы:\n\n"
            "%s\n\nПродолжить?" % self.var_pass.get())
        if not ok:
            return
        self.new_password = self.var_pass.get()
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
    root = tk.Tk()
    RouterToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()