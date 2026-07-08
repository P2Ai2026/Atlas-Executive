# Atlas-Executive

All agents and code for summer internship that aims to create insights into the AI infrastructure business and give an advantage to executives.

## What's here

- **Electron app** (repo root) — Executive Assistant: Mail.app email briefs via
  local Ollama, calendar, draft-only email workflow, and the daily **Signal
  Radar** (fringe→mainstream trend detection across 16 podcasts). App details
  in [README-app.md](README-app.md).
- **`agents/`** — the Python agents behind the app's Agents tabs (podcast
  signal scanner, distressed-stocks scanner). Setup instructions in
  [agents/README.md](agents/README.md).
- **AI Operations Hub** — a local Streamlit AI workspace for meetings, reports,
  and future agents. See details below.

## Quick start (Electron app)

```bash
npm install
npm start
```

Requires macOS, Node 18+, and [Ollama](https://ollama.com/download) with
`qwen2.5` pulled. To enable the agent tabs, follow
[agents/README.md](agents/README.md).

## Quick start (AI Operations Hub - Streamlit)

```bash
cd ~/Desktop/Atlas-Executive
python3 -m streamlit run hub.py
```

### Requirements

Install Python packages:

```bash
python3 -m pip install -r requirements.txt
```

You also need Ollama installed and the local model available:

```bash
ollama pull llama3.2
```

### Features

- Drag-and-drop meeting audio upload
- Whisper transcription
- Local AI summaries with Ollama
- PDF report generation
- Meeting Brain chat across saved transcripts
- Searchable meeting history
- Dashboard metrics
- PDF downloads
- Podcast Intelligence placeholder
- Investment Intelligence page
- Research brief framework
- Company/theme/risk extraction from saved text sources

### Version

Current version: v1.1
