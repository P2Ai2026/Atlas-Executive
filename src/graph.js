/**
 * Mail & Calendar via AppleScript → Mail.app + Calendar.app
 * No API keys, no OAuth, no Azure. Talks to whatever accounts
 * you already have set up in Mail.app on your Mac.
 */

const { execFile } = require('child_process');
const util = require('util');
const exec = util.promisify(execFile);

async function osascript(script) {
  const { stdout } = await exec('osascript', ['-e', script]);
  return stdout.trim();
}

// Run a longer multi-line AppleScript from a heredoc string
async function osascriptML(script) {
  const { stdout } = await exec('osascript', ['-ss', '-e', script]);
  return stdout.trim();
}

// ── Mail ──────────────────────────────────────────────────────────────────────

async function getMail(cfg) {
  const count = cfg.emailFetchCount || 60;

  // Fetch messages from every account's "Inbox" mailbox.
  // "inbox of acct" fails for Exchange/Outlook accounts; "mailbox 'Inbox' of acct"
  // is the correct approach. The global "every mailbox whose name is 'Inbox'"
  // also fails — it doesn't search inside account mailboxes.
  const script = `
    set NL to ASCII character 10
    set output to ""
    tell application "Mail"
      repeat with acct in every account
        try
          set mb to mailbox "Inbox" of acct
          set msgs to (messages of mb)
          set msgCount to count of msgs
          if msgCount > ${count} then set msgCount to ${count}
          repeat with i from 1 to msgCount
            set m to message i of mb
            set mId to message id of m
            set mSubject to subject of m
            set mSender to sender of m
            set mDate to date received of m as string
            set mRead to read status of m
            set mPreview to ""
            try
              set mPreview to (content of m)
              if (count of mPreview) > 300 then
                set mPreview to (text 1 thru 300 of mPreview)
              end if
            end try
            set output to output & "---MSG---" & NL
            set output to output & "ID:" & mId & NL
            set output to output & "SUBJECT:" & mSubject & NL
            set output to output & "FROM:" & mSender & NL
            set output to output & "DATE:" & mDate & NL
            set output to output & "READ:" & mRead & NL
            set output to output & "PREVIEW:" & mPreview & NL
          end repeat
        end try
      end repeat
    end tell
    return output
  `;

  const raw = await osascript(script);
  if (!raw) return [];

  // Normalize any stray \r from AppleScript to \n
  const normalized = raw.replace(/\r\n?/g, '\n');

  const emails = [];
  const blocks = normalized.split('---MSG---').filter(b => b.trim());
  for (const block of blocks) {
    const get = (key) => {
      const match = block.match(new RegExp(`${key}:(.+?)(?=\\n[A-Z]+:|\\n?$)`, 's'));
      return match ? match[1].trim() : '';
    };
    const id = get('ID');
    if (!id) continue;
    emails.push({
      id,
      subject: get('SUBJECT'),
      from: { emailAddress: { address: get('FROM') } },
      receivedDateTime: get('DATE'),
      isRead: get('READ') === 'true',
      bodyPreview: get('PREVIEW').replace(/\n/g, ' '),
    });
  }
  return emails;
}

async function deleteMail(id, cfg) {
  // Use sender-name deletion as the reliable path when called from digest blocklist.
  // For direct ID-based deletion, match by message id using whose clause.
  const safeId = id.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const script = `
    tell application "Mail"
      set targetId to "${safeId}"
      repeat with acct in every account
        try
          set mb to mailbox "Inbox" of acct
          set matchMsgs to (every message of mb whose message id is targetId)
          if (count of matchMsgs) > 0 then
            set trashBox to missing value
            try
              set trashBox to mailbox "Deleted Items" of acct
            end try
            if trashBox is missing value then
              try
                set trashBox to mailbox "Trash" of acct
              end try
            end if
            if trashBox is not missing value then
              move (item 1 of matchMsgs) to trashBox
            else
              delete (item 1 of matchMsgs)
            end if
            return "deleted"
          end if
        end try
      end repeat
    end tell
    return "not_found"
  `;
  return await osascript(script);
}

