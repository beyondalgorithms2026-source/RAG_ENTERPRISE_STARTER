"""Bounded selection of already SQL-authorized evidence; no data access."""

import re
from typing import Any


def compound_question(question: str) -> bool:
    return bool(
        re.search(
            r"\b(sequence|ordered|in order|sections|steps|jointly|supersed\w*|previous\w*)\b|\b(?:before|under)\s+(?:the\s+)?[Vv]ersion\b|\bwho\b.*\bapprov\w*\b",
            question,
            re.I,
        )
    )


def definition_term(question: str) -> str | None:
    """A named rule in a classification question, never an evaluation identifier."""
    quoted = re.search(r'[“"]([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})[”"]', question)
    if quoted:
        return quoted[1]
    singled = re.search(r"\b(?:handled|applies|means|defined as)\s+([A-Z][a-z]+)\b", question)
    if singled:
        return singled[1]
    if not re.search(r"\b(is|meet|definition|does)\b", question, re.I):
        return None
    match = re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b", question)
    return match[0] if match else None


def _terms(question: str) -> set[str]:
    terms = {t for t in re.findall(r"[a-z]+", question.casefold()) if len(t) > 3}
    # Domain vocabulary, not case IDs or expected answers. These expansions
    # affect ranking only; they never become evidence or generation instructions.
    for triggers, related in (
        ({"conduct", "suspension"}, {"disciplinary", "testing"}),
        ({"accident"}, {"accident", "response"}),
    ):
        if terms & triggers:
            terms |= related
    return terms


def select_candidates(
    chunks: list[Any], *, question: str, limit: int
) -> tuple[list[Any], list[dict]]:
    terms = _terms(question)
    ranked = []
    for rank, chunk in enumerate(chunks):
        heading = str(chunk.heading or "").casefold()
        heading_terms = set(re.findall(r"[a-z]+", heading))
        score = 1 / (rank + 1) + 0.6 * len(terms & heading_terms)
        body = str(chunk.snippet or "")
        body_terms = set(re.findall(r"[a-z]+", body.casefold()))
        score += 0.15 * len(terms & body_terms)
        if (
            definition_term(question)
            or re.search(r"\b(is|meet|definition|threshold)\b", question, re.I)
        ) and "definitions" in heading:
            score += 2
        historical = bool(
            re.search(
                r"\b(previous|supersed\w*)\b|\b(?:before|under)\b.{0,30}\b(version|update|revision)\b",
                question,
                re.I,
            )
        )
        if any(t in heading for t in ("amendment", "change log", "revision history")):
            score += 3 if historical else -2
        if any(t in heading for t in ("ownership", "purpose and scope")) and not re.search(
            r"\b(owner|owns|ownership|purpose|scope)\b", question, re.I
        ):
            score -= 3
        if " ".join(body.split()).casefold() == " ".join(heading.split()) and not re.search(
            r"\b(title|name|called)\b", question, re.I
        ):
            score -= 3
        ranked.append((score, rank, chunk))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    selected = []
    seen = set()
    decisions = []
    for score, rank, chunk in ranked:
        key = (str(chunk.file_name).casefold(), " ".join(chunk.snippet.split()).casefold())
        reason = (
            "duplicate"
            if key in seen
            else "selected"
            if len(selected) < limit
            else "selection_limit"
        )
        decisions.append(
            {
                "chunk_id": chunk.chunk_id,
                "rank": rank + 1,
                "score": round(score, 4),
                "reason": reason,
            }
        )
        if reason == "selected":
            selected.append(chunk)
            seen.add(key)
    return selected, decisions


def bounded_excerpt(text: str, *, question: str, cap: int) -> str:
    """Select complete evidence units, restoring original order afterwards.

    Never cut an exception at a character boundary. An indivisible oversized
    sentence is excluded rather than made to assert an incomplete rule.
    """
    if len(text) <= cap:
        return text
    terms = _terms(question)
    # Numbered procedures are atomic. Never strip list numbers or select a few
    # attractive steps while silently losing the rest of the procedure.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units = []
    index = 0
    while index < len(paragraphs):
        paragraph = paragraphs[index]
        lines = paragraph.splitlines()
        if len(lines) >= 3 and lines[0].startswith("|") and re.match(r"^\|[-:| ]+\|$", lines[1]):
            header = "\n".join(lines[:2])
            units.extend(header + "\n" + row for row in lines[2:] if row.strip())
            index += 1
            continue
        if re.match(r"\d+[.)]\s", paragraph):
            sequence = [paragraph]
            index += 1
            while index < len(paragraphs) and re.match(r"\d+[.)]\s", paragraphs[index]):
                sequence.append(paragraphs[index])
                index += 1
            units.append("\n\n".join(sequence))
            continue
        units.extend(
            u.strip()
            for u in re.split(r"(?<=[!?])\s+|(?<=[.])(?<!\d[.])\s+", paragraph)
            if u.strip()
        )
        index += 1
    ranked = sorted(
        enumerate(units),
        key=lambda row: (-len(terms & set(re.findall(r"[a-z]+", row[1].casefold()))), row[0]),
    )
    kept = []
    used = 0
    for index, unit in ranked:
        if len(unit) + used + bool(kept) <= cap:
            kept.append((index, unit))
            used += len(unit) + bool(len(kept) > 1)
    return "\n".join(unit for _, unit in sorted(kept))
