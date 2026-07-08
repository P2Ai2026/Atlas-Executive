/**
 * AI layer — uses local Ollama (qwen2.5).
 * Everything stays on your machine. No API keys. No cost. No data leaving.
 */

const OLLAMA_BASE = 'http://127.0.0.1:11434/api';

// Pre-process text, replacing vague day references with exact dates in code
// so the model never has to calculate dates itself.
function resolveDates(text) {
  if (!text) return text;
  const today = new Date();
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

  return text.replace(
    /\b(this\s+|next\s+)?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b/gi,
    (match, qualifier, dayName) => {
      const targetDay = days.findIndex(d => d.toLowerCase() === dayName.toLowerCase());
      const todayDay  = today.getDay();
      let daysAhead   = targetDay - todayDay;
      if (daysAhead <= 0 || qualifier?.toLowerCase().trim() === 'next') {
        daysAhead += 7;
      }
      const targetDate = new Date(today);
      targetDate.setDate(today.getDate() + daysAhead);
      return targetDate.toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      });
    }
  );
}

async function ollamaChat(system, messages, model = 'qwen2.5') {
  const res = await fetch(`${OLLAMA_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      stream: false,
      messages: [
        { role: 'system', content: system },
        ...messages,
      ],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Ollama error ${res.status}: ${err}`);
  }

  const data = await res.json();
  return data.message?.content || '';
}

// Build a people context block for the AI
function buildPeopleContext(people = []) {
  if (!people.length) return '';
  const lines = people.map(p =>
    `- ${p.name} <${p.email}>: ${p.relationship}, Priority: ${p.priority}`
  );
  return `\n\nKNOWN CONTACTS:\n${lines.join('\n')}`;
}

// Summarise inbox into an executive digest
async function summarizeMail(emails, _apiKey, starlist = [], profile = {}) {
  if (!emails.length) return 'No emails in your inbox.';

  const people = profile.people || [];

  // Resolve day references in subject and preview before the AI ever sees them
  const emailList = emails.map((e, i) =>
    `[${i + 1}] FROM: ${e.from?.emailAddress?.address || 'unknown'}\n` +
    `SUBJECT: ${resolveDates(e.subject || '(no subject)')}\n` +
    `PREVIEW: ${resolveDates(e.bodyPreview?.slice(0, 200) || '')}\n` +
    `RECEIVED: ${e.receivedDateTime}`
  ).join('\n\n');

  // Build priority note from starlist + people marked Critical/High
  const criticalEmails = [
    ...starlist,
    ...people.filter(p => p.priority === 'Critical' || p.priority === 'High').map(p => p.email.toLowerCase()),
  ].filter((v, i, a) => a.indexOf(v) === i);

  const priorityNote = criticalEmails.length
    ? `\n\nALWAYS ESCALATE TO 🔴 if from: ${criticalEmails.join(', ')}`
    : '';

  const bossEmails = people
    .filter(p => p.relationship === 'Boss' || p.relationship === 'Executive')
    .map(p => p.email.toLowerCase());
  const mandatoryNote = bossEmails.length
    ? `\n\nMANDATORY: Any meeting or event requested by ${bossEmails.join(', ')} is MANDATORY and must be flagged as such.`
    : '';

  const system = `You are a sharp executive assistant preparing a twice-daily email brief for a busy executive.
Distill what matters, surface anything requiring attention or decision, and make it scannable in under 2 minutes.${priorityNote}${mandatoryNote}

Format your brief using these three sections. Output the header line exactly as shown, with nothing after it on the same line:

**🔴 Needs Your Attention**
- Sender Name (Subject keyword): 2-3 sentences of real context — what they want, any key details, and whether the meeting/event is MANDATORY or OPTIONAL. → Specific action to take.

**🟡 Worth Noting**
- Sender Name (Subject keyword): 2-3 sentences of real context. → Specific action to take.

**⚪ Low Priority**
- Sender Name (Subject keyword): Brief context. → Action or "No action needed."

FORMAT RULES:
- Output ONLY the three section headers above — do not add any description or subtitle after them
- Each email is ONE bullet starting with "- "
- Write 2-3 sentences of genuine context per item: who, what they want, key details
- Dates in the email content are already resolved to exact dates — copy them as-is, do not recalculate
- For meetings from Boss/Executive contacts: state MANDATORY. From others: OPTIONAL.
- End every bullet with → and a specific action
- No sub-bullets, no labeled fields like "Subject:" or "FROM:"${buildPeopleContext(people)}`;

  const text = await ollamaChat(system, [
    { role: 'user', content: `Here are my inbox emails:\n\n${emailList}\n\nPrepare my executive brief.` }
  ]);

  return text;
}

// Parse [DRAFT]...[/DRAFT] blocks from the model's response
function parseDraftBlocks(text) {
  const drafts = [];
  const re = /\[DRAFT\]([\s\S]*?)\[\/DRAFT\]/gi;
  let m;
  while ((m = re.exec(text)) !== null) {
    const block = m[1].trim();
    const lines = block.split('\n');
    let to = '', subject = '';
    let headersDone = false;
    let bodyLines = [];
    for (const line of lines) {
      if (!headersDone) {
        if (line.startsWith('To:')) { to = line.slice(3).trim(); continue; }
        if (line.startsWith('Subject:')) { subject = line.slice(8).trim(); continue; }
        if (line.trim() === '' && (to || subject)) { headersDone = true; continue; }
      } else {
        bodyLines.push(line);
      }
    }
    if (!headersDone && lines.length > 2) {
      bodyLines = lines.filter(l => !l.startsWith('To:') && !l.startsWith('Subject:'));
    }
    const body = bodyLines.join('\n').trim();
    if (to && body) drafts.push({ to, subject: subject || '(no subject)', body });
  }
  return drafts;
}

