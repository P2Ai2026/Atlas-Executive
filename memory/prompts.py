def build_memory_prompt(question, documents):
    context = ""

    for i, doc in enumerate(documents, start=1):
        context += f"""
SOURCE {i}
Type: {doc["source_type"]}
File: {doc["file_name"]}

{doc["text"][:5000]}
"""

    prompt = f"""
You are AI Memory, a local research assistant.

Answer the user's question using ONLY the sources provided below.
If the sources do not contain the answer, say you could not find enough information.

After your answer, include a "Sources Used" section listing the file names.

User Question:
{question}

Sources:
{context}
"""

    return prompt