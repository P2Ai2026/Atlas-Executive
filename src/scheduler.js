/**
 * Lightweight scheduler — checks every 30s AND on demand (launch, wake).
 * - Digest fires at configured times (default 10:00 and 18:00, daily)
 * - Podcast signal scanner is SELF-HEALING: it runs whenever we notice it's
 *   past the scheduled time and today's scan hasn't happened yet — so a Mac
 *   that was asleep/off at 07:30 still gets its scan the moment the app is
 *   awake, instead of silently skipping the day.
 * - Stocks agent fires Mondays at/after 10:00 (also catch-up style).
 */

const { loadConfig } = require('./config');

let interval = null;
let lastFired = {};
let ctx = null;   // { digestFn, agentFn, isPodcastFreshFn }

function tick() {
  if (!ctx) return;
  const { digestFn, agentFn, isPodcastFreshFn } = ctx;
  const now  = new Date();
  const hhmm = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const cfg  = loadConfig();
  const times = cfg.digestTimes || ['10:00', '18:00'];
  const key   = now.toDateString();

  // Prune fire-keys from previous days so the map doesn't grow forever
  for (const k of Object.keys(lastFired)) {
    if (!k.endsWith(key)) delete lastFired[k];
  }

  // Daily digest — exact-minute (cheap, reads live mail; fine to miss a slot)
  for (const t of times) {
    const fireKey = `digest:${t}:${key}`;
    if (hhmm === t && lastFired[fireKey] !== true) {
      lastFired[fireKey] = true;
      digestFn().catch(err => console.error('Scheduled digest error:', err));
    }
  }

  if (!agentFn) return;

  // Daily podcast scan — SELF-HEALING catch-up.
  // Fires once it's past signalsTime AND no scan has been recorded on disk
  // today. lastFired guards against re-firing during the ~30-min run (before
  // signals_latest.json updates); the disk check survives app restarts.
  const signalsTime = cfg.signalsTime || '07:30';
  const podKey = `agent:podcast:${key}`;
  const scanFreshToday = isPodcastFreshFn ? safe(isPodcastFreshFn) : false;
  if (hhmm >= signalsTime && lastFired[podKey] !== true && !scanFreshToday) {
    lastFired[podKey] = true;
    agentFn('podcast');
  }

  // Monday stocks — catch-up at/after 10:00
  if (now.getDay() === 1 && hhmm >= '10:00') {
    const stockKey = `agent:stocks:${key}`;
    if (lastFired[stockKey] !== true) {
      lastFired[stockKey] = true;
      agentFn('stocks');
    }
  }
}

function safe(fn) { try { return fn(); } catch { return false; } }

function start(digestFn, agentFn, isPodcastFreshFn) {
  ctx = { digestFn, agentFn, isPodcastFreshFn };
  tick();                              // immediate catch-up on launch
  interval = setInterval(tick, 30000);
}

function stop() {
  if (interval) clearInterval(interval);
}

module.exports = { start, stop, tick };
