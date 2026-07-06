const fs = require('fs');
const path = require('path');
const os = require('os');

const CONFIG_FILE = path.join(os.homedir(), '.exec-assistant-config.json');

const DEFAULTS = {
  anthropicKey: '',
  msClientId: '',
  msTenantId: 'common',
  emailFetchCount: 75,
  blocklist: [],
  starlist: [],
  digestTimes: ['10:00', '18:00'],
  signalsTime: '07:30',   // daily podcast signal-scanner run
  userName: '',
  userTitle: '',
  people: [],             // [{name,email,relationship,priority}]
};

function loadConfig() {
  if (fs.existsSync(CONFIG_FILE)) {
    try {
      const saved = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
      return { ...DEFAULTS, ...saved };
    } catch {}
  }
  return { ...DEFAULTS };
}

function saveConfig(cfg) {
  const merged = { ...loadConfig(), ...cfg };
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(merged, null, 2), { mode: 0o600 });
}

module.exports = { loadConfig, saveConfig };
