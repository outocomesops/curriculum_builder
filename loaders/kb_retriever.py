"""
Knowledge Base Retriever
Agentic TF-IDF retrieval: Ollama generates queries → TF-IDF finds relevant chunks.
"""
from __future__ import annotations

import json
import logging

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

_CHAT_PATH = "/api/chat"
_PERSONA_LABELS = {
    "pedagogical_expert": "Pedagogical Expert",
    "accreditation_specialist": "Accreditation Specialist",
    "industry_liaison": "Industry Liaison",
    "student_advocate": "Student Advocate",
}
_MAX_KB_CONTEXT_CHARS = 6000


def build_tfidf_index(
    kb_index: dict[str, list[dict]],
) -> dict[str, tuple]:
    """
    Returns {persona: (TfidfVectorizer, doc_matrix, chunks_list)}.
    """
    persona_indices: dict[str, tuple] = {}
    for persona, chunks in kb_index.items():
        texts = [c["text"] for c in chunks]
        if not texts:
            continue
        vec = TfidfVectorizer(stop_words="english", max_features=10000)
        matrix = vec.fit_transform(texts)
        persona_indices[persona] = (vec, matrix, chunks)
    return persona_indices


def retrieve_chunks(
    persona_indices: dict[str, tuple],
    queries: list[str],
    top_k: int = 3,
) -> dict[str, list[str]]:
    """
    For each persona, retrieves top_k unique chunks across all queries.
    Returns {persona: [chunk_text, ...]}.
    """
    results: dict[str, list[str]] = {}
    for persona, (vec, matrix, chunks) in persona_indices.items():
        seen_indices: set[int] = set()
        ranked: list[tuple[float, int]] = []
        for q in queries:
            try:
                q_vec = vec.transform([q])
                scores = cosine_similarity(q_vec, matrix).flatten()
                for idx in scores.argsort()[::-1]:
                    if idx not in seen_indices:
                        ranked.append((float(scores[idx]), int(idx)))
                        seen_indices.add(int(idx))
            except Exception:
                continue

        ranked.sort(reverse=True)
        top_chunks = [chunks[idx]["text"] for _, idx in ranked[:top_k] if _ > 0.0]
        if top_chunks:
            results[persona] = top_chunks
    return results


def generate_retrieval_queries(
    program_name: str,
    program_level: str,
    step_name: str,
    ollama_url: str,
    model: str,
) -> list[str]:
    """
    Non-streaming Ollama call to generate 3 targeted retrieval queries.
    Falls back to basic queries on any error.
    """
    fallback = [program_name, program_level, step_name]
    prompt = (
        f"You are helping retrieve expert knowledge for curriculum design.\n"
        f"Program: {program_name} ({program_level})\n"
        f"Current step: {step_name}\n\n"
        f"Generate exactly 3 short, specific search queries (one per line, no numbering, no explanation) "
        f"to retrieve the most relevant pedagogical, accreditation, and industry knowledge "
        f"for this step. Focus on what an expert reviewer would look for."
    )
    try:
        resp = requests.post(
            f"{ollama_url}{_CHAT_PATH}",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.2, "num_ctx": 2048},
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "")
        queries = [line.strip() for line in content.splitlines() if line.strip()][:3]
        return queries if len(queries) >= 1 else fallback
    except Exception as exc:
        logger.warning("Query generation failed, using fallback: %s", exc)
        return fallback


def build_kb_context(
    persona_indices: dict[str, tuple],
    queries: list[str],
    top_k: int = 3,
) -> str:
    """
    Retrieves chunks and formats them as a context block for injection into prompts.
    Truncated to _MAX_KB_CONTEXT_CHARS total.
    """
    if not persona_indices or not queries:
        return ""

    retrieved = retrieve_chunks(persona_indices, queries, top_k=top_k)
    if not retrieved:
        return ""

    lines = ["=== EXPERT KNOWLEDGE BASE ==="]
    for persona, chunks in retrieved.items():
        label = _PERSONA_LABELS.get(persona, persona.replace("_", " ").title())
        lines.append(f"\n--- {label} ---")
        for chunk in chunks:
            lines.append(chunk)

    context = "\n".join(lines)
    if len(context) > _MAX_KB_CONTEXT_CHARS:
        context = context[:_MAX_KB_CONTEXT_CHARS] + "\n[...truncated]"
    return context
