# Executive Assistant

A private, local macOS desktop app that reads your Mail.app inbox, summarises it twice daily using a local AI model, and lets you chat to follow up, check your calendar, and prepare draft replies — nothing ever leaves your machine.

---

## What it does

- **10 AM & 6 PM email brief** — Llama 3 (running locally via Ollama) reads your inbox and delivers a prioritised summary: what needs attention, what's worth noting, what's noise.
- **Block list** — any address you add gets auto-deleted on arrival, before it reaches your brief.
- **Chat interface** — follow up conversationally ("book a meeting with Sarah on Wednesday, prep the reply"). It checks Calendar.app and creates a draft in Mail.app for you to review.
- **Drafts only** — nothing is ever sent. All outbound action stops at a draft you manually review.

---

## Privacy

| What | How |
|------|-----|
| Email access | AppleScript → Mail.app (your existing setup) |
| Calendar access | AppleScript → Calendar.app |
| AI summarisation | Ollama + Llama 3, runs entirely on your Mac |
| Network | Zero — nothing leaves your machine |
| API keys | None needed |
| Cost | Free |

---

## Setup (2 steps)

### 1. Install Node.js
Download from https://nodejs.org (LTS version). This is the engine that runs the app — it doesn't touch your email.

### 2. Run it
```bash
cd exec-assistant
npm install
npm start
```

In the app:
1. Make sure the **Ollama app is open** (you should see it in your menu bar)
2. Go to **Settings** → add any addresses to the Block List → Save
3. Go to **Email Brief** → **Run Now**

**First run:** macOS will ask "Allow this app to control Mail.app?" and "...Calendar.app?" — click **Allow** both times. Standard macOS permission prompt, same as when any new app wants to access something.

---

## Requirements

- macOS 12+
- Ollama installed and running with `llama3` pulled (you have this ✓)
- Mail.app with your account already added (you have this ✓)
- Node.js 18+
