from pathlib import Path
import subprocess

def load_all_transcripts(notes_folder):
    transcript_files = list(Path(notes_folder).glob("*.txt"))

    if not transcript_files:
        return "No transcripts found."

    combined = ""

    for file in transcript_files:
        text = file.read_text(encoding="utf-8", errors="ignore")
        combined += f"\n\n--- Transcript: {file.name} ---\n{text}"

    return combined

def ask_meeting_brain(notes_folder, question):
    all_transcripts = load_all_transcripts(notes_folder)

    prompt = f"""
You are Meeting Brain, an AI assistant that answers questions using the user's saved meeting transcripts.

Use only the transcript information provided.
If the answer is not found in the transcripts, say that you could not find it.

User question:
{question}

Saved transcripts:
{all_transcripts}
"""

    result = subprocess.run(
        ["ollama", "run", "llama3.2"],
        input=prompt,
        text=True,
        capture_output=True
    )

    return result.stdout.strip()