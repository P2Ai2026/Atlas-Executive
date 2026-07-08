# Executive Assistant — app guide

A private, local macOS desktop app. Reads your Mail.app inbox, briefs you twice
a day, watches the market's fringe through the Signal Radar, and never sends
anything without you.

---

## The tabs

**Workspace**
- **Email Brief** — 10 AM & 6 PM digest of your inbox (local Ollama, `qwen2.5`):
  what needs attention, what's worth noting, what's noise. Includes agent
  highlights and the Signal Radar's top movers. Each item has ✓ (done) and
  Action → (send to Chat).
- **Chat** — follow up conversationally: check the calendar, prep draft replies,
  delete emails. Drafts are saved to Mail's Drafts folder for YOUR review.
- **Calendar** — next 7 days from Apple Calendar.
- **Sender Rules** — priority senders (always top of brief) and auto-delete.
- **The Paper Trail** — log of completed items, drafts, and calendar adds.
- **Library** — drop in documents (txt/md/pdf) for structured AI summaries,
  exact-phrase search, and "Ask the Library": grounded Q&A that answers only
  from your documents and cites which files it used. Docs live in
  `~/Desktop/Atlas Library/`. (Concepts adapted from the AI Operations Hub's
  summarizer/memory modules.)

**Agents**
- **📡 Signal Radar** — the daily fringe→mainstream scan across 16 podcasts.
  Each signal shows exact 7-day mentions vs a 3-week baseline, velocity,
  cross-show breadth, an 8-week trend sparkline, and a status:
  `FRINGE RISING` (loud but only 1-2 shows — the early warning) →
  `EMERGING` → `GOING MAINSTREAM` → `MAINSTREAM` (you're late).
  Click a row for evidence (which episodes, when, how many mentions).
  Click ✕ to mute a junk term permanently.
- **Podcast Intel** — the PDF briefs behind the radar, one per day with
  new episodes.
- **Distressed Stocks** — weekly SEC-filing/permit scanner (Mondays 10 AM).

**Configuration**
- **Profile** — your name/title (signs drafts) and key people (tone + priority).
- **Settings** — digest times, daily radar scan time (default 7:30 AM).

## Privacy & safety

| What | How |
|---|---|
| Email / Calendar | AppleScript → Mail.app / Calendar.app |
| AI | Ollama (`qwen2.5` app, `llama3` agents) — all local |
| Outbound email | **Drafts only, always.** Nothing is ever auto-sent |
| Keys/config | `~/.exec-assistant-config.json` — never in this repo |

## Run it

```bash
npm install
npm start
```

Requires macOS 12+, Node 18+, Ollama running. First run: allow the Mail.app and
Calendar.app automation prompts. Agent setup: see [agents/README.md](agents/README.md).

Data lives outside the repo: reports + signal history in
`~/Desktop/Agent 3- Podcast Reviews/` and `~/Desktop/Distress Reports/`.
