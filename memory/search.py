import re
from memory.loader import load_memory_documents

def score_document(question, document):
    question_words = re.findall(r"\b\w+\b", question.lower())
    text = document["text"].lower()

    score = 0

    for word in question_words:
        if len(word) > 2:
            score += text.count(word)

    return score

def search_memory(question, top_k=5):
    documents = load_memory_documents()

    scored = []

    for document in documents:
        score = score_document(question, document)

        if score > 0:
            scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [document for score, document in scored[:top_k]]