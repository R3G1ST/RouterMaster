# -*- coding: utf-8 -*-
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
import paramiko
import webview

APP_VERSION = "1.5.0-beta34"
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
    "sidebar_collapsed": False,
    "auto_check_update": False,
    "font_size": "normal",
    "language": "ru",
    "download_dir": "",
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


class Api:
    def __init__(self, app):
        self._app = app
        self._window = None

    # ---------- Чтение/запись конфига ----------
    def get_config(self):
        cfg = dict(self._app.config)
        cfg["app_version"] = APP_VERSION
        return cfg

    def save_field(self, key, value):
        if key.startswith("steps."):
            self._app.config["steps"][key.split(".", 1)[1]] = value
        else:
            if key in self._app.config:
                self._app.config[key] = value
        try:
            self._app.save_config()
        except Exception:
            pass
        return True

    def save_config(self):
        try:
            self._app.save_config()
            return True
        except Exception as e:
            return str(e)

    def set_theme(self, dark):
        self._app.config["gui_theme"] = "dark" if dark else "light"
        try:
            self._app.save_config()
        except Exception:
            pass
        return True

    def reset_settings(self):
        import copy
        self._app.config = copy.deepcopy(DEFAULTS)
        self._app.save_config()
        return True

    # ---------- Действия ----------
    def run_all(self):
        self._app.run_all()
        return True

    def reboot_router(self):
        self._app.reboot_router()
        return True

    def reset_and_setup(self):
        self._app.reset_and_setup()
        return True

    def test_system(self):
        self._app.test_system()
        return True

    def remove_podkop(self):
        self._app.remove_podkop()
        return True

    def remove_zapret(self):
        self._app.remove_zapret()
        return True

    def check_update(self):
        threading.Thread(target=self._app._check_update_worker, daemon=True).start()
        return True

    def open_extra_soft(self):
        self._app.show_message("Доп. Софт",
                              "Здесь будут дополнительные программы\nдля установки на роутер.\nПока пусто — вернитесь позже.")
        return True

    def open_repo(self):
        webbrowser.open("https://github.com/%s" % UPDATE_REPO)
        return True

    def get_default_download_dir(self):
        return DOWNLOAD_DIR

    def open_download_dir(self):
        path = self._app.config.get("download_dir") or self.get_default_download_dir()
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
        os.startfile(path)
        return True

    def begin_drag(self):
        try:
            hwnd = self._window.native.Handle.ToInt32()
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            self._drag = (rect.left, rect.top)
        except Exception:
            self._drag = None
        return True

    def move_window(self, dx, dy):
        if not getattr(self, "_drag", None):
            return True
        try:
            hwnd = self._window.native.Handle.ToInt32()
            x = self._drag[0] + int(dx)
            y = self._drag[1] + int(dy)
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010)
        except Exception:
            pass
        return True

    def end_drag(self):
        self._drag = None
        return True

    def minimize_window(self):
        self._window.minimize()
        return True

    def toggle_maximize(self):
        try:
            if getattr(self, "_maximized", False):
                self._window.restore()
                self._maximized = False
            else:
                self._window.maximize()
                self._maximized = True
        except Exception:
            pass
        return True

    def close_window(self):
        self._window.destroy()
        return True

    def get_stars(self):
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/%s" % UPDATE_REPO,
                headers={"User-Agent": "RouterMaster"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8")).get("stargazers_count", 0)
        except Exception:
            return 0

    def clear_log(self):
        self._app.clear_log()
        return True

    def copy_log(self):
        return self._app.log_buf()

    def confirm_response(self, ok):
        self._app.confirm_response(bool(ok))
        return True


class RouterToolApp:
    def __init__(self, window):
        self._window = window
        self.config = self.load_config()
        self._log_buf = ""
        self._timer_running = False
        self._start_time = None
        self._confirm_event = None
        self._confirm_ok = False
        self.new_password = None

    # ---------- Связь с JS ----------
    def js(self, expr):
        try:
            self._window.evaluate_js(expr)
        except Exception:
            pass

    def log(self, msg):
        self._log_buf += msg + "\n"
        self.js("App.log(%s)" % json.dumps(msg, ensure_ascii=False))

    def log_buf(self):
        return self._log_buf

    def clear_log(self):
        self._log_buf = ""
        self.js("App.clearLog()")

    def show_message(self, title, message):
        self.js("App.msg(%s, %s)" % (json.dumps(message, ensure_ascii=False),
                                      json.dumps(title, ensure_ascii=False)))

    def ask_confirm(self, title, message):
        self.js("App.confirm(%s, %s)" % (json.dumps(message, ensure_ascii=False),
                                         json.dumps(title, ensure_ascii=False)))
        self._confirm_event = threading.Event()
        self._confirm_ok = False
        self._confirm_event.wait(300)
        return self._confirm_ok

    def confirm_response(self, ok):
        self._confirm_ok = ok
        if self._confirm_event:
            self._confirm_event.set()

    def set_running(self, on):
        self.js("App.setRunning(%s)" % ("true" if on else "false"))

    def set_progress(self, on):
        self.js("App.setProgress(%s)" % ("true" if on else "false"))

    def open_log(self):
        self.js("App.openLog()")

    # ---------- Прогресс и время ----------
    def start_progress(self):
        self._timer_running = True
        self._start_time = time.time()
        self.set_progress(True)
        self.set_time("0:00")
        threading.Thread(target=self._timer_loop, daemon=True).start()

    def _timer_loop(self):
        while self._timer_running:
            el = int(time.time() - self._start_time)
            m, s = divmod(el, 60)
            self.set_time("%d:%02d" % (m, s))
            time.sleep(1)

    def set_time(self, text):
        self.js("App.setTime(%s)" % json.dumps(text, ensure_ascii=False))

    def stop_progress(self):
        self._timer_running = False
        self.set_progress(False)
        if self._start_time:
            el = int(time.time() - self._start_time)
            m, s = divmod(el, 60)
            self.set_time("%d:%02d (готово)" % (m, s))

    # ---------- Обновление ----------
    def _ver_tuple(self, v):
        v = str(v).lstrip("v")
        base, _, pre = v.partition("-")
        t = [int(x) for x in re.findall(r"\d+", base)][:3]
        t = (t + [0, 0, 0])[:3]
        if pre:
            m = re.search(r"(\d+)", pre)
            return tuple(t) + (-1, int(m.group(1)) if m else 0)
        return tuple(t) + (0, 0)

    def _check_update_worker(self):
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/%s/releases?per_page=10" % UPDATE_REPO,
                headers={"User-Agent": "RouterMaster"})
            with urllib.request.urlopen(req, timeout=15) as r:
                releases = json.loads(r.read().decode("utf-8"))
            candidates = []
            for rel in releases:
                tag = str(rel.get("tag_name", "v0.0.0")).lstrip("v")
                candidates.append((self._ver_tuple(tag), tag, rel))
            if not candidates:
                raise RuntimeError("релизы не найдены")
            best = max(candidates, key=lambda c: c[0])
            if best[0] > self._ver_tuple(APP_VERSION):
                self._prompt_update(best[2], best[1])
            else:
                self.show_message("Обновление", "Установлена последняя версия %s" % APP_VERSION)
        except Exception as e:
            self.show_message("Ошибка", "Не удалось проверить обновление:\n%s" % e)

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
                with urllib.request.urlopen(req, timeout=180) as r:
                    total = int(r.headers.get("Content-Length") or 0)
                    done = 0
                    last_pct = -1
                    start_time = time.time()
                    with open(tmp, "wb") as f:
                        while True:
                            chunk = r.read(262144)
                            if not chunk:
                                break
                            f.write(chunk)
                            done += len(chunk)
                            if total:
                                pct = int(done * 100 / total)
                                if pct >= last_pct + 5:
                                    last_pct = pct
                                    elapsed = time.time() - start_time
                                    speed = done / elapsed / 1048576 if elapsed > 0 else 0
                                    self.log("Скачивание: %d%% (%d МБ из %d МБ) — %.1f МБ/с" % (
                                        pct, done // 1048576, total // 1048576, speed))
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
                self.log("Установка выполняется. Программа закроется и перезапустится автоматически.")
                time.sleep(1)
                try:
                    self._window.destroy()
                except Exception:
                    pass
            except Exception as e:
                self.log("ОШИБКА обновления: " + str(e))
                self.stop_progress()
                self.show_message("Ошибка", "Не удалось скачать обновление:\n%s" % e)
        self.clear_log()
        self.open_log()
        self.start_progress()
        self.log("Скачивание обновления %s ..." % name)
        threading.Thread(target=work, daemon=True).start()

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
                cfg.setdefault("steps", {})
                for k, v in DEFAULTS["steps"].items():
                    cfg["steps"].setdefault(k, v)
                if cfg.get("app_version") != APP_VERSION:
                    cfg["app_version"] = APP_VERSION
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                return cfg
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULTS))

    def save_config(self):
        cfg = dict(self.config)
        try:
            cfg["port"] = int(cfg.get("port") or 22)
        except Exception:
            cfg["port"] = 22
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    # ---------- SSH ----------
    def _conn_info(self):
        return (str(self.config.get("host", "")).strip(),
                int(self.config.get("port") or 22),
                str(self.config.get("user", "root")).strip(),
                str(self.config.get("password", "")))

    def _connect_ssh(self):
        host, port, user, password = self._conn_info()
        self.log("=== Подключение к %s:%s ... ===" % (host, port))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password,
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log("Подключено.")
        return client

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
        if not self.config.get("host") or not self.config.get("password"):
            self.show_message("Внимание", "Укажите IP роутера и пароль SSH!")
            return
        need_key = (
            (self.config["steps"].get("setup_wifi") and ENC_LABELS.get(self.config.get("wifi_enc_5g"), "sae") != "none")
            or (self.config["steps"].get("setup_wifi_2g") and ENC_LABELS.get(self.config.get("wifi_enc_2g"), "psk2") != "none")
        )
        if need_key and len(self.config.get("wifi_password", "")) < 8:
            self.show_message("Внимание", "Пароль Wi-Fi должен быть не короче 8 символов!")
            return
        self.open_log()
        self.set_running(True)
        threading.Thread(target=self.worker, daemon=True).start()

    def reboot_router(self):
        def work():
            try:
                host, port, user, password = self._conn_info()
                self.open_log()
                self.start_progress()
                self.log("=== Перезагрузка роутера... ===")
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, port=port, username=user, password=password,
                               timeout=15, look_for_keys=False, allow_agent=False)
                self.ssh_exec(client, "sleep 2; reboot", timeout=30)
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
                    self.show_message("Готово",
                                      "Роутер перезагрузился и снова в сети.\n\n"
                                      "Обновите страницу в браузере (Ctrl+F5),\n"
                                      "чтобы увидеть новый интерфейс: http://%s" % host)
                else:
                    self.log("Роутер не вернулся в сеть за 5 минут — проверьте питание.")
            except Exception as e:
                self.log("ОШИБКА: " + str(e))
                self.show_message("Ошибка", str(e))
            finally:
                self.stop_progress()
                self.open_log()
        threading.Thread(target=work, daemon=True).start()

    def worker(self):
        self.start_progress()
        try:
            self.run_steps()
            self._window.evaluate_js("App.showRebootConfirm()")
        except Exception as e:
            self.log("ОШИБКА: " + str(e))
            self.show_message("Ошибка", str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log("Завершено.")

    def run_steps(self):
        host, port, user, password = self._conn_info()

        self.log("=== Подключение к %s:%s ... ===" % (host, port))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password,
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log("Подключено.")

        hostname = "RouterMaster"
        self.log("--- Имя хоста: %s ---" % hostname)
        self.ssh_exec(client,
                      "uci set system.@system[0].hostname='%s'; uci commit system; /etc/init.d/system reload"
                      % hostname)

        steps = self.config["steps"]

        if steps.get("update_packages"):
            self.log("--- Обновление пакетов ---")
            self.ssh_exec(client, "apk update")
            out, _ = self.ssh_exec(client, "apk upgrade")
            if "error" in out.lower():
                self.ssh_exec(client, "apk upgrade")
                self.log("Повторный apk upgrade выполнен.")

        if steps.get("install_podkop"):
            self.log("--- Podkop: установка/обновление ---")
            self.ssh_exec(client, "wget -qO /tmp/podkop_install.sh https://raw.githubusercontent.com/itdoginfo/podkop/refs/heads/main/install.sh")
            self.ssh_exec(client, "printf 'y\\ny\\ny\\ny\\ny\\n' | sh /tmp/podkop_install.sh", timeout=600)
            self.ssh_exec(client, "uci delete podkop.@section[0].community_lists 2>/dev/null; for s in %s; do uci add_list podkop.@section[0].community_lists=\"$s\"; done; uci commit podkop" % PODKOP_COMMUNITY_LISTS)
            self.ssh_exec(client, "/etc/init.d/podkop enable; /etc/init.d/podkop start", timeout=60)

        if steps.get("install_zapret"):
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

        if steps.get("install_argon"):
            theme_name = self.config.get("theme") or "Argon"
            theme = THEMES.get(theme_name, THEMES["Argon"])
            self.log("--- Тема: %s ---" % theme_name)
            if "url" in theme:
                exists, _ = self.ssh_exec(client, "apk info 2>/dev/null | grep -c '^%s$'" % theme["pkg"])
                if exists.strip() == "0":
                    self.install_theme_file(client, theme)
            else:
                self.ssh_exec(client, "apk add " + theme["pkg"], timeout=300)
            self.ssh_exec(client, "uci set luci.main.mediaurlbase='%s'; uci commit luci" % theme["media"])

        if steps.get("install_ru"):
            self.log("--- Русский язык ---")
            self.ssh_exec(client, "apk add luci-i18n-base-ru", timeout=300)
            self.ssh_exec(client, "uci set luci.main.lang=ru; uci commit luci")

        if steps.get("setup_wifi") or steps.get("setup_wifi_2g"):
            self.log("--- Wi-Fi ---")
            wp = self.config.get("wifi_password", "")
            chan = str(self.config.get("wifi_channel", "")).strip() or "36"
            parts = []
            if steps.get("setup_wifi"):
                ssid = str(self.config.get("wifi_ssid", "")).strip()
                enc5 = ENC_LABELS.get(self.config.get("wifi_enc_5g"), "sae")
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
            if steps.get("setup_wifi_2g"):
                ssid2 = str(self.config.get("wifi_ssid_2g", "")).strip() or "OpenWrt 2G"
                enc2 = ENC_LABELS.get(self.config.get("wifi_enc_2g"), "psk2")
                chan2 = str(self.config.get("wifi_channel_2g", "")).strip() or "auto"
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

        if steps.get("setup_proxy"):
            proxy = str(self.config.get("proxy_string", "")).strip()
            if proxy:
                self.log("--- Прокси для Podkop ---")
                self.ssh_exec(client,
                              "uci set podkop.@section[0].proxy_string='%s'; uci commit podkop; "
                              "/etc/init.d/podkop restart" % proxy.replace("'", ""))
            else:
                self.log("Прокси не задан — пропускаю.")

        if steps.get("update_os"):
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

        client.close()
        self.log("=== Установка завершена ===")

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

    # ---------- Удаление сервисов ----------
    def remove_podkop(self):
        if not self.config.get("host") or not self.config.get("password"):
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
        self.open_log()
        self.set_running(True)
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
            self.show_message("Ошибка", str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log("Удаление завершено.")

    def remove_zapret(self):
        if not self.config.get("host") or not self.config.get("password"):
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
        self.open_log()
        self.set_running(True)
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
            self.show_message("Ошибка", str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log("Удаление завершено.")

    # ---------- Сброс + настройка ----------
    def reset_and_setup(self):
        if not self.config.get("host") or not self.config.get("password"):
            self.show_message("Внимание", "Укажите IP роутера и пароль SSH!")
            return
        password = self.config.get("password", "")
        ok = self.ask_confirm(
            "Сброс роутера",
            "ВНИМАНИЕ! Все настройки роутера будут сброшены к заводским:\n"
            "- удалятся пароли, Wi-Fi, Podkop, тема, пакеты\n\n"
            "После сброса роутер перезагрузится,\n"
            "затем пароль %s будет установлен автоматически,\n"
            "и автоматически выполнится полная настройка:\n"
            "Wi-Fi 2.4/5 ГГц, Podkop, тема, язык.\n\n"
            "Обычно это занимает 3-4 минуты, редко дольше.\n\n"
            "Продолжить?" % password)
        if not ok:
            return
        self.new_password = password
        self.open_log()
        self.set_running(True)
        threading.Thread(target=self.reset_worker, daemon=True).start()

    def reset_worker(self):
        self.start_progress()
        try:
            self.do_reset_and_setup()
        except Exception as e:
            self.log("ОШИБКА: " + str(e))
            self.show_message("Ошибка", str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log("Завершено.")

    def do_reset_and_setup(self):
        host, port, user, _ = self._conn_info()

        self.log("=== Сброс к заводским настройкам ===")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=self.config.get("password"),
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
        self.config["password"] = self.new_password
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

    # ---------- Тест системы и подключения ----------
    def test_system(self):
        if not self.config.get("host") or not self.config.get("password"):
            self.show_message("Внимание", "Укажите IP роутера и пароль SSH!")
            return
        self.open_log()
        self.clear_log()
        self.set_running(True)
        threading.Thread(target=self.test_worker, daemon=True).start()

    def test_worker(self):
        import socket
        import platform
        ok = True

        def check(cond, good, bad):
            nonlocal ok
            if cond:
                self.log("[OK] " + good)
            else:
                ok = False
                self.log("[ОШИБКА] " + bad)

        self.start_progress()
        try:
            self.log("=== Тест системы и подключения ===")
            host, port, _, _ = self._conn_info()

            self.log("--- Ваша система ---")
            self.log("ОС: %s" % platform.platform())
            self.log("Python: %s" % sys.version.split()[0])
            check(sys.version_info >= (3, 8), "Версия Python поддерживается", "Python слишком старый")

            self.log("--- Связь с роутером %s:%s ---" % (host, port))
            try:
                s = socket.create_connection((host, port), timeout=5)
                s.close()
                self.log("[OK] Порт %s доступен по сети" % port)
            except Exception:
                ok = False
                self.log("[ОШИБКА] Роутер недоступен по адресу %s:%s" % (host, port))
                self.log("Проверьте кабель, что роутер включён и IP указан верно.")
                raise SystemExit

            client = self._connect_ssh()
            check(True, "SSH-подключение установлено", "")

            self.log("--- Система роутера ---")
            out, _ = self.ssh_exec(client, "uname -a")
            check(bool(out.strip()), "Ядро: " + out.strip()[:90], "Не удалось получить информацию о ядре")

            out, _ = self.ssh_exec(client, "cat /etc/openwrt_release 2>/dev/null | head -2 || cat /etc/os-release | head -2")
            check(bool(out.strip()), "ПО роутера: " + " ".join(out.split())[:100], "Не удалось определить прошивку")

            out, _ = self.ssh_exec(client, "cat /proc/meminfo | head -2")
            check(bool(out.strip()), "Память: " + " ".join(out.split())[:80], "Не удалось прочитать память")

            out, _ = self.ssh_exec(client, "df -h / | tail -1")
            check(bool(out.strip()), "Диск: " + " ".join(out.split())[:80], "Не удалось прочитать диск")

            self.log("--- Интернет на роутере ---")
            out, _ = self.ssh_exec(client, "ping -c 2 -W 2 8.8.8.8 2>&1 | tail -2")
            check("0% packet loss" in out or "2 received" in out,
                  "Интернет работает: " + " ".join(out.split())[:80],
                  "Роутер не имеет доступа в интернет")

            self.log("--- Службы ---")
            out, _ = self.ssh_exec(client, "uci get network.lan.ipaddr 2>/dev/null || ip -4 addr show br-lan 2>/dev/null | grep inet")
            check(bool(out.strip()), "IP роутера: " + " ".join(out.split())[:60], "Не удалось определить IP роутера")

            self.log("")
            if ok:
                self.log("=== ИТОГ: все проверки пройдены. Роутер готов к настройке. ===")
            else:
                self.log("=== ИТОГ: обнаружены проблемы (см. выше) ===")
        except SystemExit:
            pass
        except Exception as e:
            ok = False
            self.log("ОШИБКА: " + str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            if ok:
                self.log("Завершено. Подключение удачное.")
                self.show_message("Тест завершён", "Система и подключение в порядке!\nРоутер готов к настройке.")
            else:
                self.log("Завершено. Подключение НЕ удалось или есть проблемы.")
                self.show_message("Тест завершён", "Обнаружены проблемы.\nПодробности — в логе.")


def _find_html():
    for base in (getattr(sys, "_MEIPASS", None), APP_DIR):
        if not base:
            continue
        p = os.path.join(base, "assets", "ui", "index.html")
        if os.path.exists(p):
            return p
    return os.path.join(APP_DIR, "assets", "ui", "index.html")


def _find_icon():
    for base in (getattr(sys, "_MEIPASS", None), APP_DIR):
        if not base:
            continue
        p = os.path.join(base, "assets", "icon.ico")
        if os.path.exists(p):
            return p
    return None


def main():
    html = _find_html()
    api = Api(None)
    window = webview.create_window(
        "RouterMaster",
        url=html,
        width=1200,
        height=760,
        min_size=(960, 640),
        background_color="#05070d",
        frameless=True,
        easy_drag=False,
        shadow=False,
        js_api=api,
    )
    app = RouterToolApp(window)
    api._app = app
    api._window = window

    def on_loaded():
        if app.config.get("auto_check_update"):
            threading.Thread(target=app._check_update_worker, daemon=True).start()
        app.log("Готово. Заполните настройки и нажмите «ВЫПОЛНИТЬ».")

    window.events.loaded += on_loaded
    window.events.closing += lambda: app.save_config()

    webview.start(icon=_find_icon())
    return app


if __name__ == "__main__":
    main()