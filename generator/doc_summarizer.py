import requests


_SUMMARY_PROMPT = """\
You are reviewing a document from a higher education institution to extract information
useful for curriculum design.

Extract and summarize the following (if present):
1. Institutional mission, vision, and core values
2. Educational philosophy and pedagogical approach
3. Program quality expectations and policies
4. Any stated graduate competencies or desired outcomes
5. Community, social, or professional commitments

Document name: {filename}
---
{excerpt}
---

Respond with a structured summary of 300-500 words covering only what is actually present.
If the document contains no relevant institutional or educational content (e.g. financial report,
equipment manual, unrelated legal text), respond with exactly: NO_CONTENT"""


def summarize_doc(
    text: str,
    filename: str,
    ollama_url: str,
    model: str,
) -> dict:
    """
    Run the institutional document through the LLM to extract values/policies.
    Returns {filename, summary, has_content, error?}.
    """
    excerpt = text[:4500]
    prompt = _SUMMARY_PROMPT.format(filename=filename, excerpt=excerpt)

    try:
        resp = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=180,
        )
        resp.raise_for_status()
        summary = resp.json()["message"]["content"].strip()
        has_content = not summary.startswith("NO_CONTENT")
        return {
            "filename": filename,
            "summary": summary if has_content else "",
            "has_content": has_content,
        }
    except Exception as exc:
        return {"filename": filename, "summary": "", "has_content": False, "error": str(exc)}


def batch_summarize(
    docs: list[dict],
    ollama_url: str,
    model: str,
    progress_callback=None,
) -> list[dict]:
    results = []
    for i, doc in enumerate(docs):
        result = summarize_doc(doc["text"], doc["filename"], ollama_url, model)
        results.append(result)
        if progress_callback:
            progress_callback(i + 1, len(docs), doc["filename"])
    return results
