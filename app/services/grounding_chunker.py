"""GroundingChunker — intelligent document chunking for LLM context management.

Solves the problem where large documents (textbooks, long PDFs, reports) exceed
LLM context windows when passed in full, causing silent truncation or API errors.

Strategy:
  1. Split the document into semantically coherent chunks (section / paragraph boundaries).
  2. For the DECK PLANNER: produce a compressed "table of contents" summary that the
     LLM can plan from without needing the full text.
  3. For the SLIDE WRITER: retrieve only the chunks most relevant to each slide's
     topic / headline rather than using the same N characters for every batch.

No external ML dependencies — uses a lightweight TF-IDF-inspired keyword scorer.
"""

from __future__ import annotations

import math
import re
from typing import Sequence


# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
_CHUNK_SIZE_CHARS = 900          # target chars per chunk (before overlap)
_CHUNK_OVERLAP_CHARS = 120       # chars of trailing context carried into next chunk
_MAX_PLANNER_CHARS = 5000        # max chars for the compressed planning summary
_MAX_SLIDE_CONTEXT_CHARS = 700   # max chars of grounding to attach per slide
_MIN_CHUNK_SCORE = 0.05          # minimum relevance score to include a chunk


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
_HEADING_RE = re.compile(
    r"(?:^|\n)"
    r"(?:chapter|section|unit|part|lesson|topic|ch\.?|module)?\s*"
    r"(?:\d+[\.\-:)]\s*)?"
    r"([A-Z][A-Za-z0-9 ,&:'\-]{4,70})"
    r"(?:\n|\r|\.{2,}|$)",
    re.MULTILINE,
)
_STOP_WORDS = frozenset(
    "the a an and or but of in on at to for with by from that this is was are be been "
    "have has had will can could would should may might shall do does did not no its it "
    "we they their those these which who what when where how all some any many more most "
    "one two three its our also such other after before if so then than about".split()
)


def _tokenise(text: str) -> list[str]:
    """Lower-case word tokens, stop-word filtered."""
    return [
        w for w in re.findall(r"[a-z]{3,}", text.lower())
        if w not in _STOP_WORDS
    ]


