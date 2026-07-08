import re
from collections import Counter

def calculate_analytics(transcript):
    words = re.findall(r"\b\w+\b", transcript)
    word_count = len(words)
    reading_time = max(1, round(word_count / 225))
    question_count = transcript.count("?")

    action_words = ["will", "need to", "needs to", "should", "must", "due", "assignment", "homework"]
    decision_words = ["decided", "agreed", "decision", "we chose", "we will"]

    lower = transcript.lower()
    action_count = sum(lower.count(word) for word in action_words)
    decision_count = sum(lower.count(word) for word in decision_words)

    stop_words = {
        "the", "and", "that", "this", "with", "you", "for", "are", "was", "were",
        "have", "has", "had", "but", "not", "from", "they", "our", "your", "about",
        "into", "like", "just", "what", "when", "where", "how", "why", "can", "will",
        "would", "could", "should", "there", "their", "then", "than", "them"
    }

    clean_words = [w.lower() for w in words if len(w) > 3 and w.lower() not in stop_words]
    common_topics = Counter(clean_words).most_common(8)

    return {
        "word_count": word_count,
        "reading_time": reading_time,
        "question_count": question_count,
        "action_count": action_count,
        "decision_count": decision_count,
        "common_topics": common_topics
    }