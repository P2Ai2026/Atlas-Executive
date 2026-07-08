from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

SOURCES = {
    "meeting_note": BASE / "meeting_notes",
    "meeting_report": BASE / "meeting_reports",
    "podcast_transcript": BASE / "podcast_transcripts",
    "podcast_report": BASE / "podcast_reports",
}

def load_memory_documents():
    documents = []

    for source_type, folder in SOURCES.items():
        if not folder.exists():
            continue

        for file in folder.glob("*"):
            if file.suffix.lower() not in [".txt", ".md"]:
                continue

            text = file.read_text(encoding="utf-8", errors="ignore")

            documents.append({
                "source_type": source_type,
                "file_name": file.name,
                "path": str(file),
                "text": text
            })

    return documents