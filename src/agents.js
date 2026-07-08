/**
 * Agent Hub — manages Python agent runs and surfaces their PDF output.
 * Does NOT re-summarise reports; the PDF is the source of truth.
 */

const { execFile, spawn } = require('child_process');
const util = require('util');
const fs   = require('fs');
const path = require('path');
const os   = require('os');
const exec = util.promisify(execFile);

const OLLAMA_BASE = 'http://127.0.0.1:11434/api';

// Agents ship inside this repo under agents/. Legacy Desktop paths are kept
// as fallbacks so a machine with the original standalone folders still works.
const REPO_AGENTS = path.join(__dirname, '..', 'agents');

const AGENT_CONFIG = {
  stocks: {
    name:        'Distressed Stocks',
    icon:        '📉',
    outputDir:   path.join(os.homedir(), 'Desktop', 'Distress Reports'),
    outputEnv:   'DISTRESS_OUTPUT_DIR',   // passed to the script so both agree
    filePattern: /^distress_report_.*\.pdf$/i,
    scriptCandidates: [
      path.join(REPO_AGENTS, 'stocks', 'weekly_run.py'),
      path.join(os.homedir(), 'Desktop', 'Agent 1- Distressed Stocks', 'weekly_run.py'),
      path.join(os.homedir(), 'Desktop', 'internship', 'weekly_run.py'),
    ],
    venvCandidates: [
      path.join(REPO_AGENTS, 'stocks', '.venv'),
      path.join(os.homedir(), 'Desktop', 'Agent 1- Distressed Stocks', '.venv'),
      path.join(os.homedir(), 'Desktop', 'internship', '.venv'),
    ],
  },
  podcast: {
    name:        'Podcast Intel',
    icon:        '🎙️',
    outputDir:   path.join(os.homedir(), 'Desktop', 'Agent 3- Podcast Reviews'),
    outputEnv:   'PODCAST_OUTPUT_DIR',
    filePattern: /^podcast_brief_.*\.pdf$/i,
    // Run the podcast agent DIRECTLY — weekly_run.py runs both agents and
    // skips itself when the week's distress report exists, which made this
    // button silently do nothing.
    scriptCandidates: [
      path.join(REPO_AGENTS, 'podcast', 'podcast_intel_agent.py'),
      path.join(os.homedir(), 'Desktop', 'internship', 'podcast_intel_agent.py'),
    ],
    venvCandidates: [
      path.join(REPO_AGENTS, 'podcast', '.venv'),
      path.join(os.homedir(), 'Desktop', 'internship', '.venv'),
    ],
    // The agent also writes signals_latest.json every run (daily Signal Radar)
    signalsFile: path.join(os.homedir(), 'Desktop', 'Agent 3- Podcast Reviews', 'signals_latest.json'),
  },
};

function firstExisting(candidates) {
  return (candidates || []).find(p => fs.existsSync(p)) || null;
}

// ── PDF listing ───────────────────────────────────────────────────────────────

// Returns all reports for an agent, newest first.
function getAgentReports(agentKey) {
  const cfg = AGENT_CONFIG[agentKey];
  if (!cfg) return [];
  try {
    return fs.readdirSync(cfg.outputDir)
      .filter(f => cfg.filePattern.test(f))
      .map(f => {
        const fullPath = path.join(cfg.outputDir, f);
        const stat = fs.statSync(fullPath);
        return { name: f, path: fullPath, mtime: stat.mtime.toISOString() };
      })
      .sort((a, b) => b.mtime.localeCompare(a.mtime));
  } catch {
    return [];
  }
}

// ── PDF text extraction (for digest highlights only) ─────────────────────────

async function extractPdfText(pdfPath) {
  try {
    const { stdout } = await exec('pdftotext', [pdfPath, '-']);
    if (stdout.trim().length > 100) return stdout.trim();
  } catch {}
  try {
    const { stdout } = await exec('strings', [pdfPath]);
    return stdout.split('\n')
      .filter(l => l.trim().length > 6 && /[a-zA-Z]{3,}/.test(l))
      .join('\n');
  } catch {}
  return '';
}

