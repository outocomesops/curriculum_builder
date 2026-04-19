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


_CONSOLIDATION_PROMPT = """\
You are a curriculum design expert. Below are summaries extracted from multiple institutional
documents of the same higher education institution. Synthesise them into a single coherent
institutional profile of no more than 1000 words.

Cover:
- Mission, vision, and core values
- Educational philosophy and pedagogical approach
- Quality expectations and accreditation commitments
- Desired graduate competencies and outcomes
- Community, social, or professional commitments

Be concise, avoid repetition, and write in third person.

--- Individual summaries ---
{summaries}
---"""


_REPUTATION_PROMPT = """\
You are analysing public perception of a higher education institution based on web sources.

Institution: {institution_name}

--- Web sources ---
{sources_text}
---

Write a structured reputation profile (400-600 words) covering:
1. Overall public sentiment
2. Specific programs, services, or aspects that are praised
3. Common criticisms or concerns raised by students or the community
4. Graduate employment outcomes and career reputation (if mentioned)
5. Community relationships and social standing
6. Notable recent events or news

Be factual, balanced, and cite specific details where available."""


def summarize_doc(
    text: str,
    filename: str,
    ollama_url: str,
    model: str,
) -> dict:
    """
    Run an institutional document through the LLM to extract values/policies.
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


def consolidate_summaries(
    doc_summaries: list[dict],
    ollama_url: str,
    model: str,
) -> str:
    """
    Merge individual document summaries into a single institutional profile (≤1000 words).
    Returns the consolidated text string.
    """
    useful = [d for d in doc_summaries if d.get("has_content") and d.get("summary")]
    if not useful:
        return ""

    summaries_text = "\n\n".join(
        f"[{d['filename']}]\n{d['summary']}" for d in useful
    )
    prompt = _CONSOLIDATION_PROMPT.format(summaries=summaries_text)

    try:
        resp = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=240,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as exc:
        return f"Consolidation failed: {exc}"


def summarize_reputation(
    institution_name: str,
    snippets: list[dict],
    ollama_url: str,
    model: str,
) -> str:
    """
    Summarise web snippets / paste text into a structured reputation profile.
    Returns the reputation summary string.
    """
    sources_text = "\n\n".join(
        f"[{s.get('title', 'Source')}]\n{s.get('snippet', s.get('text', ''))}"
        for s in snippets
        if s.get("snippet") or s.get("text")
    )
    if not sources_text.strip():
        return "No reputation data could be extracted from the provided sources."

    prompt = _REPUTATION_PROMPT.format(
        institution_name=institution_name,
        sources_text=sources_text[:6000],
    )

    try:
        resp = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as exc:
        return f"Reputation analysis failed: {exc}"
