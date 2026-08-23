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

APP_VERSION = "1.5.1"
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

LOG_I18N = {
    "ru": {
        "connecting": "=== Подключение к %s:%s ... ===",
        "connected": "Подключено.",
        "conn_err": "Ошибка подключения: %s",
        "ssh_err": "SSH ошибка: %s",
        "timeout_err": "Таймаут: %s",
        "running": "--- Выполняю: %s ---",
        "done": "--- Готово: %s ---",
        "skip": "--- Пропускаю: %s (уже выполнено) ---",
        "fail": "--- Ошибка: %s ---",
        "downloading": "Скачивание обновления %s ...",
        "ps_downloading": "Запускаю скачивание через PowerShell...",
        "download_ok": "Обновление скачано: %.1f МБ",
        "download_err": "Ошибка скачивания: %s",
        "download_fail": "Не удалось скачать: %s",
        "unblock": "Снимаю блокировку SmartScreen (Mark of the Web)...",
        "installing": "Запускаю тихую установку (без окон)...",
        "install_msg": "Установка выполняется. Программа закроется и перезапустится автоматически.",
        "testing": "=== Тест системы и подключения ===",
        "test_ok": "Всё в порядке.",
        "test_fail": "Проблема: %s",
        "checking_update": "Проверяю обновления...",
        "update_latest": "Установлена последняя версия %s",
        "update_err": "Не удалось проверить обновление:\n%s",
        "update_avail": "Доступна новая версия %s!\nТекущая: %s\nСкачать и установить?",
        "update_notfound": "Установщик не найден в релизе.",
        "theme_ok": "Тема %s установлена.",
        "theme_err": "Ошибка установки темы: %s",
        "reset_ok": "Настройки сброшены.",
        "reset_err": "Ошибка сброса: %s",
        "podkop_rm": "Удаление Podkop...",
        "zapret_rm": "Удаление Zapret...",
        "opkg_update": "Обновление списка пакетов (opkg update)...",
        "opkg_err": "opkg update: ошибки:\n%s",
        "rebooting": "Перезагрузка роутера...",
        "reboot_wait": "Ожидание возврата (%d сек)...",
        "reboot_ok": "Роутер перезагружен.",
        "file_bad": "Файл скачан некорректно",
        "update_error": "ОШИБКА обновления: %s",
        "uploading": "Заливаю %s на роутер...",
        "reboot_timeout": "Роутер не вернулся в сеть за 5 минут — проверьте питание.",
        "error": "ОШИБКА: %s",
        "completed": "Завершено.",
        "apk_retry": "Повторный apk upgrade выполнен.",
        "no_proxy": "Прокси не задан — пропускаю.",
        "os_update_found": "Найдено обновление ОС: %s",
        "os_update_started": "Обновление запущено. Роутер перезагрузится. Подождите 2-5 минут, "
                             "затем подключитесь к Wi-Fi и откройте программу заново.",
        "os_update_cancelled": "Обновление ОС отменено пользователем.",
        "os_up_to_date": "ОС актуальна — обновлений нет",
        "remove_done": "Удаление завершено.",
        "conn_reset": "Соединение прервано — роутер сбрасывается.",
        "open_web": "Открываю веб-панель: %s",
        "wait_boot": "Ожидаю загрузки роутера...",
        "pass_set": "Пароль установлен автоматически!",
        "pass_fail": "Автоустановка пароля не прошла — установите пароль %s в веб-панели вручную.",
        "wait_ssh": "Ожидаю SSH...",
        "ssh_new_pass": "Роутер доступен с новым паролем! Устанавливаю всё...",
        "os_info": "ОС: %s",
        "check_cable": "Проверьте кабель, что роутер включён и IP указан верно.",
        "test_ok_conn": "Завершено. Подключение удачное.",
        "test_fail_conn": "Завершено. Подключение НЕ удалось или есть проблемы.",
        "wait_router": "  ожидание роутера...",
        "wait_ssh_dot": "  ожидание SSH...",
        "host_name": "--- Имя хоста: %s ---",
        "pkg_update": "--- Обновление пакетов ---",
        "podkop_install": "--- Podkop: установка/обновление ---",
        "zapret_install": "--- Zapret-Manager + Zapret (быстрый старт) ---",
        "theme_install": "--- Тема: %s ---",
        "lang_install": "--- Русский язык ---",
        "wifi_setup": "--- Wi-Fi ---",
        "wifi_5g": "Wi-Fi 5G: SSID '%s', канал %s, шифрование %s",
        "wifi_2g": "Wi-Fi 2G: SSID '%s', канал %s, шифрование %s",
        "proxy_setup": "--- Прокси для Podkop ---",
        "os_check": "--- Проверка версии ОС ---",
        "os_version_line": "Версия ОС: %s",
        "setup_done": "=== Установка завершена ===",
        "theme_dl": "%s: скачивание apk на ПК...",
        "theme_dl_done": "  скачано: %s байт (папка программы: %s)",
        "podkop_rm_done": "Podkop успешно удалён с роутера.",
        "zapret_rm_done": "Zapret успешно удалён с роутера.",
        "podkop_rm_header": "--- Podkop: удаление ---",
        "zapret_rm_header": "--- Zapret: удаление ---",
        "reset_header": "=== Сброс к заводским настройкам ===",
        "reset_exec": "Выполняю сброс (как кнопка Perform reset в LuCI)...",
        "luci_wait": "LuCI не поднялась за 10 минут — проверьте роутер.",
        "luci_ready": "LuCI доступна — устанавливаю пароль автоматически...",
        "ssh_wait_fail": "Не удалось подключиться после сброса за 15 минут. Проверьте пароль в веб-панели.",
        "test_system_header": "--- Ваша система ---",
        "test_router_header": "--- Связь с роутером %s:%s ---",
        "port_ok": "Порт %s доступен по сети",
        "port_fail": "Роутер недоступен по адресу %s:%s",
        "test_router_system": "--- Система роутера ---",
        "test_inet": "--- Интернет на роутере ---",
        "inet_ok": "Интернет работает: %s",
        "inet_fail": "Роутер не имеет доступа в интернет",
        "test_services": "--- Службы ---",
        "ip_info": "IP роутера: %s",
        "ip_fail": "Не удалось определить IP роутера",
        "test_result_ok": "=== ИТОГ: все проверки пройдены. Роутер готов к настройке. ===",
        "test_result_fail": "=== ИТОГ: обнаружены проблемы (см. выше) ===",
        "test_good_msg": "Система и подключение в порядке!\nРоутер готов к настройке.",
        "test_bad_msg": "Обнаружены проблемы.\nПодробности — в логе.",
        "init_done": "Готово. Заполните настройки и нажмите «ВЫПОЛНИТЬ».",
        "ok": "[ОК] %s",
        "check_fail": "[ОШИБКА] %s",
        "kernel": "Ядро: %s",
        "kernel_fail": "Не удалось получить информацию о ядре",
        "firmware": "ПО роутера: %s",
        "firmware_fail": "Не удалось определить прошивку",
        "memory": "Память: %s",
        "memory_fail": "Не удалось прочитать память",
        "disk": "Диск: %s",
        "disk_fail": "Не удалось прочитать диск",
        "inet_works": "Интернет работает: %s",
        "inet_no": "Роутер не имеет доступа в интернет",
        "ip_router": "IP роутера: %s",
        "ssh_ok": "SSH-подключение установлено",
        "python_ok": "Версия Python поддерживается",
        "python_bad": "Python слишком старый",
        "test_finished": "Завершено. Подключение удачное.",
        "test_finished_bad": "Завершено. Подключение не удалось или есть проблемы.",
        "attention": "Внимание",
        "enter_ip_pass": "Укажите IP роутера и пароль SSH!",
        "test_complete": "Тест завершён",
        "uploaded": "  загружено: %s",
        "wait_router": "  ожидание роутера...",
        "lang_ru": "Русский язык",
        "upd_done": "Обновление выполнено. Роутер перезагрузится. Подождите 2-5 мин, подключитесь к Wi-Fi заново, откройте программу.",
        "downloaded": "  загружено: %s",
        "msg_update": "Обновление",
        "msg_error": "Ошибка",
        "msg_done": "Готово",
        "latest_ver": "Установлена последняя версия %s",
        "check_update_err": "Не удалось проверить обновление:\n%s",
        "installer_not_found": "Установщик не найден в релизе.",
        "dl_err": "Не удалось скачать обновление:\n%s",
        "wifi_short": "Пароль Wi-Fi должен быть не короче 8 символов!",
        "extra_soft": "Доп. Софт",
        "extra_soft_msg": "Здесь будут дополнительные программы\nдля установки на роутер.\nПока пусто — вернитесь позже.",
        "update_avail": "Доступна новая версия %s!\n\nТекущая версия: %s\n\nСкачать установщик и установить сейчас?",
        "upd_error": "неизвестно",
        "os_update": "Обновление ОС",
        "os_update_msg": "Обновление ОС: %s. Перезагрузка. Подождите 2-5 мин.",
        "os_update_confirm": "Найдено обновление ОС: %s\n\nОбновить? Роутер перезагрузится. SSH прервётся на 2-5 мин.",
        "remove_podkop": "Удаление Podkop",
        "remove_podkop_msg": "Удалить Podkop с роутера?\n\n"
                             "Будут остановлены и удалены:\n"
                             "- сервис /etc/init.d/podkop\n"
                             "- конфигурация uci podkop и файл /etc/config/podkop\n"
                             "- пакеты podkop, luci-app-podkop, luci-i18n-podkop-ru",
        "remove_zapret": "Удаление Zapret",
        "remove_zapret_msg": "Удалить Zapret и Zapret-Manager с роутера?\n\n"
                             "Будут остановлены и удалены:\n"
                             "- сервис /etc/init.d/zapret\n"
                             "- файлы /etc/zapret, /opt/zapret\n"
                             "- утилиты zms / zmsA\n"
                             "- конфигурация uci zapret",
        "reboot_done_msg": "Роутер перезагрузился и снова в сети.\n\n"
                           "Обновите страницу в браузере (Ctrl+F5),\n"
                           "чтобы увидеть новый интерфейс: http://%s",
    },
    "en": {
        "connecting": "=== Connecting to %s:%s ... ===",
        "connected": "Connected.",
        "conn_err": "Connection error: %s",
        "ssh_err": "SSH error: %s",
        "timeout_err": "Timeout: %s",
        "running": "--- Running: %s ---",
        "done": "--- Done: %s ---",
        "skip": "--- Skipped: %s (already done) ---",
        "fail": "--- Failed: %s ---",
        "downloading": "Downloading update %s ...",
        "ps_downloading": "Starting download via PowerShell...",
        "download_ok": "Update downloaded: %.1f MB",
        "download_err": "Download error: %s",
        "download_fail": "Download failed: %s",
        "unblock": "Removing SmartScreen block (Mark of the Web)...",
        "installing": "Starting silent installation...",
        "install_msg": "Installation in progress. Program will close and restart automatically.",
        "testing": "=== System & connection test ===",
        "test_ok": "Everything OK.",
        "test_fail": "Problem: %s",
        "checking_update": "Checking for updates...",
        "update_latest": "Latest version %s is installed",
        "update_err": "Failed to check for update:\n%s",
        "update_avail": "New version %s available!\nCurrent: %s\nDownload and install?",
        "update_notfound": "Installer not found in release.",
        "theme_ok": "Theme %s installed.",
        "theme_err": "Theme install error: %s",
        "reset_ok": "Settings reset.",
        "reset_err": "Reset error: %s",
        "podkop_rm": "Removing Podkop...",
        "zapret_rm": "Removing Zapret...",
        "opkg_update": "Updating package list (opkg update)...",
        "opkg_err": "opkg update errors:\n%s",
        "rebooting": "Rebooting router...",
        "reboot_wait": "Waiting for return (%d sec)...",
        "reboot_ok": "Router rebooted.",
        "file_bad": "File downloaded incorrectly",
        "update_error": "UPDATE ERROR: %s",
        "uploading": "Uploading %s to router...",
        "reboot_timeout": "Router did not return in 5 minutes — check power.",
        "error": "ERROR: %s",
        "completed": "Completed.",
        "apk_retry": "Retry apk upgrade done.",
        "no_proxy": "No proxy set — skipping.",
        "os_update_found": "OS update found: %s",
        "os_update_started": "Update started. Router will reboot. Wait 2-5 minutes, "
                             "then connect to Wi-Fi and reopen the program.",
        "os_update_cancelled": "OS update cancelled by user.",
        "os_up_to_date": "OS is up to date",
        "remove_done": "Removal complete.",
        "conn_reset": "Connection interrupted — router is resetting.",
        "open_web": "Opening web panel: %s",
        "wait_boot": "Waiting for router to boot...",
        "pass_set": "Password set automatically!",
        "pass_fail": "Auto password setup failed — set password %s in web panel manually.",
        "wait_ssh": "Waiting for SSH...",
        "ssh_new_pass": "Router accessible with new password! Installing everything...",
        "os_info": "OS: %s",
        "check_cable": "Check cable, router is on and IP is correct.",
        "test_ok_conn": "Done. Connection successful.",
        "test_fail_conn": "Done. Connection FAILED or there are issues.",
        "wait_router": "  waiting for router...",
        "wait_ssh_dot": "  waiting for SSH...",
        "host_name": "--- Host name: %s ---",
        "pkg_update": "--- Updating packages ---",
        "podkop_install": "--- Podkop: install/update ---",
        "zapret_install": "--- Zapret-Manager + Zapret (quick start) ---",
        "theme_install": "--- Theme: %s ---",
        "lang_install": "--- Russian language ---",
        "wifi_setup": "--- Wi-Fi ---",
        "wifi_5g": "Wi-Fi 5G: SSID '%s', channel %s, encryption %s",
        "wifi_2g": "Wi-Fi 2G: SSID '%s', channel %s, encryption %s",
        "proxy_setup": "--- Proxy for Podkop ---",
        "os_check": "--- Checking OS version ---",
        "os_version_line": "OS version: %s",
        "setup_done": "=== Setup complete ===",
        "theme_dl": "%s: downloading apk to PC...",
        "theme_dl_done": "  downloaded: %s bytes (program folder: %s)",
        "podkop_rm_done": "Podkop successfully removed from router.",
        "zapret_rm_done": "Zapret successfully removed from router.",
        "podkop_rm_header": "--- Podkop: removal ---",
        "zapret_rm_header": "--- Zapret: removal ---",
        "reset_header": "=== Factory reset ===",
        "reset_exec": "Performing reset (like LuCI Perform reset button)...",
        "luci_wait": "LuCI did not start in 10 minutes — check router.",
        "luci_ready": "LuCI is available — setting password automatically...",
        "ssh_wait_fail": "Could not connect after reset in 15 minutes. Check password in web panel.",
        "test_system_header": "--- Your system ---",
        "test_router_header": "--- Router connection %s:%s ---",
        "port_ok": "Port %s is reachable",
        "port_fail": "Router unreachable at %s:%s",
        "test_router_system": "--- Router system ---",
        "test_inet": "--- Internet on router ---",
        "inet_ok": "Internet works: %s",
        "inet_fail": "Router has no internet access",
        "test_services": "--- Services ---",
        "ip_info": "Router IP: %s",
        "ip_fail": "Could not determine router IP",
        "test_result_ok": "=== RESULT: all checks passed. Router ready for setup. ===",
        "test_result_fail": "=== RESULT: issues found (see above) ===",
        "test_good_msg": "System and connection OK!\nRouter ready for setup.",
        "test_bad_msg": "Issues found.\nSee log for details.",
        "init_done": "Done. Fill in settings and press «RUN».",
        "ok": "[OK] %s",
        "check_fail": "[ERROR] %s",
        "kernel": "Kernel: %s",
        "kernel_fail": "Could not get kernel info",
        "firmware": "Router firmware: %s",
        "firmware_fail": "Could not determine firmware",
        "memory": "Memory: %s",
        "memory_fail": "Could not read memory",
        "disk": "Disk: %s",
        "disk_fail": "Could not read disk",
        "inet_works": "Internet works: %s",
        "inet_no": "Router has no internet access",
        "ip_router": "Router IP: %s",
        "ssh_ok": "SSH connection established",
        "python_ok": "Python version supported",
        "python_bad": "Python too old",
        "test_finished": "Done. Connection successful.",
        "test_finished_bad": "Done. Connection FAILED or there are issues.",
        "attention": "Attention",
        "enter_ip_pass": "Enter router IP and SSH password!",
        "test_complete": "Test complete",
        "uploaded": "  uploaded: %s",
        "wait_router": "  waiting for router...",
        "lang_ru": "Russian language",
        "upd_done": "Update done. Router will reboot. Wait 2-5 min, reconnect Wi-Fi, reopen program.",
        "downloaded": "  downloaded: %s",
        "msg_update": "Update",
        "msg_error": "Error",
        "msg_done": "Done",
        "latest_ver": "Latest version %s is installed",
        "check_update_err": "Failed to check for update:\n%s",
        "installer_not_found": "Installer not found in release.",
        "dl_err": "Failed to download update:\n%s",
        "wifi_short": "Wi-Fi password must be at least 8 characters!",
        "extra_soft": "Extra Software",
        "extra_soft_msg": "Additional programs for the router will be here.\nCurrently empty — check back later.",
        "update_avail": "New version %s is available!\n\nCurrent version: %s\n\nDownload installer and install now?",
        "upd_error": "unknown",
        "os_update": "OS Update",
        "os_update_msg": "OS update: %s. Rebooting. Wait 2-5 min.",
        "os_update_confirm": "OS update found: %s\n\nUpdate? Router will reboot. SSH will disconnect for 2-5 min.",
        "remove_podkop": "Remove Podkop",
        "remove_podkop_msg": "Remove Podkop from router?\n\n"
                             "The following will be stopped and removed:\n"
                             "- service /etc/init.d/podkop\n"
                             "- uci configuration podkop and file /etc/config/podkop\n"
                             "- packages podkop, luci-app-podkop, luci-i18n-podkop-ru",
        "remove_zapret": "Remove Zapret",
        "remove_zapret_msg": "Remove Zapret and Zapret-Manager from router?\n\n"
                             "The following will be stopped and removed:\n"
                             "- service /etc/init.d/zapret\n"
                             "- files /etc/zapret, /opt/zapret\n"
                             "- utilities zms / zmsA\n"
                             "- uci configuration zapret",
        "reboot_done_msg": "Router rebooted and is back online.\n\n"
                           "Refresh the page in your browser (Ctrl+F5)\n"
                           "to see the new interface: http://%s",
    },
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
    "gui_theme": "dark",
    "sidebar_collapsed": False,
    "auto_check_update": False,
    "allow_beta": False,
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
        self._app.show_message(self.lt("extra_soft"),
                              self.lt("extra_soft_msg"))
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

    def lt(self, key, *args):
        lang = self.config.get("language", "ru")
        s = LOG_I18N.get(lang, LOG_I18N["ru"]).get(key, key)
        return s % args if args else s

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
            allow_beta = self.config.get("allow_beta", False)
            for rel in releases:
                tag = str(rel.get("tag_name", "v0.0.0")).lstrip("v")
                is_prerelease = rel.get("prerelease", False)
                if is_prerelease and not allow_beta:
                    continue
                candidates.append((self._ver_tuple(tag), tag, rel))
            if not candidates:
                raise RuntimeError("релизы не найдены")
            best = max(candidates, key=lambda c: c[0])
            if best[0] > self._ver_tuple(APP_VERSION):
                self._prompt_update(best[2], best[1])
            else:
                self.show_message(self.lt("msg_update"), self.lt("latest_ver") % APP_VERSION)
        except Exception as e:
            self.show_message(self.lt("msg_error"), self.lt("check_update_err") % e)

    def _prompt_update(self, data, latest_tag):
        if not self.ask_confirm(
                self.lt("msg_update"),
                self.lt("update_avail") % (latest_tag, APP_VERSION)):
            return
        for a in data.get("assets", []):
            if a.get("name", "").lower() == UPDATE_ASSET.lower():
                self._download_and_install(a["browser_download_url"], a["name"])
                return
        self.show_message(self.lt("msg_update"), self.lt("installer_not_found"))

    def _unblock_file(self, path):
        try:
            return bool(ctypes.windll.kernel32.DeleteFileW(path + ":Zone.Identifier"))
        except Exception:
            return False

    def _download_and_install(self, url, name):
        def work():
            try:
                tmp = os.path.join(tempfile.gettempdir(), name)
                self.log(self.lt("downloading", name))

                ps_script = (
                    "$ProgressPreference = 'SilentlyContinue'\n"
                    "$url = '%s'\n"
                    "$out = '%s'\n"
                    "try {\n"
                    "  $r = Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing\n"
                    "  exit 0\n"
                    "} catch {\n"
                    "  Write-Host $_.Exception.Message\n"
                    "  exit 1\n"
                    "}\n"
                ) % (url, tmp.replace("\\", "\\\\"))

                ps_path = os.path.join(tempfile.gettempdir(), "rm_download.ps1")
                with open(ps_path, "w", encoding="utf-8") as f:
                    f.write(ps_script)

                self.log(self.lt("ps_downloading"))
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                    capture_output=True, text=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode != 0:
                    self.log(self.lt("download_err", result.stderr or result.stdout or self.lt("upd_error")))
                    return

                if not os.path.exists(tmp) or os.path.getsize(tmp) < 1000000:
                    self.log(self.lt("file_bad"))
                    return

                size_mb = os.path.getsize(tmp) / 1048576
                self.log(self.lt("download_ok", size_mb))
                self.log(self.lt("unblock"))
                self._unblock_file(tmp)
                self.log(self.lt("installing"))
                upd_src = os.path.join(
                    getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                    "assets", "rm_updater.exe")
                upd_tmp = os.path.join(tempfile.gettempdir(), "rm_updater.exe")
                shutil.copyfile(upd_src, upd_tmp)
                subprocess.Popen([upd_tmp, tmp, self._installed_exe()],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                self.log(self.lt("install_msg"))
                time.sleep(1)
                try:
                    self._window.destroy()
                except Exception:
                    pass
            except Exception as e:
                self.log(self.lt("update_error", e))
                self.stop_progress()
                self.show_message(self.lt("msg_error"), self.lt("dl_err") % e)
        self.clear_log()
        self.open_log()
        self.start_progress()
        self.log(self.lt("downloading", name))
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
        self.log(self.lt("connecting", host, port))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password,
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log(self.lt("connected"))
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
        self.log(self.lt("uploading", os.path.basename(local_path)))
        sftp = client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()
        self.log(self.lt("uploaded", remote_path))

    # ---------- Запуск ----------
    def run_all(self):
        if not self.config.get("host") or not self.config.get("password"):
            self.show_message(self.lt("attention"), self.lt("enter_ip_pass"))
            return
        need_key = (
            (self.config["steps"].get("setup_wifi") and ENC_LABELS.get(self.config.get("wifi_enc_5g"), "sae") != "none")
            or (self.config["steps"].get("setup_wifi_2g") and ENC_LABELS.get(self.config.get("wifi_enc_2g"), "psk2") != "none")
        )
        if need_key and len(self.config.get("wifi_password", "")) < 8:
            self.show_message(self.lt("attention"), self.lt("wifi_short"))
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
                self.log(self.lt("rebooting"))
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, port=port, username=user, password=password,
                               timeout=15, look_for_keys=False, allow_agent=False)
                self.ssh_exec(client, "sleep 2; reboot", timeout=30)
                client.close()
                self.log(self.lt("reboot_wait", 300))
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
                        self.log(self.lt("wait_router"))
                if back_up:
                    self.log(self.lt("reboot_ok"))
                    self.show_message(self.lt("msg_done"),
                                      self.lt("reboot_done_msg") % host)
                else:
                    self.log(self.lt("reboot_timeout"))
            except Exception as e:
                self.log(self.lt("error", e))
                self.show_message(self.lt("msg_error"), str(e))
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
            self.log(self.lt("error", e))
            self.show_message(self.lt("msg_error"), str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log(self.lt("completed"))

    def run_steps(self):
        host, port, user, password = self._conn_info()

        self.log(self.lt("connecting", host, port))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password,
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log(self.lt("connected"))

        hostname = "RouterMaster"
        self.log(self.lt("host_name", hostname))
        self.ssh_exec(client,
                      "uci set system.@system[0].hostname='%s'; uci commit system; /etc/init.d/system reload"
                      % hostname)

        steps = self.config["steps"]

        if steps.get("update_packages"):
            self.log(self.lt("pkg_update"))
            self.ssh_exec(client, "apk update")
            out, _ = self.ssh_exec(client, "apk upgrade")
            if "error" in out.lower():
                self.ssh_exec(client, "apk upgrade")
                self.log(self.lt("apk_retry"))

        if steps.get("install_podkop"):
            self.log(self.lt("podkop_install"))
            self.ssh_exec(client, "wget -qO /tmp/podkop_install.sh https://raw.githubusercontent.com/itdoginfo/podkop/refs/heads/main/install.sh")
            self.ssh_exec(client, "printf 'y\\ny\\ny\\ny\\ny\\n' | sh /tmp/podkop_install.sh", timeout=600)
            self.ssh_exec(client, "uci delete podkop.@section[0].community_lists 2>/dev/null; for s in %s; do uci add_list podkop.@section[0].community_lists=\"$s\"; done; uci commit podkop" % PODKOP_COMMUNITY_LISTS)
            self.ssh_exec(client, "/etc/init.d/podkop enable; /etc/init.d/podkop start", timeout=60)

        if steps.get("install_zapret"):
            self.log(self.lt("zapret_install"))
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
            self.log(self.lt("theme_install", theme_name))
            if "url" in theme:
                exists, _ = self.ssh_exec(client, "apk info 2>/dev/null | grep -c '^%s$'" % theme["pkg"])
                if exists.strip() == "0":
                    self.install_theme_file(client, theme)
            else:
                self.ssh_exec(client, "apk add " + theme["pkg"], timeout=300)
            self.ssh_exec(client, "uci set luci.main.mediaurlbase='%s'; uci commit luci" % theme["media"])

        if steps.get("install_ru"):
            self.log(self.lt("lang_install"))
            self.ssh_exec(client, "apk add luci-i18n-base-ru", timeout=300)
            self.ssh_exec(client, "uci set luci.main.lang=ru; uci commit luci")

        if steps.get("setup_wifi") or steps.get("setup_wifi_2g"):
            self.log(self.lt("wifi_setup"))
            wp = self.config.get("wifi_password", "")
            chan = str(self.config.get("wifi_channel", "")).strip() or "36"
            parts = []
            if steps.get("setup_wifi"):
                ssid = str(self.config.get("wifi_ssid", "")).strip()
                enc5 = ENC_LABELS.get(self.config.get("wifi_enc_5g"), "sae")
                self.log(self.lt("wifi_5g", ssid, chan, enc5))
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
                self.log(self.lt("wifi_2g", ssid2, chan2, enc2))
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
                self.log(self.lt("proxy_setup"))
                self.ssh_exec(client,
                              "uci set podkop.@section[0].proxy_string='%s'; uci commit podkop; "
                              "/etc/init.d/podkop restart" % proxy.replace("'", ""))
            else:
                self.log(self.lt("no_proxy"))

        if steps.get("update_os"):
            self.log(self.lt("os_check"))
            out, _ = self.ssh_exec(client, "owut check 2>&1 | grep -E 'Version-from|Version-to|ERROR'", timeout=300)
            upgrade = None
            for line in out.splitlines():
                if "Version-to" in line:
                    upgrade = line.split("Version-to")[1].strip()
            if upgrade and "25.12.5" not in upgrade:
                self.log(self.lt("os_update_found", upgrade))
                ok = self.ask_confirm(self.lt("os_update"),
                                      self.lt("os_update_confirm") % upgrade)
                if ok:
                    self.ssh_exec(client,
                                  "printf 'y\\n' | owut upgrade --ignored-changes 'luci-app-podkop,luci-i18n-podkop-ru,luci-theme-argon,podkop' >/dev/null 2>&1 &",
                                  timeout=60)
                    self.log(self.lt("os_update_started"))
                else:
                    self.log(self.lt("os_update_cancelled"))
            else:
                self.log(self.lt("os_up_to_date"))

        client.close()
        self.log(self.lt("setup_done"))

    def install_theme_file(self, client, theme):
        self.log(self.lt("theme_dl", theme["pkg"]))
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        except Exception:
            pass
        local = os.path.join(DOWNLOAD_DIR, theme["pkg"] + ".apk")
        urllib.request.urlretrieve(theme["url"], local)
        self.log(self.lt("theme_dl_done", os.path.getsize(local), DOWNLOAD_DIR))
        self.ssh_exec(client, "apk add openssh-sftp-server", timeout=300)
        self.ssh_upload(client, local, "/tmp/theme.apk")
        self.ssh_exec(client, "apk add --allow-untrusted /tmp/theme.apk", timeout=300)

    # ---------- Удаление сервисов ----------
    def remove_podkop(self):
        if not self.config.get("host") or not self.config.get("password"):
            self.show_message(self.lt("attention"), self.lt("enter_ip_pass"))
            return
        if not self.ask_confirm(self.lt("remove_podkop"),
                                self.lt("remove_podkop_msg")):
            return
        threading.Thread(target=self._remove_podkop_worker, daemon=True).start()

    def _remove_podkop_worker(self):
        self.open_log()
        self.set_running(True)
        self.start_progress()
        try:
            self.log(self.lt("podkop_rm_header"))
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
            self.log(self.lt("podkop_rm_done"))
            client.close()
        except Exception as e:
            self.log(self.lt("error", e))
            self.show_message(self.lt("msg_error"), str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log(self.lt("remove_done"))

    def remove_zapret(self):
        if not self.config.get("host") or not self.config.get("password"):
            self.show_message(self.lt("attention"), self.lt("enter_ip_pass"))
            return
        if not self.ask_confirm(self.lt("remove_zapret"),
                                self.lt("remove_zapret_msg")):
            return
        threading.Thread(target=self._remove_zapret_worker, daemon=True).start()

    def _remove_zapret_worker(self):
        self.open_log()
        self.set_running(True)
        self.start_progress()
        try:
            self.log(self.lt("zapret_rm_header"))
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
            self.log(self.lt("zapret_rm_done"))
            client.close()
        except Exception as e:
            self.log(self.lt("error", e))
            self.show_message(self.lt("msg_error"), str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log(self.lt("remove_done"))

    # ---------- Сброс + настройка ----------
    def reset_and_setup(self):
        if not self.config.get("host") or not self.config.get("password"):
            self.show_message(self.lt("attention"), self.lt("enter_ip_pass"))
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
            self.log(self.lt("error", e))
            self.show_message(self.lt("msg_error"), str(e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            self.log(self.lt("completed"))

    def do_reset_and_setup(self):
        host, port, user, _ = self._conn_info()

        self.log(self.lt("reset_header"))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=self.config.get("password"),
                       timeout=15, look_for_keys=False, allow_agent=False)
        self.log(self.lt("connected") + " " + self.lt("reset_exec"))
        try:
            self.ssh_exec(client, "/sbin/firstboot -r -y", timeout=60)
        except Exception:
            self.log(self.lt("conn_reset"))
        client.close()

        self.log(self.lt("open_web", host))
        webbrowser.open("http://%s/cgi-bin/luci/admin/system/flash" % host)

        self.log(self.lt("wait_boot"))
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
                self.log(self.lt("wait_router"))

        if luci_up:
            self.log(self.lt("luci_ready"))
            if self.luci_set_password(host, self.new_password):
                self.log(self.lt("pass_set"))
            else:
                self.log(self.lt("pass_fail", self.new_password))
        else:
            self.log(self.lt("luci_wait"))

        self.log(self.lt("wait_ssh"))
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
                self.log(self.lt("wait_ssh_dot"))

        if not connected:
            raise RuntimeError(self.lt("ssh_wait_fail"))

        self.log(self.lt("ssh_new_pass"))
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
            self.show_message(self.lt("attention"), self.lt("enter_ip_pass"))
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
                self.log(self.lt("ok", good))
            else:
                ok = False
                self.log(self.lt("check_fail", bad))

        self.start_progress()
        try:
            self.log(self.lt("testing"))
            host, port, _, _ = self._conn_info()

            self.log(self.lt("test_system_header"))
            self.log(self.lt("os_info", platform.platform()))
            self.log("Python: %s" % sys.version.split()[0])
            check(sys.version_info >= (3, 8), self.lt("python_ok"), self.lt("python_bad"))

            self.log(self.lt("test_router_header", host, port))
            try:
                s = socket.create_connection((host, port), timeout=5)
                s.close()
                self.log("[OK] " + self.lt("port_ok", port))
            except Exception:
                ok = False
                self.log(self.lt("check_fail", self.lt("port_fail", host, port)))
                self.log(self.lt("check_cable"))
                raise SystemExit

            client = self._connect_ssh()
            check(True, self.lt("ssh_ok"), "")

            self.log(self.lt("test_router_system"))
            out, _ = self.ssh_exec(client, "uname -a")
            check(bool(out.strip()), self.lt("kernel", out.strip()[:90]), self.lt("kernel_fail"))

            out, _ = self.ssh_exec(client, "cat /etc/openwrt_release 2>/dev/null | head -2 || cat /etc/os-release | head -2")
            check(bool(out.strip()), self.lt("firmware", " ".join(out.split())[:100]), self.lt("firmware_fail"))

            out, _ = self.ssh_exec(client, "cat /proc/meminfo | head -2")
            check(bool(out.strip()), self.lt("memory", " ".join(out.split())[:80]), self.lt("memory_fail"))

            out, _ = self.ssh_exec(client, "df -h / | tail -1")
            check(bool(out.strip()), self.lt("disk", " ".join(out.split())[:80]), self.lt("disk_fail"))

            self.log(self.lt("test_inet"))
            out, _ = self.ssh_exec(client, "ping -c 2 -W 2 8.8.8.8 2>&1 | tail -2")
            check("0% packet loss" in out or "2 received" in out,
                  self.lt("inet_works", " ".join(out.split())[:80]),
                  self.lt("inet_no"))

            self.log(self.lt("test_services"))
            out, _ = self.ssh_exec(client, "uci get network.lan.ipaddr 2>/dev/null || ip -4 addr show br-lan 2>/dev/null | grep inet")
            check(bool(out.strip()), self.lt("ip_router", " ".join(out.split())[:60]), self.lt("ip_fail"))

            self.log("")
            if ok:
                self.log(self.lt("test_result_ok"))
            else:
                self.log(self.lt("test_result_fail"))
        except SystemExit:
            pass
        except Exception as e:
            ok = False
            self.log(self.lt("error", e))
        finally:
            self.stop_progress()
            self.set_running(False)
            self.open_log()
            if ok:
                self.log(self.lt("test_finished"))
                self.show_message(self.lt("test_complete"), self.lt("test_good_msg"))
            else:
                self.log(self.lt("test_finished_bad"))
                self.show_message(self.lt("test_complete"), self.lt("test_bad_msg"))


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
        app.log(self.lt("init_done"))

    window.events.loaded += on_loaded
    window.events.closing += lambda: app.save_config()

    webview.start(icon=_find_icon())
    return app


if __name__ == "__main__":
    main()