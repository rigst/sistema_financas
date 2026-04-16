import re
import unicodedata
from difflib import SequenceMatcher


def normalize_search_text(value):
    text = str(value or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def _split_words(text):
    return [word for word in re.split(r"[^a-z0-9]+", text) if word]


def _resolve_attr(obj, path):
    current = obj
    for part in path.split("__"):
        current = getattr(current, part, None)
        if current is None:
            return ""
    return str(current or "")


def _fuzzy_token_score(token, words):
    best = 0.0
    for word in words:
        if token in word or word in token:
            return 1.0
        score = SequenceMatcher(None, token, word).ratio()
        if score > best:
            best = score
    return best


def filter_ranked_search(objects, search, fields):
    query_raw = str(search or "").strip()
    if not query_raw:
        return list(objects)

    query_norm = normalize_search_text(query_raw)
    if not query_norm:
        return list(objects)

    query_tokens = _split_words(query_norm)
    ranked = []

    for idx, obj in enumerate(objects):
        values = [_resolve_attr(obj, field) for field in fields]
        raw_joined = " ".join(values).casefold()
        norm_joined = normalize_search_text(" ".join(values))

        if query_raw.casefold() in raw_joined:
            ranked.append((0, 0.0, idx, obj))
            continue

        if query_norm in norm_joined:
            ranked.append((1, 0.0, idx, obj))
            continue

        if query_tokens and all(token in norm_joined for token in query_tokens):
            ranked.append((2, 0.0, idx, obj))
            continue

        if not query_tokens:
            continue

        words = _split_words(norm_joined)
        if not words:
            continue

        token_scores = [_fuzzy_token_score(token, words) for token in query_tokens]
        strong_matches = [score for score in token_scores if score >= 0.74]
        if not strong_matches:
            continue

        fuzzy_score = sum(token_scores) / len(token_scores)
        ranked.append((3, -fuzzy_score, idx, obj))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in ranked]
