// RouterMaster UI
const App = {
  api: null,
  current: 'home',
  _logBuf: '',
  timer: null,
  running: false,

  init() {
    this.bindNav();
    this.bindActions();
    this.bindFields();
    this.bindTitlebar();
    this.initDropdowns();
    this.loadStars();
    setInterval(() => this.loadStars(), 300000);
  },

  initDropdowns() {
    this._dds = [];
    document.querySelectorAll('select').forEach(sel => this.buildDropdown(sel));
  },

  buildDropdown(sel) {
    const wrap = document.createElement('div');
    wrap.className = 'dd';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'dd-btn';
    const list = document.createElement('div');
    list.className = 'dd-list hidden';
    const render = () => {
      btn.textContent = sel.options[sel.selectedIndex]?.text || '';
    };
    const close = () => list.classList.add('hidden');
    sel.querySelectorAll('option').forEach((o, i) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'dd-item' + (o.selected ? ' sel' : '');
      item.textContent = o.text;
      item.addEventListener('click', () => {
        sel.selectedIndex = i;
        sel.dispatchEvent(new Event('change'));
        list.querySelectorAll('.dd-item').forEach(el => el.classList.remove('sel'));
        item.classList.add('sel');
        render();
        close();
      });
      list.appendChild(item);
    });
    btn.addEventListener('click', e => {
      e.stopPropagation();
      document.querySelectorAll('.dd-list').forEach(l => {
        if (l !== list) l.classList.add('hidden');
      });
      list.classList.toggle('hidden');
      btn.classList.toggle('open', !list.classList.contains('hidden'));
    });
    document.addEventListener('mousedown', e => {
      if (!wrap.contains(e.target)) close();
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') close();
    });
    render();
    wrap.appendChild(btn);
    wrap.appendChild(list);
    sel.insertAdjacentElement('afterend', wrap);
    sel.classList.add('dd-native');
    this._dds.push({ sel, btn });
  },

  syncDropdowns() {
    this._dds.forEach(({ sel, btn }) => {
      btn.textContent = sel.options[sel.selectedIndex]?.text || '';
    });
  },

  bindTitlebar() {
    this.byId('btn-min').addEventListener('click', () => this.api?.minimize_window());
    this.byId('btn-max').addEventListener('click', () => this.api?.toggle_maximize());
    this.byId('btn-close').addEventListener('click', () => this.api?.close_window());
    const tb = this.byId('titlebar');
    const dpr = window.devicePixelRatio || 1;
    let dragging = false, sx = 0, sy = 0;
    tb.addEventListener('mousedown', e => {
      if (e.button !== 0 || e.target.closest('.tb-btn')) return;
      dragging = true;
      sx = e.screenX;
      sy = e.screenY;
      this.api?.begin_drag();
      e.preventDefault();
    });
    window.addEventListener('mousemove', e => {
      if (!dragging) return;
      this.api?.move_window(Math.round((e.screenX - sx) * dpr), Math.round((e.screenY - sy) * dpr));
    });
    window.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      this.api?.end_drag();
    });
    tb.addEventListener('dblclick', e => {
      if (e.target.closest('.tb-btn')) return;
      this.api?.toggle_maximize();
    });
  },

  async loadStars() {
    const el = this.byId('repo-stars');
    try {
      const s = await this.api?.get_stars();
      el.textContent = '★ ' + (s >= 1000 ? (s / 1000).toFixed(1).replace('.', ',') + 'k' : (s ?? 0));
    } catch (e) {
      el.textContent = '★ 0';
    }
  },

  bindNav() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => this.show(btn.dataset.page));
    });
  },

  show(page) {
    this.current = page;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.page === page));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
  },

  bindActions() {
    document.getElementById('btn-run').addEventListener('click', () => this.showRunConfirm());
    document.getElementById('btn-reset').addEventListener('click', () => {
      this.api?.reset_and_setup();
    });
    document.getElementById('btn-save')?.addEventListener('click', () => this.api?.save_config().then(() => this.msg('Настройки сохранены', 'Готово')));
    document.getElementById('btn-log').addEventListener('click', () => this.openLog());
    document.getElementById('btn-test').addEventListener('click', () => this.api?.test_system());
    const btnCheck = document.getElementById('btn-check');
    btnCheck.addEventListener('click', () => {
      btnCheck.classList.add('checking');
      (this.api?.check_update() || Promise.resolve()).finally(() => btnCheck.classList.remove('checking'));
    });
    document.getElementById('btn-extra').addEventListener('click', () => this.api?.open_extra_soft());
    document.getElementById('btn-side-toggle').addEventListener('click', () => this.toggleSidebar());
    this.byId('repo-widget').addEventListener('click', e => {
      e.preventDefault();
      this.api?.open_repo();
    });
    document.getElementById('btn-settings').addEventListener('click', () => this.openSettings());
    document.getElementById('settings-ok').addEventListener('click', () => this.byId('settings-overlay').style.display = 'none');
    document.getElementById('settings-save').addEventListener('click', () => {
      this.api?.save_config().then(() => this.msg('Настройки сохранены', 'Готово'));
    });
    document.getElementById('settings-reset').addEventListener('click', () => this.resetSettings());
    document.getElementById('btn-open-folder').addEventListener('click', () => this.api?.open_download_dir());
    document.getElementById('st-theme-mode').addEventListener('change', e => this.setDark(e.target.value === 'dark'));
    document.getElementById('st-autocheck').addEventListener('change', e => this.api?.save_field('auto_check_update', e.target.checked));
    document.getElementById('st-fontsize').addEventListener('change', e => {
      document.body.classList.remove('font-small', 'font-large');
      if (e.target.value === 'small') document.body.classList.add('font-small');
      if (e.target.value === 'large') document.body.classList.add('font-large');
      this.api?.save_field('font_size', e.target.value);
    });
    document.getElementById('st-downloads').addEventListener('input', e => this.api?.save_field('download_dir', e.target.value));
    const bindPassToggle = (btnId, inpId) => {
      const btn = document.getElementById(btnId);
      btn.addEventListener('click', () => {
        const inp = document.getElementById(inpId);
        const show = inp.type === 'password';
        inp.type = show ? 'text' : 'password';
        btn.textContent = show ? 'Скрыть' : 'Показать';
      });
    };
    bindPassToggle('btn-show-pass', 'cfg-pass');
    bindPassToggle('btn-show-pass-wifi', 'cfg-wifi-pass');
    document.querySelectorAll('[data-act]').forEach(b => {
      b.addEventListener('click', () => this.api[b.dataset.act]());
    });

    document.getElementById('log-close').addEventListener('click', () => this.hideLog());
    document.getElementById('log-copy').addEventListener('click', async () => {
      const txt = await this.api?.copy_log();
      if (txt) {
        await navigator.clipboard.writeText(txt);
        this.msg('Лог скопирован в буфер обмена.', 'Готово');
      }
    });
    document.getElementById('log-clear').addEventListener('click', () => this.clearLog());
    document.getElementById('confirm-ok').addEventListener('click', () => this.confirmResolve(true));
    document.getElementById('confirm-cancel').addEventListener('click', () => this.confirmResolve(false));
    document.getElementById('msg-ok').addEventListener('click', () => this.byId('msg-overlay').style.display = 'none');
    document.getElementById('run-ok').addEventListener('click', () => {
      this.byId('run-overlay').style.display = 'none';
      this.api?.run_all();
    });
    document.getElementById('run-cancel').addEventListener('click', () => {
      this.byId('run-overlay').style.display = 'none';
    });
    document.getElementById('reboot-ok').addEventListener('click', () => {
      this.byId('reboot-overlay').style.display = 'none';
      this.api?.reboot_router();
    });
    document.getElementById('reboot-cancel').addEventListener('click', () => {
      this.byId('reboot-overlay').style.display = 'none';
    });
  },

  byId(id) { return document.getElementById(id); },

  bindFields() {
    const map = {
      'cfg-host': 'host', 'cfg-port': 'port', 'cfg-user': 'user', 'cfg-pass': 'password',
      'cfg-ssid': 'wifi_ssid', 'cfg-ssid2': 'wifi_ssid_2g', 'cfg-wifi-pass': 'wifi_password',
      'cfg-ch5': 'wifi_channel', 'cfg-ch2': 'wifi_channel_2g', 'cfg-proxy': 'proxy_string'
    };
    Object.entries(map).forEach(([id, key]) => {
      const el = this.byId(id);
      el.addEventListener('input', () => this.api?.save_field(key, el.value));
    });

    const stepsMap = {
      'st-update': 'update_packages', 'st-podkop': 'install_podkop', 'st-zapret': 'install_zapret',
      'st-theme': 'install_argon', 'st-ru': 'install_ru', 'st-wifi': 'setup_wifi',
      'st-wifi2': 'setup_wifi_2g', 'st-proxy': 'setup_proxy', 'st-os': 'update_os'
    };
    Object.entries(stepsMap).forEach(([id, key]) => {
      this.byId(id).addEventListener('change', e => this.api?.save_field('steps.' + key, e.target.checked));
    });

    const selMap = { 'st-theme-sel': 'theme', 'st-enc5': 'wifi_enc_5g', 'st-enc2': 'wifi_enc_2g' };
    Object.entries(selMap).forEach(([id, key]) => {
      this.byId(id).addEventListener('change', e => this.api?.save_field(key, e.target.value));
    });
  },

