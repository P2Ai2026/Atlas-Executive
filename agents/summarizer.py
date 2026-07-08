import subprocess

def ai_summary(transcript, analytics):
    topics = ", ".join([topic for topic, count in analytics["common_topics"]])

    prompt = f"""
You are a professional meeting assistant.

Create a polished meeting report with these sections:

1. Executive Summary
2. Key Topics
3. Action Items
4. Decisions Made
5. Unanswered Questions
6. Important Notes

Use clear bullet points. Be specific. If something is not mentioned, say "None clearly identified."

Possible common topics from the transcript:
{topics}

Transcript:
{transcript}
"""

    result = subprocess.run(
        ["ollama", "run", "llama3.2"],
        input=prompt,
        text=True,
        capture_output=True
    )

    return result.stdout.strip()