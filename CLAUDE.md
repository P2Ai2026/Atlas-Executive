# Atlas-Executive — instructions for Claude Code

## What this is

An Electron desktop app ("Executive Assistant") + Python agents for an AI-
infrastructure business. Mission: early-warning market intelligence — find
signals at the fringe before they go mainstream. The Signal Radar tab is the
core product.

## Layout

- Repo root: the Electron app (`main.js`, `preload.js`, `index.html`, `src/`).
  Plain JS, no bundler, no framework — `index.html` holds all renderer UI/JS.
- `agents/podcast/` — daily podcast signal scanner (LangGraph + local Ollama).
  Writes `signals_latest.json` (read by the app) and `signal_history.json`
  (per-episode term counts — the memory behind velocity/breadth math).
- `agents/stocks/` — weekly SEC-filing scanner (`weekly_run.py` entry).
- Each agent has its own `.venv` (gitignored) + `requirements.txt`.

## Hard rules

1. **Never send email.** AppleScript may `save`/create drafts only — never the
   `send` command. All outbound stops at a draft the human reviews. No exceptions.
2. **No secrets in the repo.** Keys/config live in `~/.exec-assistant-config.json`.
3. **Data stays out of git**: reports, signal history, transcript caches live in
   `~/Desktop/Agent 3- Podcast Reviews/` and `~/Desktop/Distress Reports/`.
4. **Signal counts are computed in code, not by the model.** LLMs may nominate
   terms; counting happens with regex on transcripts. Keep it that way — the
   numbers must be real. Deterministic routing in agent graphs; token budgets
   and iteration caps stay.

## Conventions

- All AI calls go to local Ollama (`qwen2.5` for the app, `llama3` for agents).
  No cloud API calls without the user's explicit say-so.
- Renderer HTML is built with template strings — escape all untrusted content
  (email text, model output, feed titles) with `escapeHtml`/`escAttr` before
  it reaches `innerHTML`.
- After JS changes run `node --check` on touched files and parse the
  `index.html` script block; after Python changes run `py_compile`. Verify the
  app boots with `npm start` before committing.
- This machine may also have legacy copies of this code on the Desktop
  (`exec-assistant-2`, `internship`, `Agent 1- Distressed Stocks`) — those are
  frozen backups. Only edit this repo.