// Returns a one-line highlight per agent for the email digest.
async function getAgentHighlights() {
  const highlights = [];
  for (const [key, cfg] of Object.entries(AGENT_CONFIG)) {
    const reports = getAgentReports(key);
    if (!reports.length) continue;
    const latest = reports[0];
    const rawText = await extractPdfText(latest.path);
    if (!rawText) continue;
    try {
      const res = await fetch(`${OLLAMA_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'qwen2.5',
          stream: false,
          messages: [
            { role: 'system', content: 'You are an executive assistant. Extract the single most important finding from this report in ONE sentence of 20 words or less. Be specific — include names, tickers, or figures.' },
            { role: 'user', content: rawText.slice(0, 4000) },
          ],
        }),
      });
      if (!res.ok) continue;
      const data = await res.json();
      const topLine = (data.message?.content || '').trim().split('\n')[0];
      if (topLine) {
        const date = new Date(latest.mtime).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        highlights.push(`- ${cfg.icon} ${cfg.name} (${date}): ${topLine} → See ${cfg.name} tab.`);
      }
    } catch {}
  }
  return highlights;
}

// ── Signal Radar data (written daily by the podcast agent) ────────────────────

function getSignals() {
  try {
    return JSON.parse(fs.readFileSync(AGENT_CONFIG.podcast.signalsFile, 'utf8'));
  } catch {
    return null;
  }
}

const HISTORY_FILE = path.join(AGENT_CONFIG.podcast.outputDir, 'signal_history.json');

function getSignalHistory() {
  try {
    return JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf8'));
  } catch {
    return null;
  }
}

// Weekly mention counts for a set of terms over the trailing N weeks — the
// data behind the sparklines. One pass over history for all terms at once.
function getTermSeries(terms, weeks = 8) {
  const hist = getSignalHistory();
  const out = {};
  for (const t of terms) out[t] = Array(weeks).fill(0);
  if (!hist) return out;
  const now = Date.now();
  const WEEK = 7 * 86400000;
  for (const e of hist.episodes || []) {
    const age = now - new Date(e.date + 'T12:00:00').getTime();
    const bucket = Math.floor(age / WEEK);           // 0 = current week
    if (bucket < 0 || bucket >= weeks) continue;
    for (const t of terms) {
      if (e.terms && e.terms[t]) out[t][weeks - 1 - bucket] += e.terms[t];
    }
  }
  return out; // arrays run oldest → newest
}

// Every episode that mentioned a term — the receipts behind a signal.
function getTermEvidence(term) {
  const hist = getSignalHistory();
  if (!hist) return { term, episodes: [] };
  const episodes = (hist.episodes || [])
    .filter(e => e.terms && e.terms[term])
    .map(e => ({ date: e.date, podcast: e.podcast, title: e.title, count: e.terms[term] }))
    .sort((a, b) => b.date.localeCompare(a.date));
  return { term, episodes: episodes.slice(0, 25) };
}

// Mute a term: mark it "drop" in term_verdicts (the agent respects this on
// every future run) and strip it from the current signals JSON immediately.
function muteTerm(term) {
  const hist = getSignalHistory() || { episodes: [] };
  hist.term_verdicts = hist.term_verdicts || {};
  hist.term_verdicts[term] = 'drop';
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(hist, null, 1));
  const sig = getSignals();
  if (sig && sig.signals) {
    sig.signals = sig.signals.filter(s => s.term !== term);
    fs.writeFileSync(AGENT_CONFIG.podcast.signalsFile, JSON.stringify(sig, null, 1));
  }
  return getSignals();
}

// ── Agent runner with file-watcher notification ───────────────────────────────

// One in-flight run per agent — clicking Run Now twice must not spawn two
// Python processes racing to write the same PDF.
const inFlight = {}; // key → start timestamp

function resolvePython(agentKey) {
  const cfg = AGENT_CONFIG[agentKey];
  for (const d of cfg.venvCandidates || []) {
    const py = path.join(d, 'bin', 'python3');
    if (fs.existsSync(py)) return py;
  }
  return 'python3';
}

// Launches the agent detached, then watches the output folder for a new PDF.
// Calls onReady(reportName) when a new PDF appears (up to 2h timeout).
function runAgent(agentKey, onReady) {
  const cfg = AGENT_CONFIG[agentKey];
  if (!cfg) throw new Error('Unknown agent key');

  // Guard: refuse to double-launch while a run from the last 2h is still going
  if (inFlight[agentKey] && Date.now() - inFlight[agentKey] < 2 * 60 * 60 * 1000) {
    return { started: false, alreadyRunning: true };
  }
  inFlight[agentKey] = Date.now();

  const scriptPath = firstExisting(cfg.scriptCandidates);
  if (!scriptPath) {
    delete inFlight[agentKey];
    throw new Error(`Runner script not found. Looked in:\n${cfg.scriptCandidates.join('\n')}`);
  }

  // Ensure output dir exists so we can watch it
  fs.mkdirSync(cfg.outputDir, { recursive: true });

  const python    = resolvePython(agentKey);
  const cwd       = path.dirname(scriptPath);
  const startTime = Date.now();
  let   notified  = false;

  const env = { ...process.env, PYTHONUNBUFFERED: '1' };
  if (cfg.outputEnv) env[cfg.outputEnv] = cfg.outputDir;

  const child = spawn(python, [scriptPath], {
    cwd,
    detached: true,
    stdio: 'ignore',
    env,
  });
  child.unref();

  // Watch output folder for new PDF created after run started
  const checkForNewPdf = () => {
    if (notified) return;
    try {
      let newReports = getAgentReports(agentKey)
        .filter(r => new Date(r.mtime).getTime() > startTime);
      // The podcast agent writes signals_latest.json every run, but a PDF only
      // when there are new episodes — a fresh JSON also means "run finished".
      if (!newReports.length && cfg.signalsFile && fs.existsSync(cfg.signalsFile)
          && fs.statSync(cfg.signalsFile).mtime.getTime() > startTime) {
        newReports = [{ name: 'Signal Radar updated (no new episodes)' }];
      }
      if (newReports.length > 0) {
        notified = true;
        delete inFlight[agentKey];
        watcher.close();
        clearInterval(poll);
        clearTimeout(timeout);
        if (onReady) onReady(newReports[0].name);
      }
    } catch {}
  };

  const watcher = fs.watch(cfg.outputDir, (event, filename) => {
    if (filename && (cfg.filePattern.test(filename)
        || (cfg.signalsFile && filename === path.basename(cfg.signalsFile)))) {
      // Small delay to let the file finish writing
      setTimeout(checkForNewPdf, 2000);
    }
  });

  // Polling fallback every 30s (fs.watch can miss events on some macOS configs)
  const poll = setInterval(checkForNewPdf, 30000);

  // Give up after 2 hours
  const timeout = setTimeout(() => {
    delete inFlight[agentKey];
    watcher.close();
    clearInterval(poll);
  }, 2 * 60 * 60 * 1000);

  return { started: true, pid: child.pid, script: scriptPath };
}

module.exports = { getAgentReports, getAgentHighlights, getSignals, getTermSeries,
                   getTermEvidence, muteTerm, runAgent, AGENT_CONFIG };
