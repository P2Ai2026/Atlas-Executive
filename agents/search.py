from pathlib import Path

def search_meetings(notes_folder, search_term):
    transcript_files = list(Path(notes_folder).glob("*.txt"))

    if not transcript_files:
        return ["No transcript files found."]

    results = []
    lower_search = search_term.lower()

    for file in transcript_files:
        text = file.read_text(encoding="utf-8", errors="ignore")
        lower_text = text.lower()

        if lower_search in lower_text:
            index = lower_text.find(lower_search)
            start = max(0, index - 250)
            end = min(len(text), index + 250)
            snippet = text[start:end].replace("\n", " ")

            results.append(f"FOUND IN: {file.name}\n...{snippet}...")

    if not results:
        results.append(f"No results found for: {search_term}")

    return results