// Delete all inbox messages where the sender field contains nameQuery.
// AppleScript string ops are case-insensitive by default — no shell call needed.
// Uses `whose sender contains` for a stable reference list, then iterates in reverse
// to avoid index-shifting bugs when deleting.
async function deleteMailBySenderName(nameQuery) {
  const safeName = nameQuery.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const script = `
    set deleted to 0
    set addrStr to ""
    tell application "Mail"
      repeat with acct in every account
        try
          set mb to mailbox "Inbox" of acct
          set matchMsgs to (every message of mb whose sender contains "${safeName}")
          set matchCount to count of matchMsgs
          -- Find the trash/deleted-items mailbox for this account
          set trashBox to missing value
          try
            set trashBox to mailbox "Deleted Items" of acct
          end try
          if trashBox is missing value then
            try
              set trashBox to mailbox "Trash" of acct
            end try
          end if
          repeat with i from matchCount to 1 by -1
            set m to item i of matchMsgs
            set addrStr to addrStr & (sender of m) & "|||"
            if trashBox is not missing value then
              move m to trashBox
            else
              delete m
            end if
            set deleted to deleted + 1
          end repeat
        end try
      end repeat
    end tell
    return (deleted as string) & ":::" & addrStr
  `;
  const result = await osascript(script);
  const sepIdx = result.indexOf(':::');
  const countStr = result.slice(0, sepIdx);
  const addrStr  = result.slice(sepIdx + 3);
  const count = parseInt(countStr, 10) || 0;
  const addrs = addrStr ? addrStr.split('|||').filter(Boolean) : [];
  return { count, addrs };
}

