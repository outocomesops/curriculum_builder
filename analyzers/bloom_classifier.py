import json
import re
from dataclasses import dataclass
from typing import Optional

import requests

from config import BLOOM_LEVEL_ORDER

OLLAMA_TEMPERATURE_ANALYSIS = 0.1
_OLLAMA_NUM_CTX = 4096


@dataclass
class ClassificationResult:
    bloom_level: Optional[str]
    bloom_level_num: Optional[int]
    confidence: float
    source: str   # "keyword" | "llm" | "unclassified"


_LEVEL_NUM = {lvl: i + 1 for i, lvl in enumerate(BLOOM_LEVEL_ORDER)}


def _keyword_classify(verb: str, verb_index: dict[str, str]) -> Optional[str]:
    verb = verb.lower().strip()
    if verb in verb_index:
        return verb_index[verb]
    for indexed_verb, level in verb_index.items():
        if verb in indexed_verb or indexed_verb in verb:
            return level
    return None


def _ollama_classify(verb: str, outcome_text: str, ollama_url: str, model: str) -> Optional[str]:
    levels_str = ", ".join(BLOOM_LEVEL_ORDER)
    prompt = (
        f"You are an expert in Bloom's Revised Taxonomy (Anderson & Krathwohl, 2001).\n"
        f"The six cognitive levels in order are: {levels_str}.\n\n"
        f'Given this learning outcome:\n"{outcome_text}"\n\n'
        f'The primary action verb is: "{verb}"\n\n'
        f"Classify this verb into exactly one of these Bloom's levels: {levels_str}\n"
        f"Respond with ONLY the level name (lowercase, one word). No explanation."
    )
    try:
        resp = requests.post(
            f"{ollama_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": OLLAMA_TEMPERATURE_ANALYSIS, "num_ctx": _OLLAMA_NUM_CTX},
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["message"]["content"].strip().lower()
        word = re.match(r"[a-z]+", content)
        if word and word.group() in BLOOM_LEVEL_ORDER:
            return word.group()
    except Exception:
        pass
    return None


def classify_verb(
    verb: str,
    outcome_text: str,
    verb_index: dict[str, str],
    ollama_url: str = "http://localhost:11434",
    model: str = "llama3",
    use_ollama_fallback: bool = True,
) -> ClassificationResult:
    level = _keyword_classify(verb, verb_index)
    if level:
        return ClassificationResult(bloom_level=level, bloom_level_num=_LEVEL_NUM[level], confidence=1.0, source="keyword")

    if use_ollama_fallback:
        level = _ollama_classify(verb, outcome_text, ollama_url, model)
        if level:
            return ClassificationResult(bloom_level=level, bloom_level_num=_LEVEL_NUM[level], confidence=0.75, source="llm")

    return ClassificationResult(bloom_level=None, bloom_level_num=None, confidence=0.0, source="unclassified")
