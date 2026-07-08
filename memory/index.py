import subprocess

from memory.search import search_memory
from memory.prompts import build_memory_prompt

def ask_memory(question):
    documents = search_memory(question)

    if not documents:
        return (
            "I couldn't find any relevant information in your local memory.",
            []
        )

    prompt = build_memory_prompt(question, documents)

    result = subprocess.run(
        ["ollama", "run", "llama3.2"],
        input=prompt,
        text=True,
        capture_output=True
    )

    answer = result.stdout.strip()

    sources = [
        {
            "type": doc["source_type"],
            "file": doc["file_name"],
        }
        for doc in documents
    ]

    return answer, sources