async function createDraft(to, subject, body, cfg) {
  // Write body to a temp file to avoid escaping nightmares in AppleScript
  const os = require('os');
  const fs = require('fs');
  const tmpFile = require('path').join(os.tmpdir(), `draft_${Date.now()}.txt`);
  // Convert literal \n sequences and normalize line endings
  const cleanBody = body.replace(/\\n/g, '\n').replace(/\\t/g, '\t');
  fs.writeFileSync(tmpFile, cleanBody, 'utf8');

  const safeSubject = subject.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const safeTo = to.replace(/"/g, '\\"');
  const safeTmp = tmpFile.replace(/"/g, '\\"');

  const script = `
    set bodyText to (read POSIX file "${safeTmp}" as «class utf8»)
    tell application "Mail"
      set newMsg to make new outgoing message with properties ¬
        {subject:"${safeSubject}", content:bodyText, visible:true}
      tell newMsg
        make new to recipient with properties {address:"${safeTo}"}
      end tell
      save newMsg
    end tell
  `;
  await osascript(script);
  // Clean up temp file
  try { fs.unlinkSync(tmpFile); } catch {}
}

// ── Calendar ──────────────────────────────────────────────────────────────────

async function getCalendarSlots(dateStr, cfg) {
  // Ensure Calendar.app is running
  try {
    await exec('open', ['-a', 'Calendar']);
    for (let i = 0; i < 10; i++) {
      try { await exec('osascript', ['-e', 'tell application "Calendar" to name of every calendar']); break; }
      catch { await new Promise(r => setTimeout(r, 500)); }
    }
  } catch {}

  const target = new Date(dateStr);
  const month = target.getMonth() + 1;
  const day = target.getDate();
  const year = target.getFullYear();

  const script = `
    set targetDate to current date
    set month of targetDate to ${month}
    set day of targetDate to ${day}
    set year of targetDate to ${year}
    set time of targetDate to 0

    set dayStart to targetDate
    set dayEnd to targetDate + (86400 - 1)

    set output to ""
    tell application "Calendar"
      repeat with cal in every calendar
        set evts to (every event of cal whose start date >= dayStart and start date <= dayEnd)
        repeat with e in evts
          set eStart to start date of e as string
          set eEnd to end date of e as string
          set output to output & eStart & "|" & eEnd & return
        end repeat
      end repeat
    end tell
    return output
  `;

  let busyRaw = '';
  try { busyRaw = await osascript(script); } catch {}

  const busy = [];
  for (const line of busyRaw.split('\n').filter(Boolean)) {
    const [s, e] = line.split('|');
    if (s && e) busy.push({ s: new Date(s), e: new Date(e) });
  }

  // Generate 30-min slots 8am–6pm and remove busy ones
  const slots = [];
  for (let h = 8; h < 18; h++) {
    for (let m = 0; m < 60; m += 30) {
      const slotStart = new Date(target);
      slotStart.setHours(h, m, 0, 0);
      const slotEnd = new Date(slotStart.getTime() + 30 * 60000);
      const conflict = busy.some(b => slotStart < b.e && slotEnd > b.s);
      if (!conflict) slots.push(`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`);
    }
  }
  return slots.slice(0, 6);
}


// Get events from Calendar.app for today + next 7 days
async function getUpcomingEvents() {
  // Ensure Calendar.app is running before querying — a cold app returns -600.
  // We open it via the shell (which has the right permissions), wait for it to
  // be ready, then query via AppleScript.
  try {
    await exec('open', ['-a', 'Calendar']);
    // Wait up to 5 s for Calendar to respond to Apple Events
    for (let i = 0; i < 10; i++) {
      try {
        await exec('osascript', ['-e', 'tell application "Calendar" to name of every calendar']);
        break; // it's ready
      } catch {
        await new Promise(r => setTimeout(r, 500));
      }
    }
  } catch {}

  const script = `
    set today to current date
    set time of today to 0
    set weekEnd to today + (7 * 86400)

    set output to ""
    tell application "Calendar"
      repeat with cal in every calendar
        set calName to name of cal
        set evts to (every event of cal whose start date >= today and start date <= weekEnd)
        repeat with e in evts
          set eTitle to summary of e
          set eStart to start date of e
          set eDate to (short date string of eStart)
          set eTime to time string of eStart
          set output to output & eDate & "||" & eTime & "||" & eTitle & "||" & calName & return
        end repeat
      end repeat
    end tell
    return output
  `;

  let raw = '';
  try {
    const { execFile } = require('child_process');
    const { promisify } = require('util');
    const exec = promisify(execFile);
    const { stdout } = await exec('osascript', ['-e', script]);
    raw = stdout.trim();
  } catch (e) {
    throw new Error('Calendar access failed: ' + e.message);
  }

  const events = [];
  for (const line of raw.split('\n').filter(Boolean)) {
    const [date, time, title, calendar] = line.split('||');
    if (date && title) {
      events.push({ date: date.trim(), time: time?.trim() || 'All day', title: title.trim(), calendar: calendar?.trim() || '' });
    }
  }

  // Sort by date then time
  events.sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time));
  return events;
}

async function addCalendarEvent(name, dateStr, timeStr, calendarName = 'Work') {
  try {
    await exec('open', ['-a', 'Calendar']);
    for (let i = 0; i < 10; i++) {
      try { await exec('osascript', ['-e', 'tell application "Calendar" to name of every calendar']); break; }
      catch { await new Promise(r => setTimeout(r, 500)); }
    }
  } catch {}

  const [year, month, day] = dateStr.split('-').map(Number);
  const [hour, minute] = (timeStr || '09:00').split(':').map(Number);
  const safeName = name.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const safeCal = calendarName.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

  const script = `
    set startDate to current date
    set year of startDate to ${year}
    set month of startDate to ${month}
    set day of startDate to ${day}
    set hours of startDate to ${hour}
    set minutes of startDate to ${minute}
    set seconds of startDate to 0
    set endDate to startDate + 3600
    tell application "Calendar"
      try
        tell calendar "${safeCal}"
          make new event with properties {summary:"${safeName}", start date:startDate, end date:endDate}
        end tell
        return "OK"
      on error
        tell first calendar
          make new event with properties {summary:"${safeName}", start date:startDate, end date:endDate}
        end tell
        return "OK_FALLBACK"
      end try
    end tell
  `;
  return await osascript(script);
}

module.exports = { getMail, deleteMail, deleteMailBySenderName, createDraft, getCalendarSlots, getUpcomingEvents, addCalendarEvent };