// Conversational chat with context of last digest
async function chat(history, digestContext, _apiKey, profile = {}) {
  const userName = profile.userName || 'the executive';
  const userTitle = profile.userTitle ? ` (${profile.userTitle})` : '';
  const people = profile.people || [];

  // Resolve dates in the latest user message before it reaches the model
  const resolvedHistory = history.map((msg, i) => {
    if (i === history.length - 1 && msg.role === 'user') {
      return { ...msg, content: resolveDates(msg.content) };
    }
    return msg;
  });

  // Build tone hints per relationship
  const toneHints = [];
  for (const p of people) {
    if (p.relationship === 'Boss' || p.relationship === 'Executive') {
      toneHints.push(`${p.name} <${p.email}>: use formal, respectful tone`);
    } else if (p.relationship === 'Friend' || p.relationship === 'Family') {
      toneHints.push(`${p.name} <${p.email}>: use casual, warm tone`);
    } else if (p.relationship === 'Client') {
      toneHints.push(`${p.name} <${p.email}>: use professional, polite tone`);
    }
  }
  const toneNote = toneHints.length
    ? `\n\nEMAIL TONE GUIDE:\n${toneHints.join('\n')}`
    : '';

  const system = `You are a concise executive assistant for ${userName}${userTitle}. You help follow up on emails, check the calendar, and prepare draft replies.

SIGN-OFF: Every draft must sign off with "${userName}" — never use "[Your Name]" or any placeholder.

DRAFTING EMAILS:
When creating email drafts, format each draft exactly like this:

[DRAFT]
To: recipient@email.com
Subject: Subject line here

Dear [Recipient Name],

First paragraph of the email.

Second paragraph if needed.

Best regards,
${userName}
[/DRAFT]

CRITICAL RULES FOR DRAFTS:
- One [DRAFT]...[/DRAFT] block per recipient — NEVER combine multiple people's emails into one block
- Always include a blank line between the Subject: header and the greeting
- Always include proper paragraph breaks (blank lines between paragraphs)
- Each draft must be complete and self-contained
- If emailing multiple people, create multiple separate [DRAFT] blocks, one per person
- NEVER use "PART 1:" or "PART 2:" — use separate [DRAFT] blocks instead

CALENDAR:
- To check availability: <action:check_calendar date="YYYY-MM-DD">
- To suggest adding an event to calendar: <action:ask_calendar event="Event Name" date="YYYY-MM-DD" time="HH:MM" calendar="Work">
  Use this when you identify a meeting, ceremony, or deadline that should go on the calendar.
  Place it on its own line at the end of your response.

INBOX MANAGEMENT:
- To delete ONE specific email (when the user says "delete this email" or "remove this one" via the Action button): <action:delete_email id="MESSAGE_ID">
  The specific email's ID is provided in context as SPECIFIC EMAIL REFERENCED. Always prefer this for single-email deletions.
- To delete ALL emails from a known exact address (user says "delete all emails from X" or "delete everything from X"): <action:delete_sender email="exact@address.com">
  Use the EXACT sender address from the "EXACT SENDER ADDRESSES FROM INBOX" list — never guess an address.
- To delete ALL emails by sender name (user explicitly says "delete all from X" or "remove everything from X"): <action:delete_sender_name name="Anthropic">
  ONLY use this for bulk deletion when the user wants ALL emails from a sender gone.
- NEVER use delete_sender or delete_sender_name when the user is asking about one specific email — use delete_email with the provided ID.
- Place the action on its own line at the end of your response.
- NEVER draft an email to manage the user's inbox. Deletion and inbox management happen via AppleScript directly.
- Inbox management requests (delete, remove, clear) must ALWAYS use an action tag, never a [DRAFT] block.
- CRITICAL: If the user asks to delete, remove, or clean up emails, ONLY use a delete action — never also create a draft. These are mutually exclusive — never combine them.

OTHER RULES:
- NEVER send emails — drafts only, always
- Keep non-draft responses brief and to the point
- Dates in the conversation are already resolved to exact dates — use them as-is, do not recalculate
- When suggesting a meeting time, pick the first free slot available${toneNote}${digestContext ? '\n\n' + digestContext : ''}`;

  const raw = await ollamaChat(system, resolvedHistory);

  const drafts = parseDraftBlocks(raw);

  const actionMatch = raw.match(/[<\[](action:(\w+)([^>\]]*?))[>\]]/);
  let action = null;
  let actionData = {};

  let cleanText = raw
    .replace(/<action:[^>]+>/g, '')
    .replace(/\[action:[^\]]+\]/g, '')
    .replace(/\[DRAFT\][\s\S]*?\[\/DRAFT\]/gi, '')
    .trim();

  if (actionMatch) {
    action = actionMatch[2];
    const attrStr = actionMatch[3];
    const attrs = [...attrStr.matchAll(/(\w+)="([^"]*)"/g)];
    for (const [, key, val] of attrs) actionData[key] = val;
  }

  if (drafts.length === 0 && action === 'create_draft') {
    const bodyText = raw
      .replace(/<action:[^>]+>/g, '')
      .replace(/\[action:[^\]]+\]/g, '')
      .replace(/^(here'?s?\s+(the\s+)?draft[:\s]*)/i, '')
      .trim();
    actionData.body = bodyText;
  }

  return { text: cleanText, action, actionData, drafts };
}

module.exports = { summarizeMail, chat };
