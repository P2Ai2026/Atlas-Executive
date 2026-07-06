/**
 * Lightweight scheduler — checks every 30s.
 * - Digest fires at configured times (default 10:00 and 18:00, daily)
 * - Podcast signal scanner fires DAILY (default 07:30, cfg.signalsTime)
 * - Stocks agent fires at 10:00 on Mondays
 */

const { loadConfig } = require('./config');

let interval = null;
let lastFired = {};

function start(digestFn, agentFn) {
  interval = setInterval(() => {
    const now  = new Date();
    const hhmm = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    const cfg  = loadConfig();
    const times = cfg.digestTimes || ['10:00', '18:00'];
    const key   = now.toDateString();

    // Prune fire-keys from previous days so the map doesn't grow forever
    for (const k of Object.keys(lastFired)) {
      if (!k.endsWith(key)) delete lastFired[k];
    }

    // Daily digest
    for (const t of times) {
      const fireKey = `digest:${t}:${key}`;
      if (hhmm === t && lastFired[fireKey] !== true) {
        lastFired[fireKey] = true;
        digestFn().catch(err => console.error('Scheduled digest error:', err));
      }
    }

    if (!agentFn) return;

    // Daily — podcast signal scanner (feeds the Signal Radar)
    const signalsTime = cfg.signalsTime || '07:30';
    const podKey = `agent:podcast:${key}`;
    if (hhmm === signalsTime && lastFired[podKey] !== true) {
      lastFired[podKey] = true;
      agentFn('podcast');
    }

    // Monday 10:00 — stocks agent
    if (now.getDay() === 1 && hhmm === '10:00') {
      const stockKey = `agent:stocks:${key}`;
      if (lastFired[stockKey] !== true) {
        lastFired[stockKey] = true;
        agentFn('stocks');
      }
    }
  }, 30000);
}

function stop() {
  if (interval) clearInterval(interval);
}

module.exports = { start, stop };
