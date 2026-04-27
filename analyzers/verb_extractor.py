import re

_ADVERB_SUFFIXES = (
    "ently", "antly", "ously", "ically", "ally", "ibly", "ably",
    "edly", "ively", "arily", "erly",
)


def _is_adverb(word: str) -> bool:
    w = word.lower()
    return any(w.endswith(sfx) for sfx in _ADVERB_SUFFIXES)


_PATTERNS = [
    r"(?:students?|graduates?|learners?|participants?)\s+(?:will|should|can|are able to)\s+([a-z]\w+)",
    r"upon\s+completion[^,]*,\s+(?:students?|graduates?|learners?)\s+(?:will|can|should)\s+([a-z]\w+)",
    r"be\s+able\s+to\s+([a-z]\w+)",
    r"^([a-z][a-z]+(?:e|y|t|n|ize|ise|fy|ate))\b",
]

_MULTIWORD_PHRASES = [
    "be familiar with",
    "be aware of",
    "be aware",
    "gain knowledge",
    "understand the importance",
    "be able to understand",
]

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "must", "can",
    "that", "this", "these", "those", "it", "its", "their", "our", "each",
    "all", "both", "any", "no", "not", "only", "also", "about", "through",
    "across", "among", "between", "into", "upon", "within",
}


def extract_verb(outcome_text: str) -> str | None:
    text = outcome_text.strip()
    lower = text.lower()

    for phrase in _MULTIWORD_PHRASES:
        if lower.startswith(phrase) or f" {phrase} " in lower:
            return phrase

    for pattern in _PATTERNS:
        m = re.search(pattern, lower)
        if m:
            candidate = m.group(1).strip().split()[0].rstrip(",.;:")
            if candidate not in _STOPWORDS and len(candidate) > 2 and not _is_adverb(candidate):
                return candidate

    words = re.findall(r"[a-zA-Z]+", text)
    for word in words[:4]:
        w = word.lower()
        if w not in _STOPWORDS and len(w) > 2 and not _is_adverb(w):
            return w

    return None
