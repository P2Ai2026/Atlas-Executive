# Agents

Python agents that power the app's Agents tabs. The Electron app looks for
them **here first**, then falls back to legacy `~/Desktop` folders (for
machines that predate this repo layout).

| Agent | Entry point | Feeds | Schedule |
|---|---|---|---|
| Podcast Signal Scanner | `podcast/podcast_intel_agent.py` | Signal Radar tab + Podcast Intel tab | Daily 7:30 AM (app scheduler) |
| Distressed Stocks | `stocks/weekly_run.py` | Distressed Stocks tab | Mondays 10:00 AM |

## One-time setup (per agent)

Each agent gets its own virtualenv, created inside its folder — the app
auto-detects `agents/<name>/.venv` and uses it:

```bash
cd agents/podcast
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd ../stocks
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Also required on the machine:

- **Ollama** (https://ollama.com/download) with two models pulled:
  `ollama pull llama3` (agents) and `ollama pull qwen2.5` (the app's email brief/chat).
- macOS. First app run will ask for Mail.app / Calendar.app automation permission.

## Where output goes

By default reports land in `~/Desktop/Agent 3- Podcast Reviews/` and
`~/Desktop/Distress Reports/` (created automatically). The app passes
`PODCAST_OUTPUT_DIR` / `DISTRESS_OUTPUT_DIR` to the scripts, so changing
`outputDir` in `src/agents.js` moves everything consistently.

The podcast agent also maintains two JSON files in its output folder:
`signal_history.json` (per-episode term counts, 6-month rolling — the memory
behind the fringe→mainstream math) and `signals_latest.json` (what the Signal
Radar tab renders). If a junk term ever appears on the radar, flip it to
`"drop"` under `term_verdicts` in `signal_history.json`.

## House rules

- Agents only ever **open Mail drafts** — nothing is sent automatically.
- Whisper transcription runs locally; the first podcast scan of a new setup is
  slow (each backlog episode transcribed once, then cached).
