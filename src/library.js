/**
 * Library — local document intelligence.
 * Adapted from the AI Operations Hub's summarizer / memory / search modules
 * (Streamlit + `ollama run` version), rebuilt on this app's patterns:
 * qwen2.5 over HTTP, IPC-friendly functions, data outside the repo.
 *
 * Docs live in ~/Desktop/Atlas Library. Each summarized doc gets a sidecar
 * `<name>.analysis.json` next to it — the summary is cached, never recomputed
 * unless the user asks.
 */

const { execFile } = require('child_process');
const util = require('util');
const fs   = require('fs');
const path = require('path');
const os   = require('os');
const exec = util.promisify(execFile);

const OLLAMA_BASE = 'http://127.0.0.1:11434/api';
const LIB_DIR = path.join(os.homedir(), 'Desktop', 'Atlas Library');
const DOC_EXTS = ['.txt', '.md', '.pdf'];

const CONTEXT_CHAR_BUDGET = 20000;   // stay inside qwen2.5's context window

function ensureDir() {
  fs.mkdirSync(LIB_DIR, { recursive: true });
  return LIB_DIR;
}

function sidecarPath(name) {
  return path.join(LIB_DIR, name + '.analysis.json');
}

// ── listing / importing ───────────────────────────────────────────────────────

function listDocs() {
  ensureDir();
  return fs.readdirSync(LIB_DIR)
    .filter(f => DOC_EXTS.includes(path.extname(f).toLowerCase()))
    .map(f => {
      const stat = fs.statSync(path.join(LIB_DIR, f));
      let summary = null;
      try { summary = JSON.parse(fs.readFileSync(sidecarPath(f), 'utf8')); } catch {}
      return {
        name: f,
        path: path.join(LIB_DIR, f),
        mtime: stat.mtime.toISOString(),
        sizeKb: Math.max(1, Math.round(stat.size / 1024)),
        hasSummary: !!summary,
        summary: summary?.summary || null,
        summarizedAt: summary?.generated || null,
      };
    })
    .sort((a, b) => b.mtime.localeCompare(a.mtime));
}

function importFiles(paths) {
  ensureDir();
  const added = [];
  for (const p of paths || []) {
    if (!DOC_EXTS.includes(path.extname(p).toLowerCase())) continue;
    const dest = path.join(LIB_DIR, path.basename(p));
    try { fs.copyFileSync(p, dest); added.push(path.basename(p)); } catch {}
  }
  return { added, docs: listDocs() };
}

// ── text extraction ───────────────────────────────────────────────────────────

async function getDocText(name) {
  const full = path.join(LIB_DIR, name);
  const ext = path.extname(name).toLowerCase();
  if (ext === '.txt' || ext === '.md') {
    return fs.readFileSync(full, 'utf8');
  }
  if (ext === '.pdf') {
    try {
      const { stdout } = await exec('pdftotext', [full, '-']);
      if (stdout.trim().length > 50) return stdout.trim();
    } catch {}
    try {
      const { stdout } = await exec('strings', [full]);
      return stdout.split('\n').filter(l => l.trim().length > 6 && /[a-zA-Z]{3,}/.test(l)).join('\n');
    } catch {}
  }
  return '';
}

// ── Ollama ────────────────────────────────────────────────────────────────────

async function ollama(system, user) {
  const res = await fetch(`${OLLAMA_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'qwen2.5',
      stream: false,
      messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
    }),
  });
  if (!res.ok) throw new Error(`Ollama error ${res.status}`);
  return (await res.json()).message?.content || '';
}

// ── summarize (his summarizer.py concept, business-flavored) ─────────────────

async function summarizeDoc(name) {
  const text = await getDocText(name);
  if (!text || text.length < 50) throw new Error('Could not extract readable text from this document.');
  const summary = await ollama(
    'You are a sharp business analyst producing a document brief for an executive in the ' +
    'AI-/data-center-infrastructure business. Be specific and faithful to the document; ' +
    'if a section has nothing, write "None identified."',
    `Summarize this document with EXACTLY these sections:\n` +
    `EXECUTIVE SUMMARY: 2-4 sentences.\n` +
    `KEY POINTS: 3-6 bullets.\n` +
    `COMPANIES & TECHNOLOGIES: bullets naming specific players/tech mentioned.\n` +
    `ACTION ITEMS: bullets of anything requiring follow-up.\n` +
    `RISKS & OPEN QUESTIONS: 1-3 bullets.\n\n` +
    `Document (${name}):\n\n${text.slice(0, CONTEXT_CHAR_BUDGET)}`
  );
  const payload = { summary, generated: new Date().toISOString() };
  fs.writeFileSync(sidecarPath(name), JSON.stringify(payload, null, 1));
  return payload;
}

// ── search (his search.py concept: snippets with context) ────────────────────

async function searchDocs(term) {
  const q = (term || '').toLowerCase().trim();
  if (!q) return [];
  const hits = [];
  for (const doc of listDocs()) {
    let text = '';
    try { text = await getDocText(doc.name); } catch { continue; }
    const lower = text.toLowerCase();
    let idx = lower.indexOf(q);
    let found = 0;
    while (idx !== -1 && found < 3) {
      const start = Math.max(0, idx - 200);
      const end = Math.min(text.length, idx + q.length + 200);
      hits.push({ name: doc.name, snippet: text.slice(start, end).replace(/\s+/g, ' ') });
      found++;
      idx = lower.indexOf(q, idx + q.length);
    }
  }
  return hits;
}

// ── ask the library (his memory/prompts.py concept: grounded, cites sources) ─

async function askLibrary(question) {
  const docs = listDocs();
  if (!docs.length) return 'The library is empty — add some documents first.';

  // Rank docs by term overlap with the question; full text for the top few,
  // cached summaries for the rest, all within the context budget.
  const qWords = question.toLowerCase().split(/\W+/).filter(w => w.length > 3);
  const scored = [];
  for (const doc of docs) {
    let text = '';
    try { text = await getDocText(doc.name); } catch {}
    const lower = text.toLowerCase();
    const score = qWords.reduce((n, w) => n + (lower.includes(w) ? 1 : 0), 0);
    scored.push({ doc, text, score });
  }
  scored.sort((a, b) => b.score - a.score);

  let context = '';
  let i = 1;
  for (const { doc, text } of scored) {
    const chunk = context.length < CONTEXT_CHAR_BUDGET * 0.7 && text
      ? text.slice(0, 6000)
      : (doc.summary || '').slice(0, 1500);
    if (!chunk) continue;
    const block = `\nSOURCE ${i} — ${doc.name}\n${chunk}\n`;
    if (context.length + block.length > CONTEXT_CHAR_BUDGET) break;
    context += block;
    i++;
  }

  return await ollama(
    'You are the Library — a local research assistant. Answer ONLY from the sources ' +
    'provided. If they do not contain the answer, say so plainly. End with a ' +
    '"Sources:" line listing the file names you actually used.',
    `Question: ${question}\n\nSources:\n${context}`
  );
}

module.exports = { LIB_DIR, listDocs, importFiles, summarizeDoc, searchDocs, askLibrary };