async loadConfig() {
    const cfg = await this.api?.get_config();
    if (!cfg) return;
    this.cfg = cfg;
    const set = (id, val) => { const el = this.byId(id); if (el && val !== undefined && val !== null) el.value = val; };
    set('cfg-host', cfg.host); set('cfg-port', cfg.port); set('cfg-user', cfg.user); set('cfg-pass', cfg.password);
    set('cfg-ssid', cfg.wifi_ssid); set('cfg-ssid2', cfg.wifi_ssid_2g); set('cfg-wifi-pass', cfg.wifi_password);
    set('cfg-ch5', cfg.wifi_channel); set('cfg-ch2', cfg.wifi_channel_2g); set('cfg-proxy', cfg.proxy_string);
    const st = cfg.steps || {};
    const stSet = (id, val) => { const el = this.byId(id); if (el) el.checked = !!val; };
    stSet('st-update', st.update_packages); stSet('st-podkop', st.install_podkop); stSet('st-zapret', st.install_zapret);
    stSet('st-theme', st.install_argon); stSet('st-ru', st.install_ru); stSet('st-wifi', st.setup_wifi);
    stSet('st-wifi2', st.setup_wifi_2g); stSet('st-proxy', st.setup_proxy); stSet('st-os', st.update_os);
    this.byId('st-theme-sel').value = cfg.theme || 'Argon';
    this.byId('st-enc5').value = cfg.wifi_enc_5g || 'WPA3 (SAE)';
    this.byId('st-enc2').value = cfg.wifi_enc_2g || 'WPA2 (PSK)';
    this.byId('app-ver').textContent = cfg.app_version || '';
    this.syncDropdowns();
    if (cfg.sidebar_collapsed) this.byId('sidebar').classList.add('collapsed');
    if ((cfg.gui_theme || 'light') === 'dark') document.body.classList.add('dark');
    if (cfg.font_size === 'small') document.body.classList.add('font-small');
    if (cfg.font_size === 'large') document.body.classList.add('font-large');
  },

  setDark(on) {
    this.byId('st-theme-mode').value = on ? 'dark' : 'light';
    document.body.classList.toggle('dark', !!on);
    this.api?.set_theme(!!on);
  },

  toggleSidebar() {
    const sb = this.byId('sidebar');
    sb.classList.toggle('collapsed');
    this.api?.save_field('sidebar_collapsed', sb.classList.contains('collapsed'));
  },

  openSettings() {
    this.byId('st-theme-mode').value = (this.cfg?.gui_theme || 'light') === 'dark' ? 'dark' : 'light';
    this.byId('st-autocheck').checked = !!(this.cfg && this.cfg.auto_check_update);
    this.byId('st-fontsize').value = this.cfg?.font_size || 'normal';
    this.byId('settings-overlay').style.display = 'flex';
    this.api?.get_default_download_dir().then(d => {
      this.byId('st-downloads').value = this.cfg?.download_dir || '';
      this.byId('st-downloads').placeholder = d;
    });
  },

  async resetSettings() {
    const ok = await this.confirm('Сбросить все настройки программы к значениям по умолчанию?', 'Сброс настроек');
    if (!ok) return;
    await this.api?.reset_settings();
    this.byId('settings-overlay').style.display = 'none';
    await this.loadConfig();
    this.msg('Настройки программы сброшены к значениям по умолчанию.');
  },

  // API вызывается из Python
  log(msg) {
    const el = this.byId('log-text');
    if (!el) return;
    el.textContent += msg + '\n';
    el.scrollTop = el.scrollHeight;
  },
  clearLog() { this.byId('log-text').textContent = ''; },
  setTime(text) { this.byId('log-time').textContent = 'Время: ' + text; },
  setProgress(on) {
    const el = this.byId('progress-bar');
    el.closest('.progress').classList.toggle('running', !!on);
    el.style.width = on ? '100%' : '0';
  },
  setRunning(on) {
    this.running = !!on;
    this.byId('btn-run').disabled = on;
    this.byId('btn-reset').disabled = on;
    this.byId('btn-test').disabled = on;
  },
  openLog() { this.byId('log-overlay').classList.remove('hidden'); this.byId('log-overlay').style.display = 'flex'; },
  hideLog() { this.byId('log-overlay').style.display = 'none'; },

  showRunConfirm() {
    const steps = this.cfg?.steps || {};
    const labels = {
      update_packages: 'Обновить все пакеты',
      install_podkop: 'Установить / обновить Podkop',
      install_zapret: 'Установить / обновить Zapret',
      install_argon: 'Установить тему',
      install_ru: 'Русский язык интерфейса',
      setup_wifi: 'Создать Wi-Fi 5G',
      setup_wifi_2g: 'Создать Wi-Fi 2G',
      setup_proxy: 'Задать прокси для Podkop',
      update_os: 'Обновить ОС (прошивку)',
    };
    const list = this.byId('run-steps-list');
    list.innerHTML = '';
    let hasAny = false;
    for (const [key, label] of Object.entries(labels)) {
      if (steps[key]) {
        const li = document.createElement('li');
        li.textContent = label;
        list.appendChild(li);
        hasAny = true;
      }
    }
    if (!hasAny) {
      const li = document.createElement('li');
      li.textContent = 'Ничего не выбрано';
      list.appendChild(li);
    }
    this.byId('run-overlay').style.display = 'flex';
  },

  confirmResolve(ok) {
    this.byId('confirm-overlay').style.display = 'none';
    if (this._confirmResolve) this._confirmResolve(ok);
    this.api?.confirm_response(ok);
  },

  showRebootConfirm() {
    this.byId('reboot-overlay').style.display = 'flex';
  },

  async confirm(text, title = 'Подтверждение') {
    return new Promise(resolve => {
      this.byId('confirm-text').textContent = text;
      this.byId('confirm-title').textContent = title;
      this.byId('confirm-overlay').style.display = 'flex';
      this._confirmResolve = resolve;
    });
  },

  msg(text, title = 'Сообщение') {
    this.byId('msg-text').textContent = text;
    this.byId('msg-title').textContent = title;
    this.byId('msg-overlay').style.display = 'flex';
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
window.addEventListener('pywebviewready', () => {
  App.api = window.pywebview.api;
  App.loadConfig();
});
window.App = App;