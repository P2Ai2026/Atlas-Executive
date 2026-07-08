# AI Operations Hub

AI Operations Hub is a local AI workspace for meetings, reports, and future agents.

## Features

- Drag-and-drop meeting audio upload
- Whisper transcription
- Local AI summaries with Ollama
- PDF report generation
- Meeting Brain chat across saved transcripts
- Searchable meeting history
- Dashboard metrics
- PDF downloads
- Podcast Intelligence placeholder

## How to Run

```bash
cd ~/Desktop/AI_Operations_Hub_v1
python3 -m streamlit run hub.py
```

## Requirements

Install Python packages:

```bash
python3 -m pip install -r requirements.txt
```

You also need Ollama installed and the local model available:

```bash
ollama pull llama3.2
```

## Version

v1.0 Clean Foundation

Current version: v1.1


## v1.1 Additions

- Podcast Intelligence page
- Investment Intelligence page
- Research brief framework
- Company/theme/risk extraction from saved text sources