def _term_freq(tokens: list[str]) -> dict[str, float]:
    """Normalised term frequency."""
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def _score_relevance(chunk_tokens: list[str], query_terms: set[str]) -> float:
    """TF-IDF-inspired relevance score of a chunk against a query term set."""
    if not chunk_tokens or not query_terms:
        return 0.0
    tf = _term_freq(chunk_tokens)
    score = 0.0
    for term in query_terms:
        if term in tf:
            idf_proxy = math.log(1 + len(term) / 4)
            score += tf[term] * idf_proxy
    return score / (math.sqrt(len(query_terms)) or 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class GroundingChunker:
    """Chunk large documents and retrieve relevant sections per slide topic."""

    @staticmethod
    def chunk_document(
        text: str,
        chunk_size: int = _CHUNK_SIZE_CHARS,
        overlap: int = _CHUNK_OVERLAP_CHARS,
    ) -> list[dict]:
        """Split *text* into overlapping chunks on paragraph/heading boundaries."""
        if not text or not text.strip():
            return []

        raw_paras = re.split(r"\n{2,}", text.strip())
        chunks: list[dict] = []
        buffer = ""
        current_heading = ""
        chunk_idx = 0

        for para in raw_paras:
            heading_match = _HEADING_RE.match("\n" + para)
            if heading_match and len(para) < 120:
                current_heading = heading_match.group(1).strip()

            if len(buffer) + len(para) + 2 >= chunk_size:
                if buffer.strip():
                    tokens = _tokenise(buffer)
                    chunks.append({
                        "text": buffer.strip(),
                        "index": chunk_idx,
                        "heading": current_heading,
                        "tokens": tokens,
                    })
                    chunk_idx += 1
                overlap_text = buffer[-overlap:] if len(buffer) > overlap else buffer
                buffer = overlap_text.lstrip() + "\n\n" + para
            else:
                buffer = (buffer + "\n\n" + para).strip() if buffer else para

        if buffer.strip():
            chunks.append({
                "text": buffer.strip(),
                "index": chunk_idx,
                "heading": current_heading,
                "tokens": _tokenise(buffer),
            })

        return chunks

    @staticmethod
    def compress_for_planning(
        text: str,
        max_chars: int = _MAX_PLANNER_CHARS,
    ) -> str:
        """Create a compact planning summary (TOC + excerpts) from a large document.

        Used by the DECK PLANNER so it sees the full structure without a context overflow.
        """
        if not text or not text.strip():
            return ""

        chunks = GroundingChunker.chunk_document(text)
        if not chunks:
            return text[:max_chars]

        lines: list[str] = []
        total = 0
        seen_headings: set[str] = set()

        for chunk in chunks:
            heading = chunk["heading"]
            body = chunk["text"]

            sentence_end = re.search(r"[.!?]\s+[A-Z]", body)
            if sentence_end:
                preview = body[: sentence_end.start() + 1].strip()
                remainder = body[sentence_end.start() + 1:]
                second = re.search(r"[.!?]\s", remainder)
                if second:
                    preview += " " + remainder[: second.start() + 1].strip()
            else:
                preview = body[:220].strip()
            preview = preview[:300]

            entry_lines: list[str] = []
            if heading and heading not in seen_headings:
                entry_lines.append(f"[SECTION: {heading}]")
                seen_headings.add(heading)
            if preview:
                entry_lines.append(preview)

            entry = "\n".join(entry_lines).strip()
            if not entry:
                continue

            if total + len(entry) + 2 > max_chars:
                remaining = max_chars - total - 20
                if remaining > 40:
                    lines.append(entry[:remaining] + "\u2026")
                break

            lines.append(entry)
            total += len(entry) + 2

        return "\n\n".join(lines)

    @staticmethod
    def retrieve_for_slides(
        text: str,
        slide_topics: Sequence[str],
        max_chars_total: int = _MAX_SLIDE_CONTEXT_CHARS * 5,
        max_chars_per_topic: int = _MAX_SLIDE_CONTEXT_CHARS,
    ) -> str:
        """Return the document sections most relevant to *slide_topics*.

        Used by the SLIDE WRITER to give each batch relevant evidence,
        not the same first 2500 chars every time.
        """
        if not text or not slide_topics:
            return text[:max_chars_total] if text else ""

        chunks = GroundingChunker.chunk_document(text)
        if not chunks:
            return text[:max_chars_total]

        query_tokens: set[str] = set()
        for topic in slide_topics:
            query_tokens.update(_tokenise(topic))

        scored = [
            (chunk, _score_relevance(chunk["tokens"], query_tokens))
            for chunk in chunks
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        selected_indices: set[int] = set()
        total = 0
        for chunk, score in scored:
            if score < _MIN_CHUNK_SCORE:
                break
            if total + len(chunk["text"]) > max_chars_total:
                remaining = max_chars_total - total
                if remaining > 150:
                    selected_indices.add(chunk["index"])
                break
            selected_indices.add(chunk["index"])
            total += len(chunk["text"]) + 2

        if not selected_indices:
            return text[:max_chars_total]

        result_parts: list[str] = []
        running = 0
        for chunk in chunks:
            if chunk["index"] not in selected_indices:
                continue
            excerpt = chunk["text"]
            if running + len(excerpt) > max_chars_total:
                excerpt = excerpt[: max_chars_total - running] + "\u2026"
            heading = chunk["heading"]
            if heading:
                result_parts.append(f"[{heading}]\n{excerpt}")
            else:
                result_parts.append(excerpt)
            running += len(excerpt) + 2
            if running >= max_chars_total:
                break

        return "\n\n".join(result_parts)

    @staticmethod
    def compress_prompt_for_retry(
        user_prompt: str,
        compression_level: int,
    ) -> str:
        """Progressively strip grounding from a composite prompt on context-error retry.

        Level 1 -> keep 60% of grounding
        Level 2 -> keep 30% of grounding
        Level 3 -> strip all grounding, keep only user instructions + slide plan
        """
        _GROUNDING_SENTINEL = "[MANDATORY GROUNDING DATA FROM ATTACHED DOCUMENTS]"
        _DIRECTIVES_SENTINEL = "[USER DIRECTIVES"

        if _GROUNDING_SENTINEL not in user_prompt:
            ratios = {1: 0.75, 2: 0.55, 3: 0.35}
            ratio = ratios.get(compression_level, 0.5)
            return user_prompt[: int(len(user_prompt) * ratio)]

        pre_grounding, rest = user_prompt.split(_GROUNDING_SENTINEL, 1)

        if compression_level >= 3:
            post_grounding_markers = [
                _DIRECTIVES_SENTINEL,
                "CRITICAL REQUIREMENT:",
                "Planned Slides Batch:",
                "User Goal:",
            ]
            cut_at = len(rest)
            for marker in post_grounding_markers:
                pos = rest.find(marker, 100)
                if pos != -1:
                    cut_at = min(cut_at, pos)
            post_grounding = rest[cut_at:] if cut_at < len(rest) else ""
            return (pre_grounding.strip() + "\n\n" + post_grounding.strip()).strip()

        ratios = {1: 0.60, 2: 0.30}
        keep_ratio = ratios.get(compression_level, 0.4)

        grounding_end = len(rest)
        for marker in [_DIRECTIVES_SENTINEL, "CRITICAL REQUIREMENT:", "Planned Slides Batch:"]:
            pos = rest.find(marker, 50)
            if pos != -1:
                grounding_end = min(grounding_end, pos)

        grounding_text = rest[:grounding_end]
        post_text = rest[grounding_end:]

        kept_grounding = grounding_text[: int(len(grounding_text) * keep_ratio)]
        if len(grounding_text) > len(kept_grounding):
            kept_grounding += "\n\n[... document truncated for context window compliance ...]"

        return (
            pre_grounding.strip()
            + f"\n\n{_GROUNDING_SENTINEL}:\n"
            + kept_grounding.strip()
            + "\n\n"
            + post_text.strip()
        ).strip()
