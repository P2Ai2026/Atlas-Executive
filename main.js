const { app, BrowserWindow, ipcMain, Notification, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { getMail, deleteMail, deleteMailBySenderName, createDraft, getCalendarSlots, getUpcomingEvents, addCalendarEvent } = require('./src/graph');
const { summarizeMail, chat } = require('./src/ai');
const { loadConfig, saveConfig } = require('./src/config');
const scheduler = require('./src/scheduler');
const { getAgentReports, getAgentHighlights, getSignals, runAgent, AGENT_CONFIG } = require('./src/agents');

let win;
let conversationHistory = [];
let lastDigest = null;
let lastSenderIndex = []; // [{ name, email }] from most recent fetch — for accurate delete_sender lookups
let pendingCalendarAdd = null; // { event, date, time, calendar, dayHint, briefCtx } awaiting user confirmation

// ── Paper Trail ───────────────────────────────────────────────────────────────
const TRAIL_FILE = path.join(os.homedir(), '.exec-assistant-papertrail.json');

function loadTrail() {
  try { return JSON.parse(fs.readFileSync(TRAIL_FILE, 'utf8')); } catch { return []; }
}

function saveTrail(entries) {
  const cutoff = Date.now() - 90 * 24 * 60 * 60 * 1000;
  const pruned = entries.filter(e => new Date(e.timestamp).getTime() > cutoff);
  fs.writeFileSync(TRAIL_FILE, JSON.stringify(pruned, null, 2));
}

function addTrailEntry(entry) {
  const trail = loadTrail();
  const full = { ...entry, id: Date.now() + Math.random(), timestamp: new Date().toISOString() };
  trail.unshift(full);
  saveTrail(trail);
  win?.webContents?.send('trail:update', full);
  return full;
}

ipcMain.handle('trail:get', () => loadTrail());
ipcMain.handle('trail:add', (_, entry) => { addTrailEntry(entry); return true; });
ipcMain.handle('trail:restore', (_, id) => {
  const trail = loadTrail();
  const idx = trail.findIndex(e => e.id === id);
  if (idx !== -1) trail.splice(idx, 1);
  saveTrail(trail);
  return true;
});

function createWindow() {
  win = new BrowserWindow({
    width: 900,
    height: 700,
    minWidth: 720,
    minHeight: 500,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0f0f13',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
  });
  win.loadFile('index.html');
}

function runScheduledAgent(key) {
  try {
    const cfg = AGENT_CONFIG[key];
    runAgent(key, (reportName) => {
      if (Notification.isSupported()) {
        new Notification({ title: `${cfg?.name || key} Report Ready`, body: reportName }).show();
      }
      win?.webContents?.send('agent:ready', { key, reportName });
      if (key === 'podcast') win?.webContents?.send('signals:new', getSignals());
    });
  } catch (err) {
    console.error(`Agent ${key} launch error:`, err.message);
  }
}

app.whenReady().then(() => {
  createWindow();
  scheduler.start(runDigest, runScheduledAgent);
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

// ── Auth ──────────────────────────────────────────────────────────────────────
ipcMain.handle('auth:start', async () => {
  const { startAuth } = require('./src/auth');
  const result = await startAuth();
  return result;
});

ipcMain.handle('auth:status', async () => {
  const { isAuthenticated } = require('./src/auth');
  return isAuthenticated();
});

// ── Config ────────────────────────────────────────────────────────────────────
ipcMain.handle('config:get', () => loadConfig());
ipcMain.handle('config:save', (_, cfg) => { saveConfig(cfg); return true; });

// ── Manual digest ─────────────────────────────────────────────────────────────
ipcMain.handle('digest:run', async () => {
  return await runDigest();
});

ipcMain.handle('digest:last', () => lastDigest);

// ── Chat ──────────────────────────────────────────────────────────────────────
ipcMain.handle('chat:send', async (_, userMessage) => {
  const cfg = loadConfig();
  const profile = { userName: cfg.userName, userTitle: cfg.userTitle, people: cfg.people || [] };

  // Check if user is confirming a pending calendar add
  if (pendingCalendarAdd && /^(yes|yeah|yep|sure|ok|do it|please|confirm|add it|go ahead)/i.test(userMessage.trim())) {
    const pca = pendingCalendarAdd;
    pendingCalendarAdd = null;
    try {
      const dayErr = verifyDayName(pca.dayHint, pca.date);
      if (dayErr) {
        const msg = `⚠️ ${dayErr} Please confirm the exact date manually before I add it.`;
        conversationHistory.push({ role: 'user', content: userMessage });
        conversationHistory.push({ role: 'assistant', content: msg });
        return msg;
      }
      await addCalendarEvent(pca.event, pca.date, pca.time, pca.calendar);
      addTrailEntry({ text: pca.briefCtx || pca.event, action: `Added "${pca.event}" to ${pca.calendar} calendar on ${pca.date}`, source: 'calendar' });
      const confirmed = `Done. "${pca.event}" has been added to your ${pca.calendar} calendar on ${pca.date} at ${pca.time}.`;
      conversationHistory.push({ role: 'user', content: userMessage });
      conversationHistory.push({ role: 'assistant', content: confirmed });
      if (conversationHistory.length > 40) conversationHistory = conversationHistory.slice(-40);
      return confirmed;
    } catch (err) {
      const errMsg = `Sorry, I couldn't add the event: ${err.message}`;
      conversationHistory.push({ role: 'user', content: userMessage });
      conversationHistory.push({ role: 'assistant', content: errMsg });
      return errMsg;
    }
  }

  // If user clearly declines a pending calendar add, clear it
  if (pendingCalendarAdd && /^(no|nope|cancel|skip|don't|dont)/i.test(userMessage.trim())) {
    pendingCalendarAdd = null;
  }

  conversationHistory.push({ role: 'user', content: userMessage });

  let context = lastDigest ? `\n\nLatest email digest:\n${lastDigest.raw}` : '';
  if (lastSenderIndex.length) {
    const senderLines = lastSenderIndex.map(s => `- "${s.name}" <${s.email}>`).join('\n');
    context += `\n\nEXACT SENDER ADDRESSES FROM INBOX (use these for delete_sender):\n${senderLines}`;
  }

  // If the user clicked "Action →" on a specific brief item, a [EMAIL_ID:xxx] tag is embedded in the message.
  // Inject the ID explicitly so the AI can use delete_email for that one message.
  const emailIdMatch = userMessage.match(/\[EMAIL_ID:([^\]]+)\]/);
  if (emailIdMatch) {
    context += `\n\nSPECIFIC EMAIL REFERENCED: id="${emailIdMatch[1]}" — if the user asks to delete or remove this email, use <action:delete_email id="${emailIdMatch[1]}">`;
  }

  const reply = await chat(conversationHistory, context, cfg.anthropicKey, profile);

  // Handle [DRAFT] blocks — create one draft per block
  let finalText = reply.text;
  const draftMessages = [];

  // Extract brief context if message starts with "Re: <ctx> — "
  const briefCtxMatch = userMessage.match(/^Re:\s+(.+?)\s+—\s*/);
  const briefCtx = briefCtxMatch ? briefCtxMatch[1] : null;

  // Never create drafts when the AI triggered a deletion — they are mutually exclusive
  if (reply.action === 'delete_email' || reply.action === 'delete_sender' || reply.action === 'delete_sender_name') reply.drafts = [];

  if (reply.drafts && reply.drafts.length > 0) {
    for (const d of reply.drafts) {
      try {
        await createDraft(d.to, d.subject, d.body, cfg);
        draftMessages.push(`Draft to ${d.to} saved to Mail Drafts.`);
        win?.webContents?.send('draft:ready', { to: d.to, subject: d.subject, body: d.body });
        addTrailEntry({ text: briefCtx || d.subject, action: `Draft created to ${d.to}`, source: 'draft' });
      } catch (err) {
        draftMessages.push(`Draft to ${d.to} failed: ${err.message}`);
      }
    }
    if (draftMessages.length > 0) {
      finalText = (finalText ? finalText + '\n\n' : '') + draftMessages.join('\n');
    }
  }

  // Handle legacy single action tag (check_calendar, ask_calendar, create_draft fallback)
  if (reply.action) {
    const actionResult = await handleAction(reply.action, reply.actionData, cfg);
    if (actionResult) finalText = (finalText ? finalText + '\n\n' : '') + actionResult;
  }

  conversationHistory.push({ role: 'assistant', content: finalText });

  if (conversationHistory.length > 40) conversationHistory = conversationHistory.slice(-40);

  return finalText;
});

ipcMain.handle('chat:clear', () => { conversationHistory = []; pendingCalendarAdd = null; return true; });

// ── Calendar ──────────────────────────────────────────────────────────────────
ipcMain.handle('calendar:get', async () => {
  return await getUpcomingEvents();
});

ipcMain.handle('calendar:add', async (_, { event, date, time, calendar }) => {
  await addCalendarEvent(event, date, time, calendar || 'Work');
  return true;
});

// ── Agent Hub ─────────────────────────────────────────────────────────────────
ipcMain.handle('agent:reports', (_, key) => getAgentReports(key));

ipcMain.handle('signals:get', () => getSignals());

ipcMain.handle('agent:open', (_, filePath) => {
  shell.openPath(filePath);
  return true;
});

ipcMain.handle('agent:run', (_, key) => {
  try {
    const cfg = AGENT_CONFIG[key];
    const result = runAgent(key, (reportName) => {
      // PDF appeared — fire macOS notification and update the renderer
      if (Notification.isSupported()) {
        new Notification({
          title: `${cfg?.name || key} Report Ready`,
          body: reportName,
        }).show();
      }
      win?.webContents?.send('agent:ready', { key, reportName });
      if (key === 'podcast') win?.webContents?.send('signals:new', getSignals());
    });
    if (result.alreadyRunning) return { error: 'This agent is already running — give it a few minutes.' };
    return result;
  } catch (err) {
    return { error: err.message };
  }
});

// ── Draft preview ─────────────────────────────────────────────────────────────
ipcMain.handle('draft:create', async (_, { to, subject, body }) => {
  const cfg = loadConfig();
  await createDraft(to, subject, body, cfg);
  return true;
});

// Verify that a named weekday actually matches a YYYY-MM-DD date string.
// Returns null if OK, or an error string if there's a mismatch.
function verifyDayName(dayHint, dateStr) {
  if (!dayHint || !dateStr) return null;
  const [year, month, day] = dateStr.split('-').map(Number);
  if (!year || !month || !day) return null;
  const actual = new Date(year, month - 1, day)
    .toLocaleDateString('en-US', { weekday: 'long' });
  const expected = dayHint.trim().replace(/^(this|next)\s+/i, '');
  if (expected && actual.toLowerCase() !== expected.toLowerCase()) {
    return `Day mismatch: the AI said "${expected}" but ${dateStr} is actually a ${actual}.`;
  }
  return null;
}

// ── Actions the AI can trigger ────────────────────────────────────────────────
async function handleAction(action, data, cfg) {
  if (action === 'check_calendar') {
    const slots = await getCalendarSlots(data.date, cfg);
    return `Free slots on ${data.date}: ${slots.join(', ')}`;
  }

  if (action === 'ask_calendar') {
    const calName = data.calendar || 'Work';
    const dayErr = verifyDayName(data.day, data.date);
    if (dayErr) {
      return `⚠️ ${dayErr} Please check the date before I add it.`;
    }
    pendingCalendarAdd = { event: data.event, date: data.date, time: data.time, calendar: calName, dayHint: data.day, briefCtx: null };
    return `Should I add "${data.event}" on ${data.date} at ${data.time} to your ${calName} calendar? Reply "yes" to confirm.`;
  }

  if (action === 'delete_email') {
    const msgId = (data.id || '').trim();
    if (!msgId) return 'No message ID specified.';
    const result = await deleteMail(msgId, cfg);
    if (result === 'not_found') return 'That email was not found in your inbox (it may have already been deleted).';
    return 'Done. That email has been removed from your inbox.';
  }

  if (action === 'delete_sender') {
    const targetAddr = (data.email || '').toLowerCase().trim();
    if (!targetAddr) return 'No sender address specified.';
    const emails = await getMail(cfg);
    const extractAddr = (s = '') => { const m = s.match(/<([^>]+)>/); return (m ? m[1] : s).toLowerCase(); };
    const matches = emails.filter(e => extractAddr(e.from?.emailAddress?.address) === targetAddr);
    if (!matches.length) return `No emails from ${targetAddr} found in your inbox.`;
    for (const e of matches) await deleteMail(e.id, cfg);
    return `Deleted ${matches.length} email${matches.length !== 1 ? 's' : ''} from ${targetAddr}.`;
  }

  if (action === 'delete_sender_name') {
    const nameQuery = (data.name || '').trim();
    if (!nameQuery) return 'No sender name specified.';
    const { count, addrs } = await deleteMailBySenderName(nameQuery);
    if (!count) return `No emails matching "${nameQuery}" found in your inbox.`;
    const unique = [...new Set(addrs)];
    const summary = unique.length <= 3 ? unique.join(', ') : `${unique.slice(0,3).join(', ')} and ${unique.length - 3} more`;
    return `Deleted ${count} email${count !== 1 ? 's' : ''} from: ${summary}.`;
  }

  if (action === 'add_calendar') {
    const calName = data.calendar || 'Work';
    const dayErr = verifyDayName(data.day, data.date);
    if (dayErr) {
      return `⚠️ ${dayErr} Please confirm the exact date manually.`;
    }
    await addCalendarEvent(data.event, data.date, data.time, calName);
    return `"${data.event}" has been added to your ${calName} calendar on ${data.date} at ${data.time}.`;
  }

  // Legacy single draft fallback (no [DRAFT] blocks found)
  if (action === 'create_draft') {
    const to      = data.to      || '';
    const subject = data.subject || '(no subject)';
    const body    = data.body    || '';
    if (!to) return 'I need a recipient email address to create a draft.';
    if (!body) return 'Could not extract email body — please try again.';
    await createDraft(to, subject, body, cfg);
    win?.webContents?.send('draft:ready', { to, subject, body });
    return `Draft saved to your Mail Drafts folder — addressed to ${to}. Review it before sending.`;
  }

  return '';
}

// ── Core digest runner ────────────────────────────────────────────────────────
async function runDigest() {
  const cfg = loadConfig();

  try {
    const { isAuthenticated } = require('./src/auth');
    if (!isAuthenticated()) return { error: 'Not authenticated with Microsoft.' };

    // 1. Fetch emails
    const emails = await getMail(cfg);

    // 2. Delete blocked senders
    const blocked = (cfg.blocklist || []).map(a => a.toLowerCase());
    const extractAddr = (s = '') => { const m = s.match(/<([^>]+)>/); return (m ? m[1] : s).toLowerCase(); };
    const toDelete = emails.filter(e => blocked.includes(extractAddr(e.from?.emailAddress?.address)));
    for (const e of toDelete) await deleteMail(e.id, cfg);

    // 3. Filter remaining
    const remaining = emails.filter(e => !toDelete.find(d => d.id === e.id));

    // 4. Summarise with Ollama, passing starlist and full profile for priority flagging
    const profile = { userName: cfg.userName, userTitle: cfg.userTitle, people: cfg.people || [] };
    const digest = await summarizeMail(remaining, null, cfg.starlist || [], profile);

    // Build sender index so chat always has exact FROM addresses
    lastSenderIndex = remaining.map(e => ({
      name:  e.from?.emailAddress?.name  || '',
      email: extractAddr(e.from?.emailAddress?.address || ''),
    }));

    // Append agent highlights if available
    let fullDigest = digest;
    try {
      const highlights = await getAgentHighlights();
      if (highlights.length) {
        fullDigest += `\n\n**🤖 Agent Updates**\n${highlights.join('\n')}`;
      }
    } catch {}

    const emailIndex = remaining.map(e => ({ id: e.id, subject: e.subject || '', from: e.from }));
    lastDigest = { text: fullDigest, raw: fullDigest, time: new Date().toISOString(), count: remaining.length, emails: emailIndex };

    // 5. Notify
    if (Notification.isSupported()) {
      new Notification({ title: 'Email Brief Ready', body: `${remaining.length} emails summarised.` }).show();
    }

    win?.webContents?.send('digest:new', lastDigest);
    return lastDigest;
  } catch (err) {
    console.error('Digest error:', err);
    return { error: err.message };
  }
}
