from pathlib import Path
from datetime import datetime
import shutil

from agents.transcriber import transcribe_audio
from agents.analytics import calculate_analytics
from agents.summarizer import ai_summary
from agents.pdf_generator import create_pdf_report
from agents.search import search_meetings

AUDIO_FOLDER = Path("meeting_audio")
NOTES_FOLDER = Path("meeting_notes")
REPORTS_FOLDER = Path("meeting_reports")
ARCHIVE_FOLDER = Path("archive")

for folder in [AUDIO_FOLDER, NOTES_FOLDER, REPORTS_FOLDER, ARCHIVE_FOLDER]:
    folder.mkdir(exist_ok=True)

AUDIO_TYPES = ["*.mp3", "*.wav", "*.m4a"]

def save_transcript(transcript, source_name):
    today = datetime.now().strftime("%Y-%m-%d")
    transcript_name = source_name.rsplit(".", 1)[0] + f"_transcript_{today}.txt"
    transcript_path = NOTES_FOLDER / transcript_name

    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print("Transcript saved here:")
    print(transcript_path)

def create_report(transcript, source_name):
    today = datetime.now().strftime("%Y-%m-%d")
    analytics = calculate_analytics(transcript)
    report = ai_summary(transcript, analytics)

    txt_name = source_name.rsplit(".", 1)[0] + f"_modular_report_{today}.txt"
    pdf_name = source_name.rsplit(".", 1)[0] + f"_modular_report_{today}.pdf"

    txt_path = REPORTS_FOLDER / txt_name
    pdf_path = REPORTS_FOLDER / pdf_name

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report)

    print("Text report saved here:")
    print(txt_path)

    create_pdf_report(pdf_path, report, transcript, source_name, today, analytics)

    print("PDF report saved here:")
    print(pdf_path)

def process_audio():
    audio_files = []

    for audio_type in AUDIO_TYPES:
        audio_files.extend(AUDIO_FOLDER.glob(audio_type))

    if not audio_files:
        print("No audio files found.")
        print("Put an .mp3, .wav, or .m4a file inside the meeting_audio folder.")
        return

    latest_audio = max(audio_files, key=lambda file: file.stat().st_mtime)

    transcript = transcribe_audio(latest_audio)
    save_transcript(transcript, latest_audio.name)
    create_report(transcript, latest_audio.name)

    archived_path = ARCHIVE_FOLDER / latest_audio.name
    shutil.move(str(latest_audio), str(archived_path))

    print("Audio moved to archive:")
    print(archived_path)

def search_history():
    term = input("Search your meeting history: ")
    results = search_meetings(NOTES_FOLDER, term)

    print("\nSEARCH RESULTS")
    print("=" * 60)

    for result in results:
        print(result)
        print("-" * 60)

def main():
    print("Meeting Organizer AI")
    print("--------------------")
    print("1. Process new audio")
    print("2. Search meeting history")

    choice = input("Choose an option: ")

    if choice == "1":
        process_audio()
    elif choice == "2":
        search_history()
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()