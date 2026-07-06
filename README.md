# Atlas-Executive

all agents and code for summer internship that aims to create insights into the ai infrastructure business and give an advantage to executives

## What's here

- **Electron app** (repo root) — Executive Assistant: Mail.app email briefs via
  local Ollama, calendar, draft-only email workflow, and the daily **Signal
  Radar** (fringe→mainstream trend detection across 16 podcasts). App details
  in [README-app.md](README-app.md).
- **`agents/`** — the Python agents behind the app's Agents tabs (podcast
  signal scanner, distressed-stocks scanner). Setup instructions in
  [agents/README.md](agents/README.md).

## Quick start

```bash
npm install
npm start
```

Requires macOS, Node 18+, and [Ollama](https://ollama.com/download) with
`qwen2.5` pulled. To enable the agent tabs, follow
[agents/README.md](agents/README.md